---
description: "Mark a feature complete: update spec, facts, index, and current plan"
argument-hint: "[feature-name] (optional, inferred from plans/current.md)"
---

# Complete Feature

Mark a feature as complete by updating all workspace tracking files.

## Arguments

- feature: (optional) Feature name in kebab-case. If not provided, infer from `.giantmem/plans/current.md` or ask.

## Steps

1. **Identify the feature**

   If no argument provided:
   - Read `.giantmem/plans/current.md` for active feature context
   - If unclear, ask the user

   Validate `.giantmem/features/{feature}/` exists with spec.md and facts.md.

2. **Read current state**

   Read these files (do not proceed without reading them first):
   - `.giantmem/features/{feature}/spec.md`
   - `.giantmem/features/{feature}/facts.md`
   - `.giantmem/features/{feature}/plan_context.json` (if it exists)
   - `.giantmem/features/_index.md`
   - `.giantmem/plans/current.md`

3. **Update spec.md**

   - Change `status: in_progress` to `status: complete`
   - Add `completed: {today's date}` after the `created:` line
   - Review acceptance criteria: mark all completed items as `[x]`
   - If any criteria are NOT met, warn the user and ask whether to proceed or address them first
   - Update scope, architecture, and files sections to reflect final implementation (not the plan, the result)

4. **Update facts.md**

   - Ensure all commands reflect final syntax (not draft/placeholder)
   - Ensure key files list is accurate and complete
   - Add benchmarks or metrics if available from the session
   - Remove any placeholder or template text

5. **Update feature index**

   In `.giantmem/features/_index.md`, change the feature's status from `in_progress` to `complete`.

6. **Update meta.json** (if it exists)

   ```json
   {
     "status": "complete",
     "last_session": "{today's date}"
   }
   ```

7. **Update features.json cache**

   Read `.giantmem/features/features.json`, update the feature entry:

   ```json
   {
     "status": "complete",
     "last_session": "{today's date}"
   }
   ```

   Write the updated JSON back to `.giantmem/features/features.json`.

8. **Update plans/current.md**

   - Move the feature to a `## Completed` section
   - Clear any steps related to this feature from active work

9. **Update domain JSONs (if domains were used)**

   Check if `.giantmem/features/{feature}/plan_context.json` exists. If it does:

   - Read it to get the `domains_referenced` list
   - Read `.giantmem/domains/_index.json`
   - For each referenced domain, check if files under its `key_paths` were modified during this feature:
     ```
     git log --name-only -- {key_paths}
     ```
     Compare against what's in the domain JSON's `key_files`.
   - If significant changes were made to a domain's files, re-explore that domain using the same approach as `/update-domains`:
     - Launch a code-explorer agent for each stale domain
     - Update the domain JSON with fresh exploration data
     - Append this feature to the domain's `explored_for_features`
     - Update `last_explored` to today
   - Update `.giantmem/domains/_index.json` with refreshed dates and feature references
   - If no domains were changed, skip silently

10. **Check frontend status (if dual-repo feature)**

   Read the feature's `meta.json` or `features.json` entry. If `frontend.enabled` is `true`:

   - Check if the frontend worktree still exists at the recorded path (`~/dev/javascript/frontend-wt/{frontend_branch}`)
   - Remind the user that the frontend branch needs its own MR/PR separately
   - Report the frontend branch name and worktree path so they can handle it
   - Do NOT remove the frontend worktree or branch — that's the user's responsibility

11. **Report**

   ```
   Feature '{feature}' marked complete.

   Updated:
     - spec.md (status, acceptance criteria, completed date)
     - facts.md (commands, files, benchmarks)
     - _index.md (status -> complete)
     - features.json (cache updated)
     - plans/current.md (moved to completed)
     - domains: {list of refreshed domains, or "none (no domain changes detected)"}

   Unchecked criteria: {count or "none"}
   Frontend: {frontend_branch at ~/dev/javascript/frontend-wt/{frontend_branch} — needs separate MR, or "n/a"}
   ```

## Rules

- Do NOT create any new files
- Do NOT modify code files, only scratch workspace files
- Read every file before modifying it
- If acceptance criteria have unchecked items, warn but let user decide
- Keep all updates terse and factual per workspace output rules
