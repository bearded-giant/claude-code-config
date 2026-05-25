---
description: "Mark a feature complete: update spec, facts, index, and current plan"
argument-hint: "[feature-name] [--quick] (feature optional, inferred from plans/current.md)"
---

# Complete Feature

Mark a feature as complete by updating all workspace tracking files.

## Arguments

- feature: (optional) Feature name in kebab-case. If not provided, infer from `.giantmem/plans/current.md` or ask.
- `--quick`: (optional) Skip full ceremony. Only update status to complete, set completed date, and update feature index + features.json. Use when feature was finished elsewhere or full update isn't needed.

## Quick Mode

If `--quick` flag is passed, run only these steps:

1. **Identify the feature** (same as step 1 below)
2. **Read minimal state**: `spec.md`, `_index.md`, `features.json`, `meta.json` (if exists)
3. **Update spec.md**: change `status: in_progress` to `status: complete`, add `completed: {today's date}` after `created:` line. Do NOT modify acceptance criteria, scope, architecture, or files sections.
4. **Update `_index.md`**: change status to `complete`
5. **Update `features.json`**: set `status: complete`, `last_session: {today's date}`
6. **Update `meta.json`** (if exists): set `status: complete`, `last_session: {today's date}`
7. **Report**:
   ```
   Feature '{feature}' marked complete (quick mode).
   Updated: spec.md (status + completed date), _index.md, features.json, meta.json
   Skipped: facts.md, plans/current.md, domain refresh, paired-counterpart check
   ```

Skip all remaining steps below. Done.

## Full Mode (default)

## Steps

1. **Identify the feature**

   If no argument provided:
   - Read `.giantmem/plans/current.md` for active feature context
   - If unclear, ask the user

   Validate `.giantmem/features/{feature}/` exists with spec.md and facts.md.

2. **Read current state**

   Read these files (do not proceed without reading them first):
   - `.giantmem/features/{feature}/proposal.md` (or legacy `spec.md` symlink)
   - `.giantmem/features/{feature}/facts.md`
   - `.giantmem/features/{feature}/specs/` — enumerate delta-specs by domain
   - `.giantmem/features/{feature}/plan_context.json` (if it exists)
   - `.giantmem/features/_index.md`
   - `.giantmem/plans/current.md`

3. **Merge delta-specs into source-of-truth (loose-rules — skippable)**

   Per migration_plan decision 3, this step never blocks completion. Three paths:

   - `features/{feature}/specs/` empty or missing → silent skip
   - `--no-merge` flag passed → skip merge but continue completion. Reason should be captured in step 3b.
   - delta-specs present + no `--no-merge` → run:

     ```bash
     python3 ~/dev/giant-tooling/workspace/scripts/merge_delta_spec.py {feature} \
         --reason "$REASON"
     ```

     The script:
     - Walks `features/{feature}/specs/{domain}/spec.md` for each domain
     - Applies `ADDED` → append, `MODIFIED` → replace by Requirement name, `REMOVED` → delete
     - Creates `.giantmem/specs/{domain}/spec.md` if missing
     - Flips each delta-spec `status: ready` → `status: done` in frontmatter
     - Appends entries to per-feature `spec_history.md` AND repo-level `.giantmem/specs/_history.md`
     - Updates `.giantmem/specs/_index.md` with new domains
     - Is idempotent — re-running on already-merged deltas reports `skipped idempotent` and skips history/index writes

   **3a. Dry-run first** (recommended for first contact): append `--dry-run`. Shows +/~/- counts per domain without writing.

   **3b. Capture `--reason`**: if interactive, prompt user for a one-line reason ("shipped", "scope cut", "moved to feature X", etc.). Non-interactive: pass `--reason "{feature} completion"`.

4. **Update proposal.md**

   - Add or update top-level frontmatter `status: done`
   - Add `completed: {today's date}` in frontmatter
   - Review legacy `## Acceptance Criteria` bullets (if any) and mark completed items `[x]`
   - If any acceptance criteria are NOT met AND no delta-specs exist, warn the user and ask whether to proceed
   - Update scope / approach sections to reflect final implementation

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

10. **Check paired-counterpart status (if cross-repo feature)**

   Read the feature's `meta.json` or `features.json` entry. If `frontend.enabled` is `true` (legacy field name — represents any paired counterpart, BE or FE):

   - Read `frontend.worktree` from the JSON — this is the absolute counterpart worktree path (no longer hardcoded to `~/dev/javascript/frontend-wt/`)
   - Check if that path still exists on disk
   - Remind the user that the counterpart branch needs its own MR/PR separately
   - Report `frontend.branch` and `frontend.worktree` so they can handle it
   - Do NOT remove the counterpart worktree or branch — that's the user's responsibility

11. **Rebuild artifact index**

   Run `giantmem artifact reindex` so the delta-spec status flip + source-spec
   updates are reflected in `.giantmem/artifacts.json`. Soft-fail if binary
   missing — print warning, continue.

12. **Report**

   ```
   Feature '{feature}' marked complete.

   Merge:
     - Domains merged: {list, or "none (no delta-specs)"}
     - Added/Modified/Removed Requirements: +N ~N -N
     - History: features/{feature}/spec_history.md + .giantmem/specs/_history.md

   Updated:
     - proposal.md (status -> done, completed date)
     - facts.md (commands, files, benchmarks)
     - _index.md (status -> complete)
     - features.json (cache updated)
     - plans/current.md (moved to completed, transient cleared)
     - artifacts.json (reindexed)
     - domains: {list of refreshed domains, or "none (no domain changes detected)"}

   Unchecked criteria: {count or "none"}
   Paired counterpart: {frontend.branch at frontend.worktree — needs separate MR, or "n/a"}
   ```

## Rules

- Do NOT create any new files
- Do NOT modify code files, only scratch workspace files
- Read every file before modifying it
- If acceptance criteria have unchecked items, warn but let user decide
- Keep all updates terse and factual per workspace output rules
