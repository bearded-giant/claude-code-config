Create a new feature folder with templates.

## Arguments

- name: Feature name in kebab-case (e.g., "jwt-session-enforcement")
- builds_on: (optional) Parent feature this depends on
- pending: (optional) If "pending" is passed as an argument or the user says "stub", "pending", or "backlog", create the feature with `status: pending` instead of `in_progress`. Use a lighter spec template (see step 3b). Skip branch creation for pending features.

## Steps

1. Validate scratch/features/ exists, if not inform user to run /ws-init
2. Create scratch/features/{name}/ directory
3. Create spec.md based on status:

**3a. If status is `in_progress` (default):**

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

**3b. If status is `pending`:**

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
   - Auto-detect the base branch: check which of `stage`, `main`, `master` exists as a remote branch (`git branch -r`). Suggest the first match, let user override.
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
   - Add new row to the appropriate table (Active Features for `in_progress`, or a new Pending/Backlog section for `pending`)
   - Format: `| [{name}]({name}/) | {status} | | {builds_on or "-"} |`

8. Display the created structure and remind user to fill in the templates.
   - If `pending`: note that `/start-feature {name}` will transition it to `in_progress` and create the branch when ready.
   - If `in_progress`: confirm the branch checkout.
