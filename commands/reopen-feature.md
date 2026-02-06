---
description: "Reopen a completed feature: set back to in_progress, update index and tracking"
argument-hint: "[feature-name] (optional, inferred from context)"
---

# Reopen Feature

Reopen a previously completed feature for additional work.

## Arguments

- feature: (optional) Feature name in kebab-case. If not provided, ask.

## Steps

1. **Identify the feature**

   If no argument provided, ask the user which feature to reopen.

   Validate `scratch/features/{feature}/` exists with spec.md.

2. **Read current state**

   Read these files (do not proceed without reading them first):
   - `scratch/features/{feature}/spec.md`
   - `scratch/features/{feature}/facts.md`
   - `scratch/features/_index.md`
   - `scratch/plans/current.md`

   Verify the feature status is `complete` or `paused`. If already `in_progress`, inform the user and stop.

3. **Update spec.md**

   - Change `status: complete` or `status: paused` to `status: in_progress`
   - Remove the `completed: {date}` line (if reopening from complete)
   - Remove the `paused: {date}` line (if reopening from paused)
   - If reopening from complete: ask which acceptance criteria need rework, uncheck those
   - If reopening from paused: check for `### Resumption Notes` and surface them to the user

4. **Update feature index**

   In `scratch/features/_index.md`, change the feature's status from `complete` or `paused` to `in_progress`.

5. **Update meta.json** (if it exists)

   ```json
   {
     "status": "in_progress",
     "last_session": "{today's date}"
   }
   ```

6. **Update plans/current.md**

   - Set this feature as the active work
   - If a `## Completed` section lists this feature, move it back to active

7. **Report**

   ```
   Feature '{feature}' reopened.

   Updated:
     - spec.md (status -> in_progress, removed completed date)
     - _index.md (status -> in_progress)
     - plans/current.md (set as active)

   Review acceptance criteria and update as needed.
   ```

## Rules

- Do NOT create any new files
- Do NOT modify code files, only scratch workspace files
- Read every file before modifying it
- Keep all updates terse and factual per workspace output rules
