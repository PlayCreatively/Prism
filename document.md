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
*   **Standard Edge:** Thin gray line.
*   **The Consensus Path:** If an edge connects two **White Nodes**, it is rendered as a **thick, glowing line**. This visualizes the "Golden Path" where the group's shared interests flow uninterrupted.

---

## 3. System Architecture

### 3.1 Data Persistence (User-Partitioned Storage)
To prevent Git merge conflicts and allow for full data portability, the system does not use a single shared database. Instead, each user has their own dedicated JSON file (e.g., `data/alex.json`, `data/sasha.json`).

*   **Runtime Aggregation:** On startup, the system reads all JSON files in the `data/` directory and merges them into a single in-memory graph.
*   **Conflict Avoidance & Write Access:** While data is partitioned by user for consensus tracking (`data/alex.json`, `data/sasha.json`), the **application instance has write-access to all local data files**. This allows for bulk imports (Ingestion Workflow) and synchronized updates. However, during standard consensus operations, users primarily append to their own file to minimize Git conflicts.
*   **Data Resilience:** By storing the full node definition with every vote, the system ensures that if a user leaves (deletes their file), the nodes they created **survive** if anyone else has voted "Yes" on them.

**Node Schema (Unified):**
Each user's file contains a flat list of every node they have interacted with, plus a log of mutations they have already applied.
```json
{
  "user_id": "Alex",
  "applied_mutations": ["hash_1", "hash_2"], // The "Cursor" linking State to Git History
  "nodes": [
    {
      "id": "uuid_v4", // Random UUID. Labels must be unique across the graph.
      "label": "Serious Games",
      "parent_id": "root_node_id", 
      "status": "accepted", // Options: "accepted" (Yes), "rejected" (No), "pending"
      "metadata": "**Markdown** notes allowed here..."
    }
  ]
}
```
*Note: Rejected ideas are simply nodes with `status: "rejected"`. This provides a permanent distributed history of bad ideas.*

### 3.2 Collaboration & Git Automations
The tool handles Git operations semi-automatically to ensure users are always looking at the latest map.

1.  **Auto-Sync on Launch:** Upon opening the tool, it attempts a `git pull --rebase`.
    *   *Success:* The latest data is loaded.
    *   *Conflict:* The system alerts the user to resolve conflicts manually in the terminal/VS Code (rare, given the file separation).
2.  **Edit & Push:** Users work locally.
3.  **Post-Session Prompt:** After a "Drilling Session" is marked complete, the tool prompts: *"You have made changes. Push to team?"*
    *   If confirmed, the tool runs `git add .`, `git commit -m "Update by [User]"`, and `git push`.

### 3.3 Data Mutation Strategy (The "Change Ledger")
Since nodes are duplicated across multiple user files for resilience, we need a way to propagate edits (Context 1: "I fixed a typo") and deletions (Context 2: "We all agreed to delete this").

**The Approach:**
We use a **Command-Based Mutation Ledger** instead of relying purely on state merging. This is similar to a database transaction log or Redux actions.

**Mechanism:**
1.  **The `mutations/` Directory:** A folder tracked by Git.
2.  **Action:** When a user modifies a shared node (Rename/Delete), the system does **not** assume the other users will see it instantly. It generates a mutation file:
    ```json
    // mutations/2026-01-14T1200_alex_rename_uuid.json
    {
      "timestamp": "2026-01-14T12:00:00Z",
      "author": "Alex",
      "node_id": "uuid_of_node",
      "action": "UPDATE_LABEL", // or "DELETE_NODE"
      "payload": "New Label Name"
    }
    ```
3.  **Propagation:**
    *   User A creates the mutation and pushes.
    *   User B pulls.
    *   User B's client detects a new file in `mutations/`.
    *   **The Patching Process:** The client reads the mutation and *applies* the change to `sasha.json` (e.g., updating the label text or removing the node entry).
    *   *Result:* `sasha.json` stays self-contained and up-to-date.

**Addressing Edge Cases (The "State-Linked" Cursor):**
To ensure the system works seamlessly with Git history (branch switching, resets):
*   **Mechanism:** We do *not* use a local untracked log. Instead, the list of `applied_mutations` is stored **inside** each `user.json` file.
*   **Why this is better:**
    *   **Git Switch/Checkout:** If you switch to an old branch, your `user.json` reverts to its old state (without the mutation applied) AND the `mutations/` folder reverts (removing the mutation file). The system sees a perfect match; nothing breaks.
    *   **Git Reset:** If you hard reset to yesterday, your data file and your mutation history move backward in lockstep.
    *   **Git Revert:** To undo a mutation, you revert the commit that added it *and* the commit that updated your `user.json`. The system then sees the mutation effectively "never happened."

**Pros of this Approach:**
*   **Deletes work correctly:** Without a specific "Delete Command," if Alex deletes a node but Sasha has it, merging the two files would normally just make the node reappear (The "Zombie Node" problem). The Change File explicitly tells Sasha's computer "Remove this."
*   **Conflict Resolution:** If two people rename the same node, the `timestamp` determines the "Last Write Wins" winner mathematically.

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

### Workflow B: The Asynchronous Consensus Loop
The "Drill Down" process is designed for asynchronous collaboration, treating "Backlog" (human-generated or pending) ideas differently from "New" (AI-generated) batches.

**The Loop Logic:**
1.  **Select:** User enters a Drilling Session on a node (Glowing or Static).
2.  **Phase 1: The Backlog (Detailed Review):**
    *   *Context:* Existing ideas that others have voted "Yes" on but the current user hasn't seen.
    *   *Interaction:* **Card Stack Mode (One-by-One).**
    *   *Action:* For each card, the user sees the Label + Other Users' Notes.
        *   **Vote:** Yes / No.
        *   **Annotate:** User can add their own "Raw Notes" metadata before voting.
3.  **Phase 2: AI Generation (Rapid Triage):**
    *   *Context:* Fresh ideas generated by the AI to expand the map.
    *   *Interaction:* **Tri-State List Mode.**
    *   *Action:* User reviews a list of $N$ items with three states:
        *   ✅ **Check (Agree):** Becomes a candidate node.
        *   ❌ **Cross (Decline):** Explicitly rejected (added to history so AI doesn't repeat).
        *   ⬜ **Empty (Ignore):** No strong opinion; recycled for later but NOT added to rejection history.
4.  **Phase 3: Commit:**
    *   The user commits the session. Accepted items enter the backlog for other users. Rejected items are logged. Ignored items evaporate.
5.  **Consensus Resolution:**
    *   New nodes are only instantiated as **White Nodes** (Tertiary) if *all other users* have also independently voted "Yes" on them.
    *   Until then, they are **fully visible** on the shared graph, rendered in the creator's primary color (e.g., Red for Alex). Other users can click these nodes to enter a voting/drilling session.

### Workflow C: Manual Maintenance
*   **Edit Node:** Users can manually rename nodes or add metadata/context text. This is crucial for guiding the AI in future "Drill Downs."
*   **Pruning:** Users can manually delete nodes they created, provided they have not yet been pushed to the shared remote. Shared nodes must be handled via a "Propose Deletion" mutation.
*   **Linking:** Users can manually draw edges between orphan nodes to clean up the graph structure.

---

## 5. User Interface Specifications

### Unified Single-View Interface
The application abandons separate tabs in favor of a modern, map-centric interface.

*   **Main Canvas:** Infinite, zoomable, pannable graph area.
*   **Visuals:** Nodes rendered with the RGB consensus color. "Backlog" nodes emit a pulsing glow.

### The Context Window (Floating Overlay)
When a user clicks a node, a floating panel appears (or slides in) containing all interaction tools for that specific idea.

1.  **Node Data (Editable):**
    *   **Label:** Rename the node.
    *   **Metadata:** Edit raw notes/context (Markdown supported).
    *   **Status display:** "Interested Users: Alex, Sasha".

2.  **The Drilling Engine:**
    *   **Mode A: Backlog Review (Card Stack):**
        *   Used for existing ideas needing a vote.
        *   **UI:** Single Card view. Shows Label + Others' Notes.
        *   **Inputs:** Text area for your notes. Buttons: "Yes" / "No".
    *   **Mode B: AI Generation (Tri-State List):**
        *   Used for rapid filtering of new ideas.
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