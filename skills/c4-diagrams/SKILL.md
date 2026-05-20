---
name: c4-diagrams
description: Generate Mermaid C4 architecture diagrams (Context L1 + Container L2 by default; L3 only on explicit request). Triggers when user says "diagram this", "show me the architecture", "how does X talk to Y", "map this system", "draw a flow chart", "C4 diagram", or invokes the skill explicitly. Skip if user only wants prose explanation, not visual.
---

# C4 Architecture Diagrams

Generate C4 architecture diagrams using Mermaid syntax.

## Default Behavior

- **Always generate**: Context (L1) and Container (L2) diagrams
- **Only on request**: Component (L3) - user must explicitly ask
- **Output format**: Mermaid C4 syntax in markdown code blocks
- **Write to**: `.giantmem/plans/` or `.giantmem/context/` depending on purpose

## Process

1. Analyze the code path or feature requested
2. Identify system boundaries, external actors, containers
3. Generate Context diagram (L1) - system and external dependencies
4. Generate Container diagram (L2) - internal structure
5. Skip Component (L3) unless explicitly requested

## Output Structure

```markdown
# [Feature/System] Architecture

## Context Diagram (L1)
[mermaid block]

Brief description of external interactions.

## Container Diagram (L2)
[mermaid block]

Brief description of internal structure.
```

## Templates

Reference @templates/context.md and @templates/container.md for Mermaid C4 syntax.

## Rules

- Keep descriptions concise (1-2 sentences per diagram)
- Use snake_case for IDs in mermaid
- Label all relationships with action verbs
- Include external systems and actors
- Write output to .giantmem/ per workspace rules
