---
description: "Pause current feature: mark as paused, capture context for later resumption"
argument-hint: "[feature-name] (optional, inferred from plans/current.md)"
---

# Pause Feature

Pause an in-progress feature to switch context. Captures enough state to resume later.

## Arguments

- feature: (optional) Feature name in kebab-case. If not provided, infer from `scratch/plans/current.md` or ask.

## Steps

1. **Identify the feature**

   If no argument provided:
   - Read `scratch/plans/current.md` for active feature context
   - If unclear, ask the user

   Validate `scratch/features/{feature}/` exists with spec.md.

2. **Read current state**

   Read these files (do not proceed without reading them first):
   - `scratch/features/{feature}/spec.md`
   - `scratch/features/{feature}/facts.md`
   - `scratch/features/_index.md`
   - `scratch/plans/current.md`

   Verify the feature status is `in_progress`. If `complete` or already `paused`, inform the user and stop.

3. **Update spec.md**

   - Change `status: in_progress` to `status: paused`
   - Add `paused: {today's date}` after the `created:` line
   - Under `## Key Decisions`, append a `### Resumption Notes` subsection with:
     - What was in progress when paused
     - Next steps to pick up (infer from plans/current.md)
     - Any blockers or open questions

4. **Update facts.md**

   - Ensure all current values are accurate (beta flags, config keys, endpoints, key files, test commands)
   - Remove any placeholder or template text that was never filled in
   - Add a `## Paused State` section at the bottom with:
     - Last known working state (e.g., "endpoints wired but untested", "model done, API in progress")
     - Any partial work not yet captured elsewhere (draft config values, WIP file paths)
   - This section gets removed on `/reopen-feature`

5. **Update feature index**

   In `scratch/features/_index.md`, change the feature's status from `in_progress` to `paused`.

6. **Update meta.json** (if it exists)

   ```json
   {
     "status": "paused",
     "last_session": "{today's date}"
   }
   ```

7. **Update features.json cache**

   Read `scratch/features/features.json`, update the feature entry:

   ```json
   {
     "status": "paused",
     "last_session": "{today's date}"
   }
   ```

   Write the updated JSON back to `scratch/features/features.json`.

8. **Update plans/current.md**

   - Clear active steps for this feature
   - Leave a one-liner: `Paused: {feature} - see features/{feature}/spec.md for resumption notes`

9. **Report**

   ```
   Feature '{feature}' paused.

   Updated:
     - spec.md (status -> paused, added resumption notes)
     - facts.md (snapshot current state, added paused state)
     - _index.md (status -> paused)
     - features.json (cache updated)
     - plans/current.md (cleared active steps)

   Resume with: /reopen-feature {feature}
   ```

## Rules

- Do NOT create any new files
- Do NOT modify code files, only scratch workspace files
- Read every file before modifying it
- Resumption notes should be brief but sufficient to pick up cold
- Keep all updates terse and factual per workspace output rules
