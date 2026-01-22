-- PRISM RLS Policy Fix - Resolves infinite recursion in project_members
-- Run this in Supabase SQL Editor to fix the recursion error

-- ============================================
-- DROP EXISTING POLICIES (that have recursion issues)
-- ============================================

DROP POLICY IF EXISTS "Project members viewable by members" ON public.project_members;
DROP POLICY IF EXISTS "Admins can manage members" ON public.project_members;
DROP POLICY IF EXISTS "Members can view their projects" ON public.projects;
DROP POLICY IF EXISTS "Members can update their projects" ON public.projects;
DROP POLICY IF EXISTS "Nodes readable by project members" ON public.nodes;
DROP POLICY IF EXISTS "Nodes writable by project members" ON public.nodes;
DROP POLICY IF EXISTS "Users can view all votes on accessible nodes" ON public.user_node_votes;
DROP POLICY IF EXISTS "Node types readable on accessible projects" ON public.node_types;
DROP POLICY IF EXISTS "Node types writable by members" ON public.node_types;
DROP POLICY IF EXISTS "Prompts writable via node_type access" ON public.prompts;

-- ============================================
-- HELPER FUNCTIONS (to avoid RLS recursion)
-- ============================================

-- Security definer function to check project membership without triggering RLS
CREATE OR REPLACE FUNCTION public.is_project_member(p_project_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.project_members
        WHERE project_id = p_project_id AND user_id = auth.uid()
    );
$$;

-- Security definer function to check if user is admin/owner of project
CREATE OR REPLACE FUNCTION public.is_project_admin(p_project_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.project_members
        WHERE project_id = p_project_id 
          AND user_id = auth.uid()
          AND role IN ('owner', 'admin')
    );
$$;

-- Security definer function to get all project IDs user is a member of
CREATE OR REPLACE FUNCTION public.user_project_ids()
RETURNS SETOF UUID
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
    SELECT project_id FROM public.project_members WHERE user_id = auth.uid();
$$;

-- ============================================
-- RECREATE POLICIES (using helper functions)
-- ============================================

-- Projects: private projects viewable by members only
CREATE POLICY "Members can view their projects" ON public.projects
    FOR SELECT USING (public.is_project_member(id));
CREATE POLICY "Members can update their projects" ON public.projects
    FOR UPDATE USING (public.is_project_admin(id));

-- Project members: viewable by project members (uses helper function to avoid recursion)
CREATE POLICY "Project members viewable by members" ON public.project_members
    FOR SELECT USING (
        public.is_project_member(project_id)
        OR project_id IN (SELECT id FROM public.projects WHERE is_public = TRUE)
    );
CREATE POLICY "Admins can manage members" ON public.project_members
    FOR ALL USING (public.is_project_admin(project_id));

-- Nodes: Readable by members
CREATE POLICY "Nodes readable by project members" ON public.nodes
    FOR SELECT USING (public.is_project_member(project_id));
CREATE POLICY "Nodes writable by project members" ON public.nodes
    FOR ALL USING (public.is_project_member(project_id));

-- Votes: Users can view votes on accessible nodes
CREATE POLICY "Users can view all votes on accessible nodes" ON public.user_node_votes
    FOR SELECT USING (
        node_id IN (
            SELECT id FROM public.nodes WHERE 
                project_id IN (SELECT id FROM public.projects WHERE is_public = TRUE)
                OR public.is_project_member(project_id)
        )
    );

-- Node types
CREATE POLICY "Node types readable on accessible projects" ON public.node_types
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE is_public = TRUE)
        OR public.is_project_member(project_id)
    );
CREATE POLICY "Node types writable by members" ON public.node_types
    FOR ALL USING (public.is_project_member(project_id));

-- Prompts
CREATE POLICY "Prompts writable via node_type access" ON public.prompts
    FOR ALL USING (
        node_type_id IN (
            SELECT id FROM public.node_types WHERE public.is_project_member(project_id)
        )
    );
