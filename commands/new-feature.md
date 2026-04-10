---
description: "Create a new feature folder with templates. Auto-detects status: pending if another feature is in_progress, otherwise in_progress."
argument-hint: "<name> [builds_on] [base-branch]"
---

Create a new feature folder with templates. Status is auto-detected:
- If another feature is already `in_progress` → new feature is `pending` (stub for later)
- If no feature is `in_progress` → new feature is `in_progress` (start working immediately)

## Arguments

- name: Feature name in kebab-case (e.g., "jwt-session-enforcement")
- builds_on: (optional) Parent feature this depends on
- base_branch: (optional) Base branch to create the feature branch from (e.g., `stage`, `main`, `master`). If not provided, prompt the user. Only used for in_progress features.

## Steps

1. Validate .giantmem/features/ exists, if not inform user to run /ws-init

2. **Determine status automatically**

   Read `.giantmem/features/features.json` (create it as `{}` if it doesn't exist).

   Check if any feature in the cache has `"status": "in_progress"`.
   - If yes → this feature's status is `pending`
   - If no → this feature's status is `in_progress`

   Tell the user which status was auto-selected and why (e.g., "Creating as pending — feature X is currently in_progress" or "Creating as in_progress — no active feature").

3. Create .giantmem/features/{name}/ directory

4. Create spec.md based on status:

**4a. If status is `in_progress`:**

```markdown
# Feature: {name (title case)}

builds_on: {builds_on or "none"}
status: in_progress
created: {today's date}

## Purpose

<!-- describe what this feature does and why -->

## Scope

<!-- what's included and what's out of scope -->

## Key Decisions

<!-- architectural decisions made, with rationale -->

## Acceptance Criteria

- [ ] criterion 1
- [ ] criterion 2

## Files Modified

<!-- list key files created/modified -->
```

**4b. If status is `pending`:**

Use a minimal template. The user is stubbing this out for later, not starting work now. Fill in the Purpose section with whatever discovery or context the user provides (don't leave it as a placeholder if they gave you a reason).

```markdown
# Feature: {name (title case)}

builds_on: {builds_on or "none"}
status: pending
created: {today's date}

## Purpose

{user's description of why this feature is needed, or "<!-- describe what this feature does and why -->" if none given}

## Discovery Context

{what prompted this stub — e.g., which feature was being worked on, what was discovered}

## Acceptance Criteria

- [ ] criterion 1
```

5. **Create branch (in_progress only, skip for pending)**

   Branch creation only applies when status is `in_progress`. Pending features defer branch creation to `/start-feature`.

   - Ask the user for a branch name (feature name != branch name on purpose)
   - If `base_branch` was provided as an argument, use it. Otherwise, ask the user for the base branch (e.g., `stage`, `main`, `master`). Do NOT auto-detect with `git branch -r` — it's too slow on large repos.
   - Run: `git fetch origin {base} && git checkout -b {branch_name} origin/{base}`
   - If the user says they already have a branch or want to skip, just record the branch name (or leave it empty) and move on

6. **Frontend (dual-repo) prompt (in_progress only, skip for pending)**

   After backend branch creation, ask:

   ```
   Does this feature include frontend changes?
   1. No (backend only)
   2. Yes
   ```

   **If yes:**
   - Ask for the frontend branch name (default: same as the backend branch name)
   - The frontend base branch is always `master` — do not ask
   - Create the frontend worktree: run `fewta {frontend_branch} master` from the shell
     - `fewta` is the registered frontend worktree command (from `wt-frontend.sh`)
     - This creates `~/dev/javascript/frontend-wt/{frontend_branch}/` with a fresh worktree
   - If `fewta` is not available in the shell (command not found), fall back to:
     ```bash
     cd ~/dev/javascript/frontend-wt/.bare && git worktree add -b {frontend_branch} ../{frontend_branch} origin/master
     ```
   - Record the frontend details (see steps 7-9 for where they go)

   **If no:** set `frontend` to `null` in meta.json/features.json.

7. Create facts.md:

```markdown
# {name} facts

## Branch

branch: {branch_name or "pending"}
base: {base_branch or "tbd"}

## Frontend

frontend: {true or false}
frontend_branch: {frontend_branch or "n/a"}
frontend_worktree: {~/dev/javascript/frontend-wt/{frontend_branch} or "n/a"}

## Identifiers

beta_flag:
config_keys:
  -

## Endpoints

affected:
  -
new:
  -

## Key Files

-

## Test Commands

```bash
# add test commands here
```
```

8. Create {name}-notes.md as an empty file (no content, no placeholders).

9. Create meta.json:

```json
{
  "name": "{name}",
  "status": "{status}",
  "branch": "{branch_name or ""}",
  "base_branch": "{base_branch or ""}",
  "builds_on": ["{builds_on}"],
  "beta_flag": "",
  "frontend": {
    "enabled": false
  },
  "created": "{today's date}",
  "last_session": "{today's date}"
}
```

When frontend is enabled:

```json
{
  "frontend": {
    "enabled": true,
    "branch": "{frontend_branch}",
    "base_branch": "master",
    "worktree": "~/dev/javascript/frontend-wt/{frontend_branch}"
  }
}
```

10. **Update features.json cache**

   Read `.giantmem/features/features.json`, add the new feature entry:

   ```json
   {
     "{name}": {
       "name": "{name}",
       "status": "{status}",
       "branch": "{branch_name or ""}",
       "base_branch": "{base_branch or ""}",
       "builds_on": "{builds_on or "none"}",
       "beta_flag": "",
       "frontend": {
         "enabled": true/false,
         "branch": "{frontend_branch or ""}",
         "base_branch": "master",
         "worktree": "~/dev/javascript/frontend-wt/{frontend_branch}"
       },
       "created": "{today's date}",
       "last_session": "{today's date}"
     }
   }
   ```

   When frontend is not enabled, use `"frontend": null`.

   Write the updated JSON back to `.giantmem/features/features.json`.

11. Update .giantmem/features/_index.md:
   - Add new row to the appropriate table (Pending Features for `pending`, Active Features for `in_progress`)
   - Format: `| [{name}]({name}/) | {status} | | {builds_on or "-"} | {FE if frontend enabled, otherwise -} |`

12. Display the created structure and confirm:
   - If `pending`: note that `/start-feature {name}` will transition it to `in_progress` and create the branch when ready.
   - If `in_progress`: confirm the branch checkout.
   - If frontend enabled: confirm the frontend worktree was created and show the path.
