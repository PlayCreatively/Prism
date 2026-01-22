-- Create project 'online-test' in Supabase
-- Run this in your Supabase SQL Editor

-- Insert project (will fail if slug already exists due to UNIQUE constraint)
INSERT INTO public.projects (slug, name, is_public)
VALUES ('online-test', 'Online Test', TRUE)
ON CONFLICT (slug) DO UPDATE SET 
    name = EXCLUDED.name,
    is_public = EXCLUDED.is_public;

-- Verify it was created
SELECT id, slug, name, is_public FROM public.projects WHERE slug = 'online-test';
