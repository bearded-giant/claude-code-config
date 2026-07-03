---
description: "Explore the code areas a feature touches and draft a concrete implementation plan."
argument-hint: "[feature-name]"
---

# Plan Feature

Ground yourself in the code the feature touches, then draft an actionable implementation plan. Grounding is done against live code at plan time -- no stored snapshots that rot. Durable non-obvious knowledge (gotchas, key decisions) is distilled into the feature's `facts.md`, which is frontmattered, lifecycle-tracked, and indexed.

## Arguments

- feature: (optional) Feature name in kebab-case. If omitted, use the current `in_progress` feature from `.giantmem/features/features.json`.

## Steps

### 1. Identify the feature

If no argument provided:
- Read `.giantmem/features/features.json` and find the feature with `"status": "in_progress"`
- If multiple in_progress, list them and ask
- If none, tell the user to run `/new-feature` or `/start-feature` first

Validate `.giantmem/features/{feature}/proposal.md` exists (or legacy `spec.md` symlink). Read it.

Read all delta-specs at `.giantmem/features/{feature}/specs/{domain}/spec.md` (may be empty) and any source-specs at `.giantmem/specs/{domain}/spec.md` for the areas the feature touches. Delta-specs describe what behavior changes; source-specs describe current behavior. Both inform the plan. Read the feature's `facts.md` -- it may already hold gotchas from earlier work.

### 2. Scope the code areas to explore

From the proposal + specs, identify the bounded code areas the feature touches (auth layer, payment flow, the command loader, etc.). These are just a scoping list for the exploration below -- they are not persisted anywhere.

### 3. Ground against the code

Grounding source depends on whether the repo is checked out in this session:

- **Repo is checked out here (the common case):** launch a `code-explorer` agent per area (run in parallel for multiple areas). It reads the live tree, so it is never stale. Ask each agent for: entry points, key files + what they export, data flow, and -- most important -- **gotchas and non-obvious design decisions** (the WHY that isn't recoverable from reading the code).
- **Repo is NOT checked out here** (planning against frost / customcheckout / a dapr service you don't have in this tree): use the `local-cerebro` skill (`~/.claude/skills/local-cerebro/scripts/cerebro-ask.sh "... in <repo>, cite files"`). Cerebro reads its own indexed checkout live -- also never stale. One question per call.

Do NOT write domain JSON files. The exploration output feeds the plan (below) and the facts distillation, nothing else.

### 4. Distill durable knowledge into facts.md

From the exploration, capture ONLY the durable, non-obvious bits into `.giantmem/features/{feature}/facts.md`: gotchas, key architectural decisions + rationale, and hard-won identifiers (config keys, beta flags, test commands, cache-key shapes). Skip structural inventory (entry points, file lists, exports) -- that is recoverable from live code on demand and rots the moment the code changes. Append; do not clobber existing facts. Keep `facts.md` frontmatter intact.

### 5. Draft the feature plan

Write `.giantmem/features/{feature}/plan.md`:

```markdown
# Plan: {feature name (title case)}

planned: {today's date}

## Context

{Brief summary of what the feature does, pulled from the proposal.}

## Grounding

{2-3 lines per code area: what's relevant to this feature and where it lives. Reference file paths, not stored JSONs.}

## Implementation Steps

1. {concrete step with file paths and function names}
2. {concrete step}
...

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| path/to/file.py | modify | add session validation |
| path/to/new_file.py | create | new endpoint |

## Open Questions

- {anything unresolved}
```

The plan must be concrete -- actual file paths, function names, specific changes. Not vague phases.

### 6. Update meta.json

Add plan-related fields to `.giantmem/features/{feature}/meta.json`:

```json
{
  "planned": true,
  "planned_at": "{today's date}",
  "last_session": "{today's date}"
}
```

### 7. Report

```
Feature '{feature}' planned.

Grounded: {list of code areas explored, and whether via live tree or cerebro}
Facts captured: .giantmem/features/{feature}/facts.md (+{n} gotchas/decisions)
Plan: .giantmem/features/{feature}/plan.md
```

## Rules

- Do NOT modify code files, only workspace files under `.giantmem/`
- Read every file before modifying it
- Ground on live code (this tree's code-explorer, or cerebro for un-checked-out repos) -- never persist a structural snapshot
- facts.md holds only the durable WHY (gotchas, decisions, identifiers), not the recoverable WHAT
- Keep plan.md actionable -- concrete steps, file paths, function names
- Any JSON written must be valid, parseable JSON with lowercase comments

$ARGUMENTS
