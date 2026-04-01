---
description: "Start a pending feature: promote to in_progress, expand spec, set as active work"
argument-hint: "[feature-name] [base-branch]"
---

# Start Feature

Transition a pending feature to in_progress. Expands the minimal stub into a full working spec and creates/checks out the feature branch.

## Arguments

- feature: (optional) Feature name in kebab-case. If not provided, list all pending features and ask which to start.
- base_branch: (optional) Base branch to create the feature branch from (e.g., `stage`, `main`, `master`). If not provided, prompt the user.

## Steps

1. **Find pending features**

   Read `.giantmem/features/features.json` and identify all features with status `pending`.

   - If no argument provided and multiple pending features exist: list them and ask the user which one to start
   - If no argument provided and exactly one pending feature exists: confirm with the user, then proceed
   - If no pending features exist: inform the user and stop
   - If argument provided: validate `.giantmem/features/{feature}/` exists and status is `pending`

2. **Read current state**

   Read these files (do not proceed without reading them first):
   - `.giantmem/features/{feature}/spec.md`
   - `.giantmem/features/{feature}/facts.md`
   - `.giantmem/features/{feature}/meta.json` (if it exists)
   - `.giantmem/features/_index.md`
   - `.giantmem/plans/current.md`

3. **Create or checkout branch**

   Check meta.json and facts.md for an existing `branch` value.

   **If no branch is set (typical for pending stubs):**
   - Ask the user for a branch name (feature name and branch name are intentionally decoupled)
   - If `base_branch` was provided as an argument, use it. Otherwise, ask the user for the base branch (e.g., `stage`, `main`, `master`). Do NOT auto-detect with `git branch -r` — it's too slow on large repos.
   - Run: `git fetch origin {base} && git checkout -b {branch_name} origin/{base}`

   **If a branch is already set:**
   - Check if the branch exists locally (`git branch --list {branch_name}`)
   - If it exists: `git checkout {branch_name}`
   - If it doesn't exist locally but exists on remote: `git fetch origin && git checkout -b {branch_name} origin/{branch_name}`
   - If it doesn't exist anywhere: treat as "no branch" and prompt for creation

3b. **Frontend (dual-repo) prompt**

   After backend branch setup, check if `meta.json` already has `frontend.enabled: true`. If so, skip the prompt and handle the existing frontend config.

   If no frontend config exists, ask:

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
   - Update meta.json, facts.md, and features.json with frontend details (see `/new-feature` for the frontend data model)

   **If no:** set `frontend` to `null` in meta.json/features.json.

4. **Expand spec.md**

   - Change `status: pending` to `status: in_progress`
   - Add `started: {today's date}` after the `created:` line
   - Preserve the existing `## Purpose` and `## Discovery Context` content (this is the reason the feature was stubbed)
   - Add the full working sections that the pending template omitted:

   ```
   ## Scope

   <!-- what's included and what's out of scope -->

   ## Key Decisions

   <!-- architectural decisions made, with rationale -->

   ## Acceptance Criteria
   (keep existing criteria, add placeholders if needed)

   ## Files Modified

   <!-- list key files created/modified -->
   ```

   - If the spec already has these sections (user may have filled them in while pending), leave them as-is

5. **Update facts.md**

   - Update the `## Branch` section with the branch name and base:
     ```
     branch: {branch_name}
     base: {base_branch}
     ```

6. **Update feature index**

   In `.giantmem/features/_index.md`, change the feature's status from `pending` to `in_progress`.

7. **Update meta.json** (if it exists)

   ```json
   {
     "status": "in_progress",
     "branch": "{branch_name}",
     "base_branch": "{base_branch}",
     "last_session": "{today's date}"
   }
   ```

8. **Update features.json cache**

   Read `.giantmem/features/features.json`, update the feature entry:

   ```json
   {
     "status": "in_progress",
     "branch": "{branch_name}",
     "base_branch": "{base_branch}",
     "last_session": "{today's date}"
   }
   ```

   Write the updated JSON back to `.giantmem/features/features.json`.

9. **Update plans/current.md**

   Set this feature as the active work. Include any context from the `## Discovery Context` section in the spec so the session has immediate context.

10. **Report**

   ```
   Feature '{feature}' started.

   Branch: {branch_name} (from {base_branch})
   Frontend: {frontend_branch at ~/dev/javascript/frontend-wt/{frontend_branch}, or "no"}

   Updated:
     - spec.md (status -> in_progress, expanded template)
     - facts.md (branch recorded)
     - _index.md (status -> in_progress)
     - features.json (cache updated)
     - plans/current.md (set as active)

   Discovery context:
     {brief summary of why this was stubbed}
   ```

## Rules

- Do NOT create any new files (except the git branch)
- Do NOT modify code files, only scratch workspace files
- Read every file before modifying it
- Preserve all content from the pending stub — it's discovery context that matters
- Keep all updates terse and factual per workspace output rules
