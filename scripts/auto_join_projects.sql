-- Auto-join functionality for public projects
-- Run this in your Supabase SQL Editor

-- Function to auto-join a public project (bypasses RLS)
CREATE OR REPLACE FUNCTION public.join_public_project(p_project_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_user_id UUID;
    v_is_public BOOLEAN;
    v_email TEXT;
BEGIN
    -- Get current user
    v_user_id := auth.uid();
    IF v_user_id IS NULL THEN
        RAISE NOTICE 'No authenticated user';
        RETURN FALSE;
    END IF;
    
    -- Ensure profile exists (create if missing)
    IF NOT EXISTS (SELECT 1 FROM profiles WHERE id = v_user_id) THEN
        -- Get email from auth.users
        SELECT email INTO v_email FROM auth.users WHERE id = v_user_id;
        
        INSERT INTO profiles (id, username, display_name)
        VALUES (
            v_user_id,
            COALESCE(split_part(v_email, '@', 1), 'user'),
            COALESCE(split_part(v_email, '@', 1), 'User')
        );
        RAISE NOTICE 'Created profile for user %', v_user_id;
    END IF;
    
    -- Check if already a member
    IF EXISTS (
        SELECT 1 FROM project_members 
        WHERE project_id = p_project_id AND user_id = v_user_id
    ) THEN
        RETURN TRUE;  -- Already a member
    END IF;
    
    -- Check if project is public
    SELECT is_public INTO v_is_public 
    FROM projects 
    WHERE id = p_project_id;
    
    IF v_is_public IS NULL THEN
        RAISE NOTICE 'Project % not found', p_project_id;
        RETURN FALSE;
    END IF;
    
    IF NOT v_is_public THEN
        RAISE NOTICE 'Project % is not public', p_project_id;
        RETURN FALSE;  -- Can't join non-public projects
    END IF;
    
    -- Join the project
    INSERT INTO project_members (project_id, user_id, role)
    VALUES (p_project_id, v_user_id, 'member');
    
    RAISE NOTICE 'User % joined project %', v_user_id, p_project_id;
    RETURN TRUE;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION public.join_public_project(UUID) TO authenticated;

-- Also allow inserting into project_members for public projects (as alternative)
CREATE POLICY "Users can join public projects" ON public.project_members
    FOR INSERT 
    WITH CHECK (
        user_id = auth.uid() 
        AND project_id IN (SELECT id FROM public.projects WHERE is_public = TRUE)
        AND role = 'member'
    );
