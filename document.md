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

### 3.1 Data Persistence (Conflict-Free Multi-File Model)
The system uses a normalized data architecture with **file-per-node storage** to eliminate merge conflicts during concurrent idea creation.

**1. Node Files (`db/nodes/{uuid}.json`)**
Each idea is stored as an individual file, enabling conflict-free concurrent creation.
*   **Scope:** One file per node, shared by all users.
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

**2. Global Metadata (`db/global.json`)**
Stores non-node configuration and UI state.
*   **Scope:** Shared by all users.
*   **Content:** UI preferences, hidden users, layout positions.
*   **Schema:**
    ```json
    {
      "hidden_users": ["Alison", "Kevin"],
      "positions": {
        "uuid_v4": [0.5, 0.3]
      }
    }
    ```

**3. User State Files (`db/data/{user}.json`)**
Stores the specific relationship between a user and the nodes.
*   **Scope:** One file per user (e.g., `Alex.json`, `Sasha.json`).
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

*   **New Idea Creation:** Creates a new file in `db/nodes/`. Two users adding ideas simultaneously create separate files — **zero merge conflicts**.
*   **Structural Edits (Rename/Move):** Updates the individual node file. Conflicts only possible if two users edit the *same* node simultaneously (rare).
*   **State Edits (Vote/Note):** Update `user.json`. Since users only write to their own file, **Merge Conflicts are impossible** for voting operations.
*   **The "Mutation Ledger":** (Deprecated) The previous complex event-sourcing ledger has been removed in favor of this normalized architecture.

### 3.4 Portability & Templating (Import/Export)
The system supports converting the complex UUID-bound graph into generic Project Templates.

*   **Export to Template:** Converts the Graph into a **Label Tree** (Nested JSON structure), stripping all UUIDs and User Data.
    *   *Result:* A clean, shareable file representing just the ideas hierarchy.
*   **Import from Template:** Ingests a Label Tree, generates **Fresh UUIDs**, and seeds a new `global.json`.
    *   *Use Case:* "Cloning" a successful brainstorming structure to start a new project with a clean slate.

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

**Position Persistence:**
*   Node positions are automatically saved to `db/global.json` in the `positions` field
*   Positions use normalized coordinates [0,1] range
*   Manual layouts survive application restarts
*   Position conflicts in git are resolved via last-write-wins (rare due to infrequent structural edits)

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

3.  **Graph Actions:**
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
*   **Version Control:** Git.