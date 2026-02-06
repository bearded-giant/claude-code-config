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

4. **Update feature index**

   In `scratch/features/_index.md`, change the feature's status from `in_progress` to `paused`.

5. **Update meta.json** (if it exists)

   ```json
   {
     "status": "paused",
     "last_session": "{today's date}"
   }
   ```

6. **Update plans/current.md**

   - Clear active steps for this feature
   - Leave a one-liner: `Paused: {feature} - see features/{feature}/spec.md for resumption notes`

7. **Report**

   ```
   Feature '{feature}' paused.

   Updated:
     - spec.md (status -> paused, added resumption notes)
     - _index.md (status -> paused)
     - plans/current.md (cleared active steps)

   Resume with: /reopen-feature {feature}
   ```

## Rules

- Do NOT create any new files
- Do NOT modify code files, only scratch workspace files
- Read every file before modifying it
- Resumption notes should be brief but sufficient to pick up cold
- Keep all updates terse and factual per workspace output rules
