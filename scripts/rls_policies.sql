-- Re-enable RLS with simplified, non-recursive policies
-- These policies use direct queries instead of helper functions to avoid recursion

-- ============================================================================
-- NODES TABLE POLICIES
-- ============================================================================
-- Strategy: 
-- - SELECT: Authenticated users can read nodes from projects they're members of
-- - INSERT: Authenticated users can create nodes (project membership checked in app layer)
-- - UPDATE: Authenticated users can update nodes (project membership checked in app layer)  
-- - DELETE: Authenticated users can delete nodes (project membership checked in app layer)
--
-- Note: We don't check project membership in the policy itself to avoid infinite
-- recursion through project_members table. The backend (SupabaseBackend) enforces
-- membership via ensure_project_membership() before any operation.

-- Drop existing policies on nodes (these were permissive placeholders)
DROP POLICY IF EXISTS "nodes_select_policy" ON nodes;
DROP POLICY IF EXISTS "nodes_insert_policy" ON nodes;
DROP POLICY IF EXISTS "nodes_update_policy" ON nodes;
DROP POLICY IF EXISTS "nodes_delete_policy" ON nodes;

-- CREATE: Only authenticated users can insert nodes
CREATE POLICY "nodes_insert_authenticated"
  ON nodes FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

-- READ: Only authenticated users can select nodes
-- (In practice, users only see nodes from projects they're members of via backend)
CREATE POLICY "nodes_select_authenticated"
  ON nodes FOR SELECT
  USING (auth.uid() IS NOT NULL);

-- UPDATE: Only authenticated users can update nodes
-- Could add: "AND user_id = auth.uid()" but would require tracking per-node ownership
CREATE POLICY "nodes_update_authenticated"
  ON nodes FOR UPDATE
  WITH CHECK (auth.uid() IS NOT NULL);

-- DELETE: Only authenticated users can delete nodes
CREATE POLICY "nodes_delete_authenticated"
  ON nodes FOR DELETE
  USING (auth.uid() IS NOT NULL);

-- ============================================================================
-- USER_NODE_VOTES TABLE POLICIES
-- ============================================================================
-- Strategy:
-- - SELECT: Users can read votes for nodes in projects they're members of
-- - INSERT: Users can insert votes (only their own)
-- - UPDATE: Users can update their own votes
-- - DELETE: Users can delete their own votes

-- Drop existing policies
DROP POLICY IF EXISTS "user_node_votes_select_policy" ON user_node_votes;
DROP POLICY IF EXISTS "user_node_votes_insert_policy" ON user_node_votes;
DROP POLICY IF EXISTS "user_node_votes_update_policy" ON user_node_votes;
DROP POLICY IF EXISTS "user_node_votes_delete_policy" ON user_node_votes;

-- CREATE: Users can only insert votes for themselves
CREATE POLICY "user_node_votes_insert_own"
  ON user_node_votes FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- READ: Users can read votes (filtering by project membership done in backend)
CREATE POLICY "user_node_votes_select_authenticated"
  ON user_node_votes FOR SELECT
  USING (auth.uid() IS NOT NULL);

-- UPDATE: Users can only update their own votes
CREATE POLICY "user_node_votes_update_own"
  ON user_node_votes FOR UPDATE
  WITH CHECK (auth.uid() = user_id);

-- DELETE: Users can only delete their own votes
CREATE POLICY "user_node_votes_delete_own"
  ON user_node_votes FOR DELETE
  USING (auth.uid() = user_id);

-- ============================================================================
-- RE-ENABLE ROW LEVEL SECURITY
-- ============================================================================
ALTER TABLE public.nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_node_votes ENABLE ROW LEVEL SECURITY;

-- Verify policies are enabled
SELECT
  schemaname,
  tablename,
  rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('nodes', 'user_node_votes');
