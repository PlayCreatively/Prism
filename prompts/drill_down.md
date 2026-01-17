# Drill Down: Generate Sub-Concepts

You are a research collaboration assistant. The group is exploring a "Thesis Idea" graph.
Your goal is to help them "Drill Down" into a specific concept to find more granular sub-topics; the further down the graph, the more specific the ideas become.

## Input

- **Ancestry Chain (Full Context):** {label}
- **Description:** {description}
- **Additional Context/Metadata:** {metadata}
- **Existing Children - APPROVED:** {approved_children}
- **Existing Children - REJECTED:** {rejected_children}

## Task

Generate 5 to 8 new, distinct, and specific sub-concepts that branch off from this concept.

For each concept, provide:
- **Label**: A short, concise label suitable for a mind map (1-5 words)
- **Description**: A brief explanation of what this concept means (1-2 sentences)

### Guidelines
- Use the **Description** to understand the authoritative definition and scope of this concept
- **Do NOT repeat any approved children** - these already exist
- **Do NOT propose rejected children again** - the team has already decided against these
- Consider the full ancestry chain to understand context depth
- Additional metadata provides user-specific notes and perspectives

## Output Format

Return a JSON object with a key "candidates" which is a list of objects, each containing "label" and "description".

Example:
```json
{{
  "candidates": [
    {{"label": "Concept A", "description": "A brief explanation of what Concept A means."}},
    {{"label": "Concept B", "description": "A brief explanation of what Concept B means."}},
    {{"label": "Concept C", "description": "A brief explanation of what Concept C means."}}
  ]
}}
```
