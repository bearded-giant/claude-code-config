---
description: "Create a new feature folder with templates. Defaults to pending (stub). Use 'start' to begin immediately."
argument-hint: "<name> [builds_on] [start] [base-branch]"
---

Create a new feature folder with templates. Defaults to `pending` status (stub). Use `/start-feature` to promote later.

## Arguments

- name: Feature name in kebab-case (e.g., "jwt-session-enforcement")
- builds_on: (optional) Parent feature this depends on
- start: (optional) If "start", "active", or "in_progress" is passed as an argument or the user explicitly says they want to start working on it now, create the feature with `status: in_progress` instead of `pending`. Use the full spec template (see step 3a). Create the branch.
- base_branch: (optional) Base branch to create the feature branch from (e.g., `stage`, `main`, `master`). If not provided, prompt the user. Only used for in_progress features.

## Steps

1. Validate scratch/features/ exists, if not inform user to run /ws-init
2. Create scratch/features/{name}/ directory
3. Create spec.md based on status:

**3a. If status is `in_progress`:**

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

**3b. If status is `pending` (default):**

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

4. **Create branch (in_progress only, skip for pending)**

   Branch creation only applies when status is `in_progress`. Pending features defer branch creation to `/start-feature`.

   - Ask the user for a branch name (feature name != branch name on purpose)
   - If `base_branch` was provided as an argument, use it. Otherwise, ask the user for the base branch (e.g., `stage`, `main`, `master`). Do NOT auto-detect with `git branch -r` — it's too slow on large repos.
   - Run: `git fetch origin {base} && git checkout -b {branch_name} origin/{base}`
   - If the user says they already have a branch or want to skip, just record the branch name (or leave it empty) and move on

5. Create facts.md:

```markdown
# {name} facts

## Branch

branch: {branch_name or "pending"}
base: {base_branch or "tbd"}

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

6. Create meta.json:

```json
{
  "name": "{name}",
  "status": "{status}",
  "branch": "{branch_name or ""}",
  "base_branch": "{base_branch or ""}",
  "builds_on": ["{builds_on}"],
  "beta_flag": "",
  "created": "{today's date}",
  "last_session": "{today's date}"
}
```

7. Update scratch/features/_index.md:
   - Add new row to the appropriate table (Pending Features for `pending`, Active Features for `in_progress`)
   - Format: `| [{name}]({name}/) | {status} | | {builds_on or "-"} |`

8. Display the created structure and remind user to fill in the templates.
   - If `pending` (default): note that `/start-feature {name}` will transition it to `in_progress` and create the branch when ready.
   - If `in_progress`: confirm the branch checkout.
