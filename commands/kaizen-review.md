---
description: "Iterate on an existing Kaizen User/Web/DB doc -- lighten, split, add scenarios, restructure"
argument-hint: "<doc_path> [codebase_path] \"<what to change>\""
---

# Kaizen Review: Iterate on a User/Web/DB Doc

Revise an existing Kaizen design doc. Use this to lighten, split, add scenarios, restructure, fix coverage gaps, or apply feedback from peer review.

## Arguments

Parse `$ARGUMENTS` for:

- `doc_path` -- path to the existing kaizen doc (required)
- `codebase_path` -- path to project root (optional, for grounding new content in actual code)
- Change description -- quoted string describing what to change

## Workflow

### Phase 1: Load context

Read `$KAIZEN_TEMPLATES_DIR/user_web_db_prompt.md` for generation rules and style guidance. If the env var is not set, stop and tell the user to export it (e.g., `export KAIZEN_TEMPLATES_DIR=~/dev/docs_and_designs/templates`). This stays loaded as system context for the revision.

### Phase 2: Read existing doc

Read the kaizen doc at the provided `doc_path`. Understand its current structure, scenarios, decisions, and scope.

### Phase 3: Understand the ask

Parse what the user wants changed. Common revision types:

- **Lighten** -- reduce scenario count, make sections more compact, remove edge cases
- **Split** -- break a large doc into separate docs per concern
- **Add scenarios** -- cover flows that are missing (the user will say which)
- **Restructure** -- change doc type (e.g., switch from feature format to fix format), reorganize sections
- **Fix coverage gaps** -- add missing sections, fill in incomplete walkthroughs
- **Apply review feedback** -- incorporate specific feedback from peer review
- **Update from code** -- if codebase_path provided, re-ground the doc in current code state

If the change description is unclear, ask the user to clarify before proceeding. Be specific about what you don't understand.

### Phase 4: Explore codebase (if needed)

If `codebase_path` was provided and the revision requires grounding in code (new scenarios, updating stale references, adding implementation details), use a Task agent (subagent_type=Explore) to read relevant files. Budget: 10 key files max.

Skip if no codebase_path or if the revision is purely structural (lighten, split, reorganize).

### Phase 5: Regenerate

Apply the requested changes following the style rules from `user_web_db_prompt.md`.

- **Overwrite** the existing doc at the same path by default
- **If splitting**: write new files alongside the original (e.g., `kaizen_{slug}_{concern}.md`) and note that the original can be removed
- Preserve content that wasn't asked to change -- don't rewrite the entire doc if only one section needs work
- When adding scenarios, follow the same actor tag format and data state conventions as existing scenarios

### Phase 6: Present

Summary of what changed:
- Sections modified
- Scenarios added/removed/rewritten
- Structural changes made
- Anything that still needs attention

Ask if the user wants further adjustments.

$ARGUMENTS
