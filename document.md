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

### 3.1 Data Persistence (`mindmap_state.json`)
The source of truth is a local JSON file managed via Git.
*   **Graph Structure:** Directed Acyclic Graph (DAG).
*   **Color Storage:** Colors are **not** stored in the database. They are rendered at runtime based on the `interested_users` array to prevent synchronization errors.

**Node Schema:**
```json
{
  "id": "uuid_v5_hash_of_label",
  "label": "Serious Games",
  "interested_users": ["Alex", "Sasha"], 
  "metadata": "Raw notes: protein folding, medical sim...", 
  "rejected_history": ["Bad Idea A", "Bad Idea B"], 
  "parent_id": "root_node_id"
}
```

### 3.2 Collaboration Workflow
To support asynchronous or synchronous work without complex server infrastructure:
1.  **Clone:** All users clone the repo containing the tool and the `.json` file.
2.  **Run & Edit:** Users run the tool locally to update the graph.
3.  **Sync:** Updates to the `.json` file are committed and pushed to GitHub.
4.  **Merge:** Other users pull the changes to see the updated map.

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

### Workflow B: The Consensus Loop (The "Drill Down")
This is a strict state-machine designed to force consensus before expanding the map. It is used to generate sub-subjects from a parent "White Node".

**The Loop Logic:**
1.  **Select:** Users select one **White Node** (Parent).
2.  **Generate:** The AI analyzes the Parent Node + Metadata and generates a batch of $N$ sub-subjects.
3.  **Gate 1 (Alex):**
    *   Alex reviews the batch.
    *   *Action:* Selects interesting items (Yes/No).
    *   *Failure Condition:* If Alex selects 0 items -> **Reset to Step 2** (Generate new batch).
4.  **Gate 2 (Sasha):**
    *   Sasha reviews *only* items Alex selected.
    *   *Failure Condition:* If Sasha selects 0 items -> **Reset to Step 2** (Generate new batch for Alex).
5.  **Gate 3 (Alison):**
    *   Alison reviews *only* items Sasha selected.
    *   *Failure Condition:* If Alison selects 0 items -> **Reset to Step 2** (Generate new batch for Alex).
6.  **Success:**
    *   Any item that passes Gate 3 is immediately instantiated as a new **White Node**.
    *   It is linked to the Parent Node.
    *   The loop can be exited or repeated.

*Note: The system maintains a `rejected_history` list for the parent node. If a batch is rejected, those specific ideas are added to the history so the AI never suggests them again.*

### Workflow C: Manual Maintenance
*   **Edit Node:** Users can manually rename nodes or add metadata/context text. This is crucial for guiding the AI in future "Drill Downs."
*   **Pruning:** Users can manually delete nodes.
*   **Linking:** Users can manually draw edges between orphan nodes to clean up the graph structure.

---

## 5. User Interface Specifications

### Tab 1: The Map (Visualization)
*   **Main View:** Interactive graph (zoomable/pannable).
*   **Visuals:** Circles (Nodes) connected by lines (Edges).
*   **Legend:** Minimal RGB reference.
*   **Interaction:** Clicking a node reveals a sidebar with:
    *   Full Label.
    *   Interested Users (Checkboxes).
    *   Context/Metadata (Editable Text Area).

### Tab 2: The Drill (Consensus Engine)
*   **Selector:** Dropdown of available White Nodes.
*   **Status Panel:** Shows who is currently "voting" (Alex, Sasha, or Alison).
*   **Voting List:** A clean list of checkboxes for the generated ideas.
*   **Feedback:** Toast notifications when a batch is rejected ("No consensus found, generating fresh ideas...").

---

## 6. Implementation Stack
*   **Language:** Python 3.9+
*   **Frontend/UI:** Streamlit (for rapid local deployment and interactivity).
*   **Graph Engine:** NetworkX (logic) + Graphviz (rendering).
*   **AI Engine:** OpenAI API (GPT-4o) for structuring CSVs and generating sub-concepts.
*   **Version Control:** Git.