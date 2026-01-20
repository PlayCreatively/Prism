# Custom Node Types System - Specification v2

## Overview

This document specifies a system for user-defined node types with customizable fields, display styles, and AI prompts. Users can create node type definitions that control:

1. **What custom data** is stored in a node (fields added on top of immutable core fields)
2. **How custom data** is displayed (semantic types with display options)
3. **What prompts** are available for that node type (auto-generated from `.md` files)

---

## Directory Structure

```
node_types/
├── _schema.json              # Master schema defining valid field types & options
├── default/                  # The base node type (existing nodes migrate here)
│   ├── definition.json       # Custom fields (empty for default: {"fields": []})
│   └── drill_down.md         # Default prompt for all nodes
├── game_mechanic/            # Example custom type
│   ├── definition.json       # Custom fields for this type
│   ├── drill_down.md         # Can override default prompts
│   ├── explore_variations.md # Type-specific prompt
│   └── analyze_balance.md    # Another type-specific prompt
└── research_paper/           # Another custom type
    ├── definition.json
    ├── find_sources.md
    └── generate_abstract.md
```

### Naming Convention

- **Folder name** = Node type identifier (e.g., `game_mechanic`)
- **Display name** = Folder name with `_` replaced by spaces (e.g., "Game Mechanic")
- **Reserved file**: `_schema.json` is the master schema, not a node type folder

---

## Core Architecture

### Immutable Base Fields (ALWAYS present on ALL nodes)

These fields are **hardcoded** and cannot be removed, renamed, or reordered by users. They form the skeleton of every node:

| Field | Storage | Purpose | UI Location |
|-------|---------|---------|-------------|
| `id` | string (UUID) | Unique identifier | Hidden (system-managed) |
| `parent_id` | string/null | Graph hierarchy | Hidden (system-managed) |
| `node_type` | string | Type identifier | Badge at top of node card |
| `label` | string | Node title | Header (markdown view, input edit) |
| `description` | string | Main content | Body (markdown view, textarea edit) |
| `metadata` | string | User's notes | Per-user section (markdown view, textarea edit) |
| — voting — | derived | Interest state | Voting buttons per user |
| — actions — | derived | Prompts | Auto-generated buttons from `.md` files |

**Key principle**: Users can only ADD custom fields. They cannot modify the base fields.

### Custom Fields (User-Defined via `definition.json`)

Custom fields are stored in the node JSON alongside base fields:

```json
{
  "id": "abc-123",
  "node_type": "game_mechanic",
  "parent_id": "xyz-789",
  "label": "Resource Management",
  "description": "A system where players...",
  "complexity": "Medium",
  "keywords": ["strategy", "economy"]
}
```

Custom fields (`complexity`, `keywords`) are defined in the type's `definition.json`.

---

## Semantic Data Types

Users specify **semantic types** with built-in storage and display behaviors:

| Type | Storage | View Mode | Edit Mode | Options |
|------|---------|-----------|-----------|---------|
| `text` | string | Markdown | Textarea or input | `multiline: bool` (default: true) |
| `tag` | string[] or string | Badges | Input or dropdown | `selection`, `multiple` |
| `user` | string or string[] | User badge(s) | Dropdown | `multiple: bool` (default: false) |

### Tag Behavior

The `tag` type adapts based on configuration:

| Config | Storage | Edit UI | Example |
|--------|---------|---------|---------|
| No `selection` | string[] | Free-form tag input | Keywords, labels |
| `selection` + `multiple: true` | string[] | Multi-select dropdown | Categories |
| `selection` + `multiple: false` | string | Single-select dropdown | Status, priority |

---

## Custom Field Definition Schema

### `definition.json` Structure

```json
{
  "fields": [
    {
      "key": "complexity",
      "type": "tag",
      "label": "Complexity Level",
      "selection": ["Low", "Medium", "High"],
      "multiple": false,
      "required": true
    },
    {
      "key": "keywords",
      "type": "tag",
      "label": "Keywords"
    },
    {
      "key": "assigned_to",
      "type": "user",
      "label": "Assigned To"
    },
    {
      "key": "notes",
      "type": "text",
      "label": "Implementation Notes",
      "multiline": true
    }
  ]
}
```

### Field Properties

| Property | Required | Type | Description |
|----------|----------|------|-------------|
| `key` | Yes | string | Storage key (lowercase, underscores) |
| `type` | Yes | string | One of: `text`, `tag`, `user` |
| `label` | No | string | Display label (default: key with `_` → space, title case) |
| `required` | No | boolean | Must have value to save (default: false) |
| `multiline` | No | boolean | For `text`: textarea vs input (default: true) |
| `selection` | No | string[] | For `tag`: enum values (if omitted, free-form) |
| `multiple` | No | boolean | For `tag`/`user`: allow multiple values (default: true for tag, false for user) |

### Reserved Keys (Will Cause Validation Error)

- `id`, `parent_id`, `node_type`, `label`, `description`, `metadata`

### Default Type Definition

The `default` type has an empty `definition.json`:

```json
{
  "fields": []
}
```

This means default nodes have **only base fields**—the original behavior.

---

## Prompt Button System

### How It Works

1. **Discovery**: System scans each node type folder for `.md` files
2. **Button Generation**: Each `.md` file becomes a prompt button
3. **Rendering**: Buttons appear in the "Actions" section of the node card
4. **Execution**: Clicking triggers AI workflow with that prompt

### Prompt File Format

```markdown
---
name: Drill Down
description: Generate sub-concepts for deeper exploration
material-logo: account_tree
produces_type: default
---

# Drill Down Prompt

You are an expert helping explore sub-concepts...

## Context
- **Ancestry**: {label}
- **Description**: {description}
- **Notes**: {metadata}
- **Existing Children (Approved)**: {approved_children}
- **Existing Children (Rejected)**: {rejected_children}

## Output Format
Return a JSON object matching this schema:

{output_schema}
```

### YAML Frontmatter Properties

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Button label |
| `description` | No | Button tooltip |
| `material-logo` | No | Material icon name (default: `smart_toy`) |
| `produces_type` | No | Node type for generated suggestions (default: same as itself) |

### Template Variables

The system injects these variables before sending to AI:

| Variable | Source |
|----------|--------|
| `{label}` | Node's label (or ancestry chain) |
| `{description}` | Node's description |
| `{metadata}` | Active user's notes |
| `{approved_children}` | Existing children user has accepted |
| `{rejected_children}` | Existing children user has rejected |
| `{custom_field_key}` | Value of any custom field by its key |
| `{output_schema}` | **Auto-generated JSON schema** for the target node type |

### Auto-Generated Output Schema

The `{output_schema}` variable is automatically generated from the `produces_type` definition:

For `produces_type: game_mechanic` with this definition:
```json
{
  "fields": [
    {"key": "complexity", "type": "tag", "selection": ["Low", "Medium", "High"], "multiple": false},
    {"key": "keywords", "type": "tag"}
  ]
}
```

Generates:
```json
{
  "candidates": [
    {
      "label": "string",
      "description": "string",
      "complexity": "Low | Medium | High",
      "keywords": ["string", "..."]
    }
  ]
}
```

This ensures AI always produces correctly-formatted nodes for the target type.

---

## UI Rendering

### Node Card Layout (Fixed Order)

```
┌─────────────────────────────────────────────────────┐
│ [game mechanic]                          (node type)│
├─────────────────────────────────────────────────────┤
│ Resource Management                          (label)│
├─────────────────────────────────────────────────────┤
│ A system where players manage limited         (desc)│
│ resources to achieve objectives...                  │
├─────────────────────────────────────────────────────┤
│ ─── Custom Fields ───                               │
│ Complexity: [Medium]                                │
│ Keywords: [strategy] [economy] [puzzle]             │
│ Assigned To: [Alex]                                 │
├─────────────────────────────────────────────────────┤
│ ─── Your Notes ───                                  │
│ I think this could work well with...      (metadata)│
├─────────────────────────────────────────────────────┤
│ [✓ Alex] [✓ Sasha] [○ Alison]              (voting) │
├─────────────────────────────────────────────────────┤
│ [🌳 Drill] [🔀 Variations] [⚖ Balance]    (actions) │
└─────────────────────────────────────────────────────┘
```

### Missing Field Warning

If a node has a `node_type` but is missing a field defined in that type's schema:

- **View Mode**: Show field with ⚠️ icon and "(missing)" text
- **Edit Mode**: Show empty field with validation warning

Example:
```
Complexity: ⚠️ (missing - required field)
```

---

## Node Data Structure

### Global Node File (`db/{project}/nodes/{uuid}.json`)

```json
{
  "id": "959c4d5f-043f-400d-aadc-d09b109ba7ac",
  "node_type": "game_mechanic",
  "parent_id": "abc123...",
  "label": "Resource Management",
  "description": "A system where players manage limited resources...",
  "complexity": "Medium",
  "keywords": ["strategy", "economy"]
}
```

### User State File (`db/{project}/data/{user}.json`)

Unchanged from current structure:

```json
{
  "user_id": "Alex",
  "nodes": {
    "959c4d5f-...": {
      "interested": true,
      "metadata": "I think this could work well with our theme..."
    }
  }
}
```

**Note**: `metadata` stays in user files (per-user notes). Custom fields go in node files (shared).

---

## Migration

### Automatic Migration for Existing Nodes

When loading a node without `node_type`:

1. Add `node_type: "default"`
2. Save the updated node file
3. Log the migration

### Migration Script (One-Time)

```python
# Run once to migrate all existing nodes
for node_file in db/*/nodes/*.json:
    if "node_type" not in node_data:
        node_data["node_type"] = "default"
        save(node_file)
```

---

## Validation

### On Node Load

1. Look up node's type definition
2. Check required custom fields have values
3. Check enum values are valid (for tags with `selection`)
4. Collect warnings for missing optional fields
5. Return node with validation warnings attached

### On Node Save

1. Validate required fields (block save if missing)
2. Validate enum constraints (block if invalid)
3. Warn for optional missing fields (allow save)
4. Reject reserved keys in custom field values

### Validation Messages

| Issue | Severity | Action |
|-------|----------|--------|
| Missing required field | Error | Block save |
| Invalid enum value | Error | Block save |
| Missing optional field | Warning | Show warning, allow save |
| Unknown field in type def | Warning | Ignore field, show warning |
| Reserved key used | Error | Block type definition load |

---

## Master Schema (`_schema.json`)

Validates `definition.json` files:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Node Type Definition",
  "type": "object",
  "required": ["fields"],
  "properties": {
    "fields": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["key", "type"],
        "properties": {
          "key": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9_]*$",
            "not": {
              "enum": ["id", "parent_id", "node_type", "label", "description", "metadata"]
            }
          },
          "type": {
            "type": "string",
            "enum": ["text", "tag", "user"]
          },
          "label": {"type": "string"},
          "required": {"type": "boolean", "default": false},
          "multiline": {"type": "boolean", "default": true},
          "selection": {
            "type": "array",
            "items": {"type": "string"}
          },
          "multiple": {"type": "boolean"}
        }
      }
    }
  }
}
```

---

## Example: Creating a Custom Node Type

### Step 1: Create folder

```
node_types/research_paper/
```

### Step 2: Define custom fields (`definition.json`)

```json
{
  "fields": [
    {
      "key": "methodology",
      "type": "tag",
      "label": "Research Methodology",
      "selection": ["RtD", "Iterative Design", "Reflective Practice", "Formal Analysis"],
      "multiple": false,
      "required": true
    },
    {
      "key": "author",
      "type": "user",
      "label": "Primary Author"
    },
    {
      "key": "keywords",
      "type": "tag",
      "label": "Keywords"
    },
    {
      "key": "abstract",
      "type": "text",
      "label": "Abstract",
      "multiline": true
    }
  ]
}
```

### Step 3: Create prompt files

**`drill_down.md`** (inherits behavior but uses research paper schema):
```markdown
---
name: Drill Down
description: Explore sub-topics for this research area
material-logo: account_tree
produces_type: research_paper
---

# Research Drill Down

Given the research paper concept below, suggest specific research questions.

## Context
- **Topic**: {label}
- **Abstract**: {abstract}
- **Methodology**: {methodology}
- **Keywords**: {keywords}

## Output Format
{output_schema}
```

**`find_sources.md`**:
```markdown
---
name: Find Sources
description: Discover relevant academic sources
material-logo: library_books
produces_type: default
---

# Find Sources

Suggest relevant academic sources for this research topic.

## Context
- **Topic**: {label}
- **Abstract**: {abstract}

## Output Format
{output_schema}
```

### Result

The "research paper" type now has:
- All base fields (label, description, metadata, voting, actions)
- Custom fields: methodology, author, keywords, abstract
- Two prompt buttons: "Drill Down" and "Find Sources"

---

## Comparison to Current Codebase

### What Changes

| Area | Current | New |
|------|---------|-----|
| Node storage | Fixed fields only | Base + custom fields |
| Node type | `node_type` field exists | Same, now required |
| Prompts | Single `prompts/` folder | Per-type in `node_types/{type}/` |
| AI output | Fixed candidate format | Schema-driven from type definition |
| UI rendering | Fixed layout | Dynamic custom fields section |

### What Stays the Same

| Area | Behavior |
|------|----------|
| User state files | Same structure (interested, metadata) |
| Voting system | Same logic and display |
| Graph structure | Same (parent_id relationships) |
| Git workflow | Same auto-sync behavior |
| Project isolation | Same multi-project support |

### Migration Impact

- **Existing nodes**: Automatically get `node_type: "default"`, no other changes
- **Existing prompts**: Move from `prompts/` to `node_types/default/`
- **Existing UI**: Continues working, custom fields section added

---

## Design Decisions (Confirmed)

### 1. Prompt Button Inheritance

**Decision**: No inheritance. Each type must define its own prompts.

**Rationale**: This prevents compatibility issues where a prompt references custom fields that don't exist on certain node types. It also enables **implicit workflow control**—you can design intricate pipelines where certain node types can only produce specific other types.

### 2. Node Type Selection on Creation

**Decision**: The `produces_type` field in the prompt YAML determines what type of child nodes are created. Users can only change this by editing the prompt markdown file itself.

**Rationale**: This keeps the workflow predictable and designer-controlled.

### 3. Prompt File Discovery

**Decision**: Each type only sees its own prompts. No inheritance from `default/`.

**Rationale**: Consistency with decision #1. If you want a "Drill Down" prompt on a custom type, you must create it in that type's folder.

### 4. Custom Field Storage

**Decision**: All custom fields are shared (stored in node files). No per-user custom fields.

**Rationale**: Keeps the system simple. Per-user notes already exist via `metadata` in user state files.

---

## Implementation Priority

### Phase 1: Core Infrastructure
1. `NodeTypeManager` - load/validate type definitions
2. Migration script - add `node_type` to existing nodes
3. Move `prompts/` to `node_types/default/`

### Phase 2: Data Layer
1. Update `DataManager` to handle custom fields
2. Add validation on load/save
3. Schema generation for AI prompts

### Phase 3: UI Integration
1. Dynamic field rendering in node details
2. Prompt button discovery and rendering
3. Validation warnings display

### Phase 4: AI Workflow
1. Update prompt loading to use node type folders
2. Inject `{output_schema}` variable
3. Parse AI response against type schema
