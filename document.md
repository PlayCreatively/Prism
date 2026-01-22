# Project Definition: PRISM
**Collaborative Consensus & Interest Mapping Engine**

## 1. Executive Summary
Prism is an interactive tool designed to visualize, align, and refine shared research interests among three collaborators (Alex, Sasha, Alison). Unlike a standard mind-map, Prism uses a **state-aware directed graph** to visualize consensus through color (RGB theory) and employs an AI agent to facilitate an iterative "Drill Down" process.

The system is designed to be **iterative and persistent**, meaning it evolves over time without ever requiring a "clean slate" restart.

---

## 2. Core Visual Logic: The RGB Model
The visual language of the graph is mathematically derived from the "Interested Users" list attached to each node.

### Node Coloring
Nodes are not manually colored; they are calculated dynamically:
*   **Primary (Individual Interest):**
    *   🔴 **Red:** Alex only.
    *   🟢 **Green:** Sasha only.
    *   🔵 **Blue:** Alison only.
*   **Secondary (Partial Consensus):**
    *   🟡 **Yellow:** Alex + Sasha.
    *   🟣 **Magenta:** Alex + Alison.
    *   💠 **Cyan:** Sasha + Alison.
*   **Tertiary (Full Consensus):**
    *   ⚪ **White:** All 3 Users.

### Edge Highlighting
*   **The Consensus Path:** If an edge connects two **White Nodes**, it is rendered as a **thick, glowing line**. This visualizes the "Golden Path" where the group's shared interests flow uninterrupted.

### Node Interaction States (Active User Context)
The visual language extends beyond consensus color to reflect the Active User's relationship with each node.

**1. Pending Node**
*   **Condition:** The node exists in the shared graph, **no user has rejected it** (zero `false` flags), and the Active User has no local record of it.
*   **Purpose:** Signals "Inbox Work" or "Backlog." These are ideas collaborators value that you haven't validated yet.
*   **Visual:** **Rotating Dashed Border**. Rendered in the color of the *other* interested users.
*   **Why:** The dashed line suggests "incompleteness" awaiting a signature. If even one person rejects an idea, it is removed from the Pending queue to save group time (Veto power).

**2. Deprioritized Node**
*   **Condition:** **The Active User** OR **Any Other User** has explicitly flagged this node as `interested: false`.
*   **Purpose:** Maintains group context without cluttering the map. If *anyone* rejects an idea, it is "tainted" and visually deemphasized for everyone.
*   **Visual:** **Translucent (30% Opacity)**, Reduced Scale (0.6x).
*   **Why:** "Fading into the background" signals that this path is blocked or controversial, preventing wasted effort.

**3. Dead Node**
*   **Condition:** The aggregated list of `interested_users` is empty (0 users) and at least one user has explicitly flagged this node as `interested: false`.
*   **Purpose:** Automatic garbage collection for universally rejected ideas.
*   **Visual:** **Hidden (Not Rendered)**.
*   **Why:** If no one advocates for an idea, it should not consume cognitive load.

**4. Consensus Node**
*   **Condition:** All users (Alex + Sasha + Alison) are interested.
*   **Purpose:** The "Golden Path"—high value targets for Deep Drilling.
*   **Visual:** **Pure White Fill**, Largest Scale, Glowing Effect.
*   **Why:** White is the additive sum of all RGB colors, providing a high-contrast visual anchor.

**Toggles**
*  **Show Dead Nodes**: Option to reveal universally rejected ideas for auditing purposes.

---

## 3. System Architecture

### 3.0 Multi-Project Support
The system supports multiple isolated projects, each with its own graph, users, node types, and git repository.

**Project Structure:**
```
db/
  {project-name}/
    .git/           # Separate git repository per project
    data/           # User state files
      Alex.json
      Sasha.json
    nodes/          # Node files (ideas)
      {uuid}.json
    node_types/     # Project-specific node types and prompts
      default/
        definition.json
        drill_down.md
      game_concept/
        definition.json
        drill_down.md
  {another-project}/
    .git/
    data/
    nodes/
    node_types/
```

**Project Features:**
*   **Isolation:** Projects are completely independent - no shared data or users.
*   **Switching:** Users can switch between projects via the Project dropdown in the header.
*   **Creation:** New projects are created via a modal dialog requiring:
    *   Project name (becomes folder name)
    *   Initial username
    *   Root node label and optional description
*   **Git:** Each project initializes its own git repository for collaboration.

**First-Time Setup:**
If no projects exist, the application shows a welcome screen prompting the user to create their first project.

### 3.1 Data Persistence (Conflict-Free Multi-File Model)
The system uses a normalized data architecture with **file-per-node storage** to eliminate merge conflicts during concurrent idea creation.

**1. Node Files (`db/{project}/nodes/{uuid}.json`)**
Each idea is stored as an individual file, enabling conflict-free concurrent creation.
*   **Scope:** One file per node, shared by all users within the project.
*   **Benefit:** Two users adding nodes simultaneously create two separate files — **zero merge conflicts**.
*   **Schema:**
    ```json
    {
      "id": "uuid_v4",
      "label": "Serious Games",
      "parent_id": "root_uuid",
      "description": "Optional markdown description"
    }
    ```

**2. User State Files (`db/{project}/data/{user}.json`)**
Stores the specific relationship between a user and the nodes.
*   **Scope:** One file per user within the project (e.g., `Alex.json`, `Sasha.json`).
*   **Content:** "Votes", Metadata, and Interest flags.
*   **Schema:**
    ```json
    {
      "user_id": "Alex",
      "nodes": {
        "uuid_v4": {
          "interested": true,       // Vote: True (Accept), False (Reject), Missing (Pending)
          "metadata": "My notes..." // Private/Public context
        }
      }
    }
    ```

**4. Runtime Composition**
On startup or refresh, the system performs a **Join Operation**:
`Graph = All Node Files + (join) All User Files`
*   **Interested Users List:** derived dynamically by checking which users have `interested: true` for a given UUID.
*   **Pending Status:** derived if a Node exists but is missing from the Active User's file.

### 3.2 Collaboration & Git Automations
The tool handles Git operations semi-automatically to ensure users are always looking at the latest map.

1.  **Auto-Sync on Launch:** Upon opening the tool, it attempts a `git pull --rebase`.
    *   *Success:* The latest data is loaded.
    *   *Conflict:* Extremely rare due to file-per-node architecture.
2.  **Edit & Push:** Users work locally.
3.  **Post-Session Prompt:** After a "Drilling Session" is marked complete, the tool prompts: *"You have made changes. Push to team?"*

### 3.3 Atomic Updates & Synchronization
The multi-file architecture makes synchronization conflicts nearly impossible.

*   **New Idea Creation:** Creates a new file in `db/{project}/nodes/`. Two users adding ideas simultaneously create separate files — **zero merge conflicts**.
*   **Structural Edits (Rename/Move):** Updates the individual node file. Conflicts only possible if two users edit the *same* node simultaneously (rare).
*   **State Edits (Vote/Note):** Update `user.json`. Since users only write to their own file, **Merge Conflicts are impossible** for voting operations.
*   **The "Mutation Ledger":** (Deprecated) The previous complex event-sourcing ledger has been removed in favor of this normalized architecture.

### 3.4 Portability & Templating (Import/Export)
The system supports converting the complex UUID-bound graph into generic Project Templates.

*   **Export to Template:** Converts the Graph into a **Label Tree** (Nested JSON structure), stripping all UUIDs and User Data.
    *   *Result:* A clean, shareable file representing just the ideas hierarchy.
*   **Import from Template:** Ingests a Label Tree, generates **Fresh UUIDs**, and seeds new node files in `db/{project}/nodes/`.
    *   *Use Case:* "Cloning" a successful brainstorming structure to start a new project with a clean slate.

### 3.5 Shared Data Editing Rules
These rules govern how users can modify nodes in a collaborative project. They apply to **both Git and Supabase backends**.

**Principle:** Protect other users' contributions while allowing free editing of personal work.

**Rule 1: Unencumbered Nodes (Free Editing)**
*   **Condition:** A node has **no external user data** attached—only the active user has interacted with it (voted, added notes, etc.).
*   **Permissions:** The active user can freely:
    *   Rename the node (change label)
    *   Edit the description
    *   Delete the node entirely
    *   Change the parent (move in hierarchy)
    *   Modify any node properties
*   **Rationale:** If you're the only person who has touched a node, your edits affect no one else.

**Rule 2: Encumbered Nodes (Protected Editing)**
*   **Condition:** A node has **external user data** attached—at least one other user has:
    *   Voted on it (interested: true or false)
    *   Added metadata/notes to it
    *   Created child nodes under it
*   **Restrictions:**
    *   **Cannot Delete:** The delete action is blocked entirely.
    *   **Edit Warning:** When attempting to modify any node property (label, description, parent, etc.), the system displays a confirmation dialog:
        ```
        ⚠️ This change will affect other users
        
        The following users have data connected to this node:
        • Alex (voted: interested, has notes)
        • Sasha (voted: not interested)
        
        Are you sure you want to proceed?
        [Cancel] [Proceed Anyway]
        ```
    *   **Audit Trail:** If the user proceeds, the change is logged with timestamp and modifier identity.
*   **Rationale:** Other users have invested cognitive effort into this node. Deleting it would erase their votes and notes. Renaming it might invalidate their understanding. They deserve a heads-up.

**Edge Cases:**
*   **Rejected-Only Nodes:** If all external users have `interested: false` (rejected), the node is still protected—rejection is valid user data.
*   **Pending Nodes:** Nodes that exist but have no votes from anyone are considered unencumbered and freely editable by anyone.
*   **Child Node Dependency:** If deleting a node would orphan child nodes that have external user data, the deletion is blocked with a message explaining the dependency chain.

**UI Implementation:**
*   The **Delete** button is disabled (grayed out) for encumbered nodes, with a tooltip: "Cannot delete: other users have data on this node"
*   The **Edit** actions show the warning modal before applying changes
*   The node detail panel displays an "Affected Users" badge when viewing encumbered nodes

---

## 4. The Workflows

### Workflow A: The Ingestion Workchain (CSV to Graph)
This routine converts raw brainstorming (CSV) into structured graph nodes. It is **idempotent** (safe to run multiple times).

1.  **Input:** User uploads `ideas.csv` (Columns: User A, User B, User C).
2.  **AI Abstraction:** The AI reads the raw text rows. It does not simply copy-paste; it:
    *   **Abstracts** concepts into clean Subject Labels (e.g., "Serious Games" -> "Protein Folding").
    *   **Retains** the original text as `metadata` (context for future generation).
3.  **Deduplication & Merge:**
    *   The system generates a unique ID for each label.
    *   **If Node Exists:** It *appends* the new user to the `interested_users` list and appends new notes to `metadata`. **Existing child links are preserved.**
    *   **If Node is New:** It creates the node and links it to the Root.
4.  **Result:** The graph grows; no work is lost.

### Workflow B: The Review Queue (Global Maintenance)
The "Inbox Zero" workflow. Users click a global **"Review Pending"** button to check ideas proposed by others or by the AI in previous sessions.

1.  **Trigger:** Global action button (badge shows count of Pending Nodes).
2.  **Interaction:** **Card Stack Mode (One-by-One)**.
3.  **Process:**
    *   System serves sequential "Pending" nodes (unvoted, unrejected).
    *   **Display:** Label + Metadata/Notes from other users.
    *   **Action:**
        *   **Accept:** Added to user's file.
        *   **Reject:** Marked `interested: false`. Node is removed from everyone's pending queue (Deprioritized).
        *   **Skip:** Returns to queue.

### Workflow C: The Drill Loop (Expansion)
The generative process. This is now purely about **expanding** the graph, not reviewing existing nodes.

1.  **Select:** User enters a drilling session on a specific node (must be a Consensus Node or own node).
2.  **Phase 1: AI Generation (Rapid Triage):**
    *   *Context:* Fresh ideas generated by the AI to branch off the selected topic.
    *   *Interaction:* **Tri-State List Mode.**
    *   *Action:* User reviews a list of $N$ items with three states:
        *   ✅ **Check (Agree):** Becomes a pending node for others; Accepted for self.
        *   ❌ **Cross (Decline):** Explicitly rejected (added to history so AI doesn't repeat).
        *   ⬜ **Empty (Ignore):** No strong opinion; recycled for later but NOT added to rejection history.
3.  **Phase 2: Commit:**
    *   The user commits the session. Accepted items become **Pending Nodes** for other users.
4.  **Consensus Resolution:**
    *   New nodes start as "Red/Blue/Green" (Shared but Pending).
    *   They only become White once all users have run **Workflow B** and accepted them.

### Workflow D: Manual Node Editing
Users can directly manipulate the graph structure through visual interactions when the Ctrl key is held.

**Activation:** Hold **Ctrl** key to enter manual edit mode.

**Visual Feedback:**
*   Semi-transparent preview nodes and dashed edges appear to show what action will occur
*   Preview elements use the active user's RGB color
*   Edge hover detection highlights edges in different colors based on action type

**Editing Actions:**

1.  **Create New Node:**
    *   **Trigger:** Ctrl + Click on empty space
    *   **Behavior:** Creates a new node labeled "New Idea" at click position
    *   **Auto-Connect:** If clicking near an existing node (within its visual radius), automatically creates a parent-child connection
    *   **Vote:** Automatically votes "interested" for the active user

2.  **Create Intermediary Node on Edge:**
    *   **Trigger:** Ctrl + Click on middle 20% of an edge
    *   **Behavior:** Creates a new node between two connected nodes
    *   **Label:** Automatically named "{Source}→{Target}"
    *   **Structure:** Breaks edge A→B into A→New→B
    *   **Vote:** Automatically votes "interested" for the active user

3.  **Cut Edge:**
    *   **Trigger:** Ctrl + Click outside middle 20% of an edge (edge highlights red)
    *   **Behavior:** Removes parent-child relationship
    *   **Visual Preview:** Edge appears red while hovering

4.  **Drag Node to Make Intermediary:**
    *   **Trigger:** Ctrl + Drag existing node over middle of an edge
    *   **Behavior:** Inserts the dragged node between the edge's source and target
    *   **Preservation:** Other connections to the dragged node are preserved
    *   **Priority:** Takes precedence over "connect nodes" action

5.  **Drag Node to Connect:**
    *   **Trigger:** Ctrl + Drag node near another node (within connection radius)
    *   **Behavior:** Creates parent-child relationship
    *   **Preservation:** Existing connections are maintained

### Workflow E: Manual Maintenance
*   **Edit Node:** Users can manually rename nodes or add metadata/context text. This is crucial for guiding the AI in future "Drill Downs."
*   **Pruning:** Users can manually delete nodes they created, provided they have not yet been pushed to the shared remote. Shared nodes must be handled via a "Propose Deletion" mutation.
*   **Linking:** Users can manually draw edges between orphan nodes to clean up the graph structure via Ctrl+Drag interactions.

---

## 5. User Interface Specifications

### Unified Single-View Interface
The application abandons separate tabs in favor of a modern, map-centric interface.

*   **Main Canvas:** Infinite, zoomable, pannable graph area.
*   **Global Controls:** Floating header containing:
    *   User Selector.
    *   **Review Pending** button (with counter badge).
    *   **Show/Hide Dead Nodes** toggle.
*   **Visuals:** Nodes rendered with the RGB consensus color. "Pending" nodes use moving dashed borders.

### The Context Window (Floating Overlay)
When a user clicks a node, a floating panel appears (or slides in) containing all interaction tools for that specific idea.

1.  **Node Data (Editable):**
    *   **Label:** Rename the node.
    *   **Metadata:** Edit raw notes/context (Markdown supported).
    *   **Status display:** "Interested Users: Alex, Sasha".

2.  **The Drilling Engine (Expansion):**
    *   **Mode:** AI Generation (Tri-State List).
    *   **UI:** Vertical list of candidates.
    *   **Controls:** Each item has [✅ Accept] [❌ Reject] [⬜ Ignore].

3.  **Prompt Button Management:**
    *   **Edit Existing Prompts:** Hover over any action button to reveal a small circular pencil icon at the top-right corner. Click to open the prompt editor.
    *   **Create New Prompts:** Click the circular "+" button next to the action buttons to create a new prompt for this node type.
    *   **Prompt Editor Modal:** Opens a full-screen modal with:
        *   **Name Field:** Large editable header-style input for the prompt display name.
        *   **Description Field:** Single-line text input for the tooltip description.
        *   **Icon Picker:** Searchable dropdown with icon preview for selecting Material Design icons.
        *   **Produces Type Dropdown:** Select which node type this prompt generates (from existing types).
        *   **Body Editor:** Markdown textarea for the prompt content. Use placeholders like `{label}`, `{description}`, `{metadata}`, `{votes}`, `{approved_children}`, `{rejected_children}`, `{children}`, `{output_schema}`.
    *   **Save/Cancel/Delete:** Save persists changes to the `.md` file in the node type folder. Delete immediately removes the prompt file (no confirmation).
    *   **Auto-Refresh:** Prompt buttons automatically refresh after save/delete operations.

4.  **Graph Actions:**
    *   **"Prune":** Delete node (only if created locally and unpushed).
    *   **"Connect":** Draw edge to another node.

---

## 6. Implementation Stack
*   **Language:** Python 3.9+
*   **Application Framework:** NiceGUI.
    *   *Architecture:* Unified Python framework. Runs locally (Localhost) and simply uses the browser as the display window.
    *   *Benefit:* Eliminates frontend-backend synchronization complexity.
*   **Graph Engine:** NetworkX (Logic) + Apache ECharts (via `ui.echart`).
    *   *Why:* Native NiceGUI element. Highly performant, handles thousands of nodes, supports physics engines (force-directed), and accepts Python dictionaries as configuration.
*   **AI Engine:** OpenAI API (GPT-4o) for structuring CSVs and generating sub-concepts.
*   **Version Control:** Git (local backend) or Supabase (cloud backend).

---

## 7. Supabase Cloud Backend (Optional)

### 7.0 Overview
The system supports two storage backends per project:
1. **Git Backend (Default):** Local file storage with git sync — the current implementation.
2. **Supabase Backend (Optional):** Cloud-hosted PostgreSQL with real-time sync, authentication, and public project URLs.

Projects can choose their backend at creation time. The choice affects:
- How data is stored and synchronized
- Whether authentication is required
- Whether the project can be publicly accessible via URL

### 7.1 Architecture: Dual Backend Pattern

**Abstract Interface (`StorageBackend` Protocol):**
```
┌─────────────────────────────────────────────────────────┐
│                    StorageBackend                        │
│                   (Abstract Protocol)                    │
├─────────────────────────────────────────────────────────┤
│  get_graph() -> Dict                                    │
│  save_node(node_id, data) -> None                       │
│  delete_node(node_id) -> None                           │
│  load_user(user_id) -> Dict                             │
│  save_user(data) -> None                                │
│  list_users() -> List[str]                              │
│  sync() -> None  # Pull latest (git pull / realtime)    │
│  push() -> None  # Push changes (git push / no-op)      │
│  subscribe(callback) -> None  # Real-time updates       │
└─────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌───────────────────┐            ┌────────────────────────┐
│    GitBackend     │            │   SupabaseBackend      │
│    (Current)      │            │   (New)                │
├───────────────────┤            ├────────────────────────┤
│ - File I/O        │            │ - REST API calls       │
│ - git pull/push   │            │ - Supabase Realtime    │
│ - Local storage   │            │ - PostgreSQL storage   │
│ - No auth required│            │ - JWT authentication   │
└───────────────────┘            └────────────────────────┘
```

**Project Configuration (`db/{project}/config.json`):**
```json
{
  "storage_backend": "supabase",
  "supabase_project_url": "https://abc123.supabase.co",
  "supabase_anon_key": "eyJ...",
  "supabase_project_id": "uuid-of-project-in-supabase",
  "is_public": true
}
```

For git-based projects, `config.json` is optional or contains:
```json
{
  "storage_backend": "git"
}
```

### 7.2 Supabase Database Schema

**Tables:**

```sql
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

-- Indexes for performance
CREATE INDEX idx_nodes_project ON public.nodes(project_id);
CREATE INDEX idx_nodes_parent ON public.nodes(parent_id);
CREATE INDEX idx_votes_node ON public.user_node_votes(node_id);
CREATE INDEX idx_votes_user ON public.user_node_votes(user_id);
CREATE INDEX idx_projects_slug ON public.projects(slug);
CREATE INDEX idx_projects_public ON public.projects(is_public) WHERE is_public = TRUE;
```

### 7.3 Row Level Security (RLS) Policies

```sql
-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_node_votes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.node_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.prompts ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can read all, update only their own
CREATE POLICY "Profiles are viewable by everyone" ON public.profiles
    FOR SELECT USING (true);
CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- Projects: Public projects readable by all, private by members only
CREATE POLICY "Public projects are viewable by everyone" ON public.projects
    FOR SELECT USING (is_public = TRUE);
CREATE POLICY "Members can view their projects" ON public.projects
    FOR SELECT USING (
        id IN (SELECT project_id FROM public.project_members WHERE user_id = auth.uid())
    );
CREATE POLICY "Members can update their projects" ON public.projects
    FOR UPDATE USING (
        id IN (SELECT project_id FROM public.project_members WHERE user_id = auth.uid() AND role IN ('owner', 'admin'))
    );
CREATE POLICY "Authenticated users can create projects" ON public.projects
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- Nodes: Readable if project is public OR user is member, writable by members only
CREATE POLICY "Nodes readable on public projects" ON public.nodes
    FOR SELECT USING (
        project_id IN (SELECT id FROM public.projects WHERE is_public = TRUE)
    );
CREATE POLICY "Nodes readable by project members" ON public.nodes
    FOR SELECT USING (
        project_id IN (SELECT project_id FROM public.project_members WHERE user_id = auth.uid())
    );
CREATE POLICY "Nodes writable by project members" ON public.nodes
    FOR ALL USING (
        project_id IN (SELECT project_id FROM public.project_members WHERE user_id = auth.uid())
    );

-- Votes: Users can only manage their own votes
CREATE POLICY "Users can view all votes on accessible nodes" ON public.user_node_votes
    FOR SELECT USING (
        node_id IN (
            SELECT id FROM public.nodes WHERE project_id IN (
                SELECT id FROM public.projects WHERE is_public = TRUE
                UNION
                SELECT project_id FROM public.project_members WHERE user_id = auth.uid()
            )
        )
    );
CREATE POLICY "Users can manage only their own votes" ON public.user_node_votes
    FOR ALL USING (auth.uid() = user_id);

-- Node types and prompts: Same access as nodes
CREATE POLICY "Node types readable on accessible projects" ON public.node_types
    FOR SELECT USING (
        project_id IN (
            SELECT id FROM public.projects WHERE is_public = TRUE
            UNION
            SELECT project_id FROM public.project_members WHERE user_id = auth.uid()
        )
    );
CREATE POLICY "Node types writable by members" ON public.node_types
    FOR ALL USING (
        project_id IN (SELECT project_id FROM public.project_members WHERE user_id = auth.uid())
    );

CREATE POLICY "Prompts readable via node_type access" ON public.prompts
    FOR SELECT USING (
        node_type_id IN (SELECT id FROM public.node_types)  -- Inherits from node_types policy
    );
CREATE POLICY "Prompts writable via node_type access" ON public.prompts
    FOR ALL USING (
        node_type_id IN (
            SELECT id FROM public.node_types WHERE project_id IN (
                SELECT project_id FROM public.project_members WHERE user_id = auth.uid()
            )
        )
    );
```

### 7.4 Real-Time Synchronization

**Supabase Realtime Subscriptions:**
```python
# Subscribe to node changes for a project
channel = supabase.channel(f'project:{project_id}')
channel.on_postgres_changes(
    event='*',
    schema='public',
    table='nodes',
    filter=f'project_id=eq.{project_id}',
    callback=on_node_change
).on_postgres_changes(
    event='*',
    schema='public',
    table='user_node_votes',
    callback=on_vote_change
).subscribe()
```

**Event Handling:**
- `INSERT` on nodes → Add node to local graph, trigger UI refresh
- `UPDATE` on nodes → Update node properties, re-render
- `DELETE` on nodes → Remove from graph
- `INSERT/UPDATE` on votes → Recalculate interested_users, update node color

**Conflict Resolution:**
- **Last-Write-Wins** for node properties (label, description)
- **No conflicts** for votes (each user writes only their own row)
- `updated_at` timestamp used for optimistic locking if needed

### 7.5 Authentication System

**Auth Flow:**

```
┌─────────────────────────────────────────────────────────┐
│                    Application Start                     │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  Check Storage Backend │
              │  for current project   │
              └───────────┬───────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
   ┌─────────────┐                ┌─────────────────┐
   │ Git Backend │                │ Supabase Backend │
   └──────┬──────┘                └────────┬────────┘
          │                                │
          ▼                                ▼
   ┌─────────────┐                ┌─────────────────┐
   │ Show User   │                │ Check Session   │
   │ Dropdown    │                │ (JWT Cookie)    │
   │ (No Auth)   │                └────────┬────────┘
   └─────────────┘                         │
                               ┌───────────┴───────────┐
                               ▼                       ▼
                        ┌─────────────┐         ┌─────────────┐
                        │ Logged In   │         │ Not Logged  │
                        │ Show App    │         │ In          │
                        └─────────────┘         └──────┬──────┘
                                                       │
                                            ┌──────────┴──────────┐
                                            ▼                     ▼
                                     ┌─────────────┐       ┌─────────────┐
                                     │ Public URL? │       │ Private URL │
                                     │ /public/*   │       │ /project/*  │
                                     └──────┬──────┘       └──────┬──────┘
                                            │                     │
                                            ▼                     ▼
                                     ┌─────────────┐       ┌─────────────┐
                                     │ Read-Only   │       │ Redirect to │
                                     │ View        │       │ /login      │
                                     └─────────────┘       └─────────────┘
```

**NiceGUI Pages:**

| Route | Auth Required | Purpose |
|-------|---------------|---------|
| `/` | No | Landing page / project selector |
| `/login` | No | Email/password login form |
| `/register` | No | New user registration |
| `/logout` | Yes | Clear session, redirect to `/` |
| `/project/{slug}` | Yes | Full editing access to project |
| `/public/{slug}` | No | Read-only view of public project |
| `/settings` | Yes | User profile settings |

**Session Management:**
- Supabase JWT stored in HTTP-only cookie
- NiceGUI middleware checks session on protected routes
- Auto-refresh tokens before expiry

### 7.6 UI Adaptations by Backend

The interface dynamically adapts based on the storage backend:

**Header Controls:**

| Component | Git Backend | Supabase Backend |
|-----------|-------------|------------------|
| User Identity | Dropdown selector (local users) | Logged-in user display + logout button |
| Sync Button | "Pull" / "Push" buttons | Hidden (real-time sync) |
| Sync Status | "Last pulled: 5m ago" | "Live" indicator (green dot) |
| Project Sharing | "Copy git URL" | "Share link" + visibility toggle |

**Project Creation Dialog:**

| Field | Git Backend | Supabase Backend |
|-------|-------------|------------------|
| Project Name | ✓ | ✓ |
| Initial Username | ✓ (creates local file) | ✗ (uses logged-in user) |
| Root Node | ✓ | ✓ |
| Git Remote URL | Optional | ✗ |
| Make Public | ✗ | ✓ (checkbox) |
| Invite Members | ✗ | ✓ (email input) |

**Node Editing Panel:**

| Feature | Git Backend | Supabase Backend (Read-Only) | Supabase Backend (Member) |
|---------|-------------|------------------------------|---------------------------|
| Edit Label | ✓ | ✗ | ✓ |
| Edit Description | ✓ | ✗ | ✓ |
| Vote (Accept/Reject) | ✓ | ✗ | ✓ |
| Drill Down | ✓ | ✗ | ✓ |
| Delete Node | ✓ | ✗ | ✓ |
| Login Prompt | ✗ | ✓ "Login to contribute" | ✗ |

**Visual Indicators:**

| Indicator | Git Backend | Supabase Backend |
|-----------|-------------|------------------|
| Unsaved Changes | Yellow dot | N/A (auto-save) |
| Sync Pending | "Push to team?" prompt | N/A (real-time) |
| Other Users Active | Not shown | Colored cursors on canvas (future) |
| Connection Status | Git remote status | WebSocket status (connected/reconnecting) |

### 7.7 Public Project Access

**URL Structure:**
```
https://your-domain.com/public/{project-slug}
```

**Read-Only Mode Features:**
- Full graph visualization with zoom/pan
- Node selection shows details (label, description, interested users)
- Color-coded consensus visualization
- **No** editing capabilities
- **No** voting capabilities
- Prominent "Login to contribute" call-to-action

**Login-to-Edit Flow:**
1. Anonymous user views `/public/my-project`
2. Clicks "Login to contribute"
3. Redirected to `/login?redirect=/project/my-project`
4. After login, redirected to `/project/my-project` with full access
5. If not already a member, prompted to "Request access" or auto-joined if project allows

### 7.8 Implementation Phases

**Phase 1: Storage Backend Abstraction (Foundation)** ✅ COMPLETE
- [x] Define `StorageBackend` protocol in `src/storage/protocol.py`
- [x] Create `GitBackend` class extracting current `DataManager` logic
- [x] Create `BackendFactory` to instantiate correct backend from config
- [x] Refactor `DataManager` to delegate to backend instance
- [x] Add `config.json` support per project
- [x] Update `ProjectManager` to handle backend selection

**Files created:**
```
src/
  storage/
    __init__.py
    protocol.py         # StorageBackend Protocol definition
    git_backend.py      # Current logic extracted
    supabase_backend.py # New Supabase implementation
    factory.py          # Backend instantiation
```

**Phase 2: Supabase Backend Implementation** ✅ COMPLETE
- [x] Add `supabase-py` to requirements.txt
- [x] Implement `SupabaseBackend` class
- [x] Implement node CRUD operations via Supabase API
- [x] Implement user vote operations
- [x] Implement node type and prompt sync
- [x] Add connection pooling and error handling

**Phase 3: Authentication System** ✅ COMPLETE
- [x] Create `/login` page with email/password form
- [x] Create `/register` page
- [x] Implement session middleware for protected routes
- [x] Add logout functionality
- [x] Update header to show logged-in user
- [x] Add "Login to contribute" prompts for public views

**Files created:**
```
src/
  auth/
    __init__.py
    middleware.py       # Session checking
    pages.py            # Login/register UI
    session.py          # JWT/cookie management
```

**Phase 4: Real-Time Sync** ✅ COMPLETE
- [x] Implement Supabase Realtime subscription manager
- [x] Handle INSERT/UPDATE/DELETE events for nodes
- [x] Handle vote change events
- [x] Implement optimistic UI updates
- [x] Add reconnection logic for dropped WebSocket
- [x] Add "Live" status indicator in header

**Files created:**
```
src/
  realtime_sync.py      # RealtimeSyncManager and NiceGUI adapter
```

**Phase 5: Public Project Routes** ✅ COMPLETE
- [x] Create `/public/{slug}` route
- [x] Implement read-only graph view
- [x] Disable all edit controls in read-only mode
- [x] Add "Login to contribute" CTA
- [x] Implement login redirect flow with return URL

**Files created:**
```
src/
  public_routes.py      # PublicProjectView and route handlers
```

**Phase 6: UI Adaptation Layer** ✅ COMPLETE
- [x] Create `UIContext` class with backend-aware feature flags
- [x] Conditionally render sync buttons (git only)
- [x] Conditionally render user dropdown vs login status
- [x] Update project creation modal with backend-specific fields
- [x] Add project visibility toggle for Supabase projects

**Files created:**
```
src/
  ui_adapter.py         # UIContext, AdaptiveHeader, AdaptiveNodePanel
```

**Phase 7: Migration & Testing** ✅ COMPLETE
- [x] Create migration tool: local project → Supabase
- [x] Create export tool: Supabase project → local files
- [x] Write unit tests for both backends
- [x] Write integration tests for auth flow
- [x] Write E2E tests for public project access
- [ ] Performance testing with large graphs (manual testing recommended)

**Files created:**
```
src/
  migration.py          # GitToSupabaseMigrator, SupabaseToGitMigrator

tests/
  test_storage_backends.py  # GitBackend and SupabaseBackend tests
  test_auth.py              # Authentication flow tests
  test_public_routes.py     # Public route and read-only tests
  test_migration.py         # Migration tool tests
```

### 7.9 Environment Configuration

**New Environment Variables (`.env`):**
```bash
# Supabase Configuration (optional, for cloud projects)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # For admin operations

# Auth Settings
SESSION_SECRET=your-random-secret-key
SESSION_EXPIRY_HOURS=168  # 7 days

# Feature Flags
ENABLE_SUPABASE=true
ENABLE_PUBLIC_PROJECTS=true
```

### 7.10 Error Handling & Offline Support

**Network Failure Handling:**
- Queue failed operations locally
- Retry with exponential backoff
- Show "Offline" indicator in header
- Prevent destructive actions while offline

**Conflict Detection:**
- Compare `updated_at` before writes
- If conflict detected, show diff UI
- Allow user to choose: "Keep mine" / "Keep theirs" / "Merge"

**Graceful Degradation:**
- If Supabase unreachable, show cached data
- Disable write operations until reconnected
- Log all errors for debugging