---
description: "Reopen a completed feature: set back to in_progress, update index and tracking"
argument-hint: "[feature-name] (optional, inferred from context)"
---

# Reopen Feature

Reopen a previously completed or paused feature for additional work.

## Arguments

- feature: (optional) Feature name in kebab-case. If not provided, ask.

## Steps

1. **Identify the feature**

   If no argument provided, ask the user which feature to reopen.

   Validate `.giantmem/features/{feature}/` exists with spec.md.

2. **Read current state**

   Read these files (do not proceed without reading them first):
   - `.giantmem/features/{feature}/spec.md`
   - `.giantmem/features/{feature}/facts.md`
   - `.giantmem/features/{feature}/meta.json` (if it exists)
   - `.giantmem/features/_index.md`
   - `.giantmem/plans/current.md`

   Verify the feature status is `complete` or `paused`. If already `in_progress`, inform the user and stop.

3. **Checkout feature branch**

   Check meta.json and facts.md for the `branch` value.

   **If a branch is recorded:**
   - Check if the branch exists locally (`git branch --list {branch_name}`)
   - If it exists: `git checkout {branch_name}`
   - If it doesn't exist locally but exists on remote: `git fetch origin && git checkout -b {branch_name} origin/{branch_name}`
   - If it doesn't exist anywhere (e.g., branch was deleted after merge): ask the user whether to create a new branch or skip

   **If no branch is recorded:**
   - Ask the user if they want to create a branch now
   - If yes: ask for branch name and base branch (do NOT auto-detect with `git branch -r` — too slow on large repos)
   - Or skip if they prefer to handle git manually

4. **Update spec.md**

   - Change `status: complete` or `status: paused` to `status: in_progress`
   - Remove the `completed: {date}` line (if reopening from complete)
   - Remove the `paused: {date}` line (if reopening from paused)
   - If reopening from complete: ask which acceptance criteria need rework, uncheck those
   - If reopening from paused: check for `### Resumption Notes` and surface them to the user

   In `facts.md`:
   - If reopening from paused: remove the `## Paused State` section (it was a snapshot, no longer relevant)
   - Update `## Branch` section if a new branch was created

5. **Update feature index**

   In `.giantmem/features/_index.md`, change the feature's status from `complete` or `paused` to `in_progress`.

6. **Update meta.json** (if it exists)

   ```json
   {
     "status": "in_progress",
     "branch": "{branch_name}",
     "last_session": "{today's date}"
   }
   ```

7. **Update features.json cache**

   Read `.giantmem/features/features.json`, update the feature entry:

   ```json
   {
     "status": "in_progress",
     "branch": "{branch_name}",
     "last_session": "{today's date}"
   }
   ```

   Write the updated JSON back to `.giantmem/features/features.json`.

8. **Update plans/current.md**

   - Set this feature as the active work
   - If a `## Completed` section lists this feature, move it back to active

9. **Report**

   ```
   Feature '{feature}' reopened.

   Branch: {branch_name or "none"}

   Updated:
     - spec.md (status -> in_progress, removed completed date)
     - _index.md (status -> in_progress)
     - features.json (cache updated)
     - plans/current.md (set as active)

   Review acceptance criteria and update as needed.
   ```

## Rules

- Do NOT create any new files (except git branches if needed)
- Do NOT modify code files, only scratch workspace files
- Read every file before modifying it
- Keep all updates terse and factual per workspace output rules
