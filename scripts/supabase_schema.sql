-- PRISM Supabase Database Schema
-- Run this SQL in your Supabase SQL Editor (supabase.com -> SQL Editor -> New Query)

-- ============================================
-- TABLES
-- ============================================

-- Users table (extends Supabase auth.users)
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    color TEXT DEFAULT '#808080',  -- User's RGB color for visualization
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Projects table
CREATE TABLE public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,          -- URL-friendly identifier
    name TEXT NOT NULL,                 -- Display name
    description TEXT,
    owner_id UUID REFERENCES public.profiles(id),
    is_public BOOLEAN DEFAULT FALSE,    -- Accessible via /public/{slug}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Project membership (which users can access which projects)
CREATE TABLE public.project_members (
    project_id UUID REFERENCES public.projects(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member',         -- 'owner', 'admin', 'member'
    color TEXT,                         -- User's color in THIS project (RGB)
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (project_id, user_id)
);

-- Nodes table (equivalent to nodes/{uuid}.json)
CREATE TABLE public.nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES public.projects(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    parent_id UUID REFERENCES public.nodes(id) ON DELETE SET NULL,
    description TEXT DEFAULT '',
    node_type TEXT DEFAULT 'default',
    created_by UUID REFERENCES public.profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User votes (equivalent to data/{user}.json -> nodes)
CREATE TABLE public.user_node_votes (
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    node_id UUID REFERENCES public.nodes(id) ON DELETE CASCADE,
    interested BOOLEAN,                 -- TRUE=accept, FALSE=reject, NULL=pending
    metadata TEXT DEFAULT '',           -- User's private notes
    voted_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, node_id)
);

-- Node types per project (equivalent to node_types/{type}/definition.json)
CREATE TABLE public.node_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES public.projects(id) ON DELETE CASCADE,
    type_name TEXT NOT NULL,            -- e.g., 'default', 'game_concept'
    definition JSONB NOT NULL,          -- The full definition.json content
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, type_name)
);

-- Prompts per node type (equivalent to node_types/{type}/*.md files)
CREATE TABLE public.prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type_id UUID REFERENCES public.node_types(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                 -- Prompt file name (without .md)
    display_name TEXT NOT NULL,
    description TEXT,
    icon TEXT DEFAULT 'psychology',
    produces_type TEXT,                 -- Which node_type this generates
    body TEXT NOT NULL,                 -- The prompt template content
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX idx_nodes_project ON public.nodes(project_id);
CREATE INDEX idx_nodes_parent ON public.nodes(parent_id);
CREATE INDEX idx_votes_node ON public.user_node_votes(node_id);
CREATE INDEX idx_votes_user ON public.user_node_votes(user_id);
CREATE INDEX idx_projects_slug ON public.projects(slug);
CREATE INDEX idx_projects_public ON public.projects(is_public) WHERE is_public = TRUE;

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_node_votes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.node_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompts ENABLE ROW LEVEL SECURITY;

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
-- RLS POLICIES
-- ============================================

-- Profiles: Users can read all, update only their own
CREATE POLICY "Profiles are viewable by everyone" ON public.profiles
    FOR SELECT USING (true);
CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Users can insert their own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);

-- Projects: Public projects readable by all, private by members only
CREATE POLICY "Public projects are viewable by everyone" ON public.projects
    FOR SELECT USING (is_public = TRUE);
CREATE POLICY "Members can view their projects" ON public.projects
    FOR SELECT USING (public.is_project_member(id));
CREATE POLICY "Members can update their projects" ON public.projects
    FOR UPDATE USING (public.is_project_admin(id));
CREATE POLICY "Authenticated users can create projects" ON public.projects
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- Project members: viewable by project members (uses helper function to avoid recursion)
CREATE POLICY "Project members viewable by members" ON public.project_members
    FOR SELECT USING (
        public.is_project_member(project_id)
        OR project_id IN (SELECT id FROM public.projects WHERE is_public = TRUE)
    );
CREATE POLICY "Admins can manage members" ON public.project_members
    FOR ALL USING (public.is_project_admin(project_id));

-- Nodes: Readable if project is public OR user is member, writable by members only
CREATE POLICY "Nodes readable on public projects" ON public.nodes
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE is_public = TRUE)
    );
CREATE POLICY "Nodes readable by project members" ON public.nodes
    FOR SELECT USING (public.is_project_member(project_id));
CREATE POLICY "Nodes writable by project members" ON public.nodes
    FOR ALL USING (public.is_project_member(project_id));

-- Votes: Users can only manage their own votes
CREATE POLICY "Users can view all votes on accessible nodes" ON public.user_node_votes
    FOR SELECT USING (
        node_id IN (
            SELECT id FROM public.nodes WHERE 
                project_id IN (SELECT id FROM public.projects WHERE is_public = TRUE)
                OR public.is_project_member(project_id)
        )
    );
CREATE POLICY "Users can manage only their own votes" ON public.user_node_votes
    FOR ALL USING (auth.uid() = user_id);

-- Node types and prompts: Same access as nodes
CREATE POLICY "Node types readable on accessible projects" ON public.node_types
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE is_public = TRUE)
        OR public.is_project_member(project_id)
    );
CREATE POLICY "Node types writable by members" ON public.node_types
    FOR ALL USING (public.is_project_member(project_id));

CREATE POLICY "Prompts readable via node_type access" ON public.prompts
    FOR SELECT USING (
        node_type_id IN (SELECT id FROM public.node_types)  -- Inherits from node_types policy
    );
CREATE POLICY "Prompts writable via node_type access" ON public.prompts
    FOR ALL USING (
        node_type_id IN (
            SELECT id FROM public.node_types WHERE public.is_project_member(project_id)
        )
    );

-- ============================================
-- REALTIME (Enable for live updates)
-- ============================================

-- Enable realtime for nodes and votes tables
ALTER PUBLICATION supabase_realtime ADD TABLE public.nodes;
ALTER PUBLICATION supabase_realtime ADD TABLE public.user_node_votes;

-- ============================================
-- FUNCTIONS & TRIGGERS
-- ============================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON public.projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nodes_updated_at BEFORE UPDATE ON public.nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_node_types_updated_at BEFORE UPDATE ON public.node_types
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_prompts_updated_at BEFORE UPDATE ON public.prompts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, username, display_name)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'username', split_part(NEW.email, '@', 1)),
        COALESCE(NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1))
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
