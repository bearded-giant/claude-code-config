---
description: "Show the next ready artifact for a feature (informational, derived from artifacts.json + artifact_dag.yaml)."
argument-hint: "[feature-name]"
---

Print the next ready artifact-type for the given feature, with a suggested
path and a 2-line instruction. Informational — never enforces.

## Arguments

- feature: (optional) Feature name. If omitted:
  - Use the in_progress feature from `features.json`.
  - If multiple in_progress: list them and prompt.
  - If none: exit with "no active feature".

## Steps

1. **Resolve feature** (see Arguments).

2. **Load DAG** from `~/.claude/config/artifact_dag.yaml` (single source for
   type → requires mapping). Falls back to a hardcoded minimal DAG if file
   missing (proposal → tasks).

3. **Load live state** by running `giantmem artifact list -f {feature} --json`.
   If `.giantmem/artifacts.json` is stale or missing, first run
   `giantmem artifact reindex`.

4. **Compute status per type** for the feature:
   - `done`    = at least one instance with `status: done`
   - `ready`   = all `requires` types are `done` AND either own type missing
                 OR own status is `draft`
   - `blocked` = any `requires` type is missing AND not marked optional
   - `skipped` = optional type that has no instances yet — informational only

5. **Pick next-ready by topological order** (proposal first, then enabled
   downstream artifacts). Tie-break by alphabetical type name.

6. **Print result.** Format:

   ```
   feature: {name}  branch: {branch}

   next ready: tasks
     path:  .giantmem/features/{name}/tasks.md
     hint:  copy ~/.claude/templates/tasks.md, fill checkboxes per Requirements
            in features/{name}/specs/{domain}/spec.md

   also ready (parallel):
     - design   .giantmem/features/{name}/design.md  (optional)

   blocked:
     - review   (requires tasks done — 0/3 checkboxes)

   done:
     - proposal
     - delta-spec/workflow (2 Requirements)
   ```

7. If everything is `done`: report "all DAG nodes done — `/complete-feature`
   when ready". If nothing is `ready` AND nothing is `done`: report "start
   with proposal — `~/.claude/templates/proposal.md`".

## Rules

- Never write files. Never modify status. Read-only.
- Never enforce — user can skip any artifact. If the DAG says `tasks` is
  blocked but the user wants to write `tasks` anyway, that is fine.
- DAG file is informational. Fall back to minimal DAG when missing.
- Tasks-checkbox auto-status (counted by `giantmem artifact list`) — do not
  ask the user about progress, just report what the index says.
