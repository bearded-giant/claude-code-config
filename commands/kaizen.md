---
description: "Generate a Kaizen User/Web/DB design doc from problem statement and optional codebase"
argument-hint: "[codebase_path] [--docs=path1,path2] \"<problem statement>\" [--type=feature|fix|refactor] [--light] [--split]"
---

# Kaizen: Generate User/Web/DB Design Doc

Generate a Kaizen design document using the User/Web/DB format. Traces user actions through the API and data layers for peer review.

## Templates

All templates live at `$KAIZEN_TEMPLATES_DIR`. If the env var is not set, stop and tell the user to export it (e.g., `export KAIZEN_TEMPLATES_DIR=~/dev/docs_and_designs/templates`). Read these before doing anything else:

1. `user_web_db_prompt.md` -- generation rules and style guide. Load as system context for the entire generation.
2. `user_web_db.md` -- scaffold structure. The output doc follows this skeleton.
3. `user_web_db_input.md` -- reference for what inputs improve quality.

## Arguments

Parse `$ARGUMENTS` for:

- `codebase_path` -- path to project root (optional, no flag prefix)
- `--docs=path1,path2` -- comma-separated paths to existing plans, specs, research, or design docs to feed into generation
- Problem statement -- quoted string describing the problem
- `--type=feature|fix|refactor` -- determines User/Web/DB section structure
- `--light` -- fewer scenarios, more compact output
- `--split` -- generate separate docs per concern instead of one unified doc

## Workflow

### Phase 1: Load context

Read all three template files from `$KAIZEN_TEMPLATES_DIR`:
- `user_web_db_prompt.md`
- `user_web_db.md`
- `user_web_db_input.md`

These are your generation rules. Follow them exactly.

### Phase 2: Gather input

Parse what was provided in $ARGUMENTS. Then ask interactively for anything critical that's missing. Skip questions already answered by the problem statement or flags.

Ask about:
- **Doc type** (if `--type` not provided): feature, fix, or refactor?
- **Key files/directories** (if codebase_path provided): which areas to focus the explore on?
- **Known decisions**: has the team already settled anything? These go straight into the Key Points section.
- **Exemptions**: any user types or systems exempt from this feature?
- **Scope boundaries**: what's explicitly NOT in scope?
- **Plan/design docs** (if `--docs` not provided): "Any existing plans, specs, or design docs I should read?" Accept file paths or directory paths.

Be efficient. If the problem statement is detailed enough, skip redundant questions. Group remaining questions into a single interactive prompt using AskUserQuestion or direct questions.

### Phase 3: Read input docs

If docs were provided (via `--docs` or interactively):
- Read every file provided. These can be plans, specs, PRDs, research notes, prior kaizen docs, or any design material.
- Extract context that feeds into generation: problem framing, decisions already made, scope, data models, API shapes, rollout plans.
- This content directly informs Background, Key Points, and scenario content in the output.

### Phase 4: Explore codebase

**Skip entirely if no codebase_path was provided** (greenfield mode).

If codebase_path was provided, use a Task agent (subagent_type=Explore) to:
- Map project structure
- Find files related to the problem
- Read key files (models, services, endpoints, schemas)
- Capture actual table/column names, endpoint paths, function names, beta flags
- Budget: 15-20 key files max

The explore should focus on areas identified in Phase 2 (key files/directories the user called out).

### Phase 5: Generate

Write the design doc following the scaffold structure (`user_web_db.md`) and generation rules (`user_web_db_prompt.md`).

Key generation rules:
- Structure the User/Web/DB section based on doc type:
  - **feature**: scenarios cover new behavior directly, grouped by user flow
  - **fix**: separate "how it works today" / "issues" / "fixes"
  - **refactor**: current architecture vs target architecture
- Ground in codebase context if available (actual table names, endpoint paths, response shapes)
- Incorporate content from input docs (decisions, data models, API shapes, rollout context)
- Use `[user]`, `[web]`, `[db]` actor tags for scenario walkthroughs
- Each scenario gets its own data state block (Starting/Ending)
- JSON blocks are pseudocode with `// new` and `// changed` markers
- Fill in every section of the scaffold. Remove all placeholder text.
- Set the date to today's date
- If `--light`: fewer scenarios, skip edge cases, keep sections compact
- If `--split`: generate separate docs per concern, each self-contained with cross-references

**Output path:** `scratch/filebox/kaizen_{slug}.md` where `{slug}` is a snake_case version of the feature name derived from the problem statement.

If `--split` is used, output multiple files: `scratch/filebox/kaizen_{slug}_{concern}.md`

### Phase 6: Present

After writing the doc, present a summary:
- What was generated (file path(s))
- Number of scenarios covered
- Key points captured
- Open questions flagged
- Ask if the user wants adjustments

Remind the user they can iterate with `/kaizen-review`.

$ARGUMENTS
