---
description: "Create a new feature folder with templates. Auto-detects status: pending if another feature is in_progress, otherwise in_progress."
argument-hint: "<name> [--branch=X] [--base=Y] [--builds-on=Z] [--paired]"
---

Create a new feature folder with templates. Status is auto-detected:
- If another feature is already `in_progress` → new feature is `pending` (stub for later)
- If no feature is `in_progress` → new feature is `in_progress` (start working immediately)

## Arguments

`$ARGUMENTS` may arrive in two forms:

**Interactive form** (positional, legacy):
- `name [builds_on] [base_branch]`

**Non-interactive form** (named flags, for `claude -p` / `ccmd`):
- `name [--branch=<git-branch>] [--base=<base-branch>] [--builds-on=<parent>] [--paired] [--skip-checkout]`

Parse rules:
- First positional token = feature name (kebab-case, required)
- Any `--key=value` token → assign to that key
- Bare `--paired` flag → counterpart-repo involvement = true (only honored if repo has a linked counterpart, see step 6)
- Bare `--no-paired` flag → counterpart involvement = false (explicit, this-repo-only)
- If `--paired` and `--no-paired` both absent AND running interactively → prompt (step 6)
- If both absent AND running non-interactively (no TTY) → default to this-repo-only

Fields:
- name: Feature name in kebab-case (e.g., "jwt-session-enforcement")
- builds_on / --builds-on: (optional) Parent feature this depends on
- branch_name / --branch: (optional) Git branch name. Defaults to current HEAD (`git rev-parse --abbrev-ref HEAD`). Interactive: prompt with current HEAD as default. Non-interactive: silently use current HEAD.
- base_branch / --base: (optional) Base branch (e.g., `stage`, `main`, `master`, `develop`). Defaults to repo's remote-default branch (`git symbolic-ref --short refs/remotes/origin/HEAD` → strip `origin/`). If origin HEAD is not set, fall back order: `develop` → `stage` → `main` → `master`, picking the first that exists on `origin`. Interactive: prompt with detected default. Non-interactive: silently use detected default. If nothing resolves, fail: `new-feature: could not detect base branch, pass --base explicitly`.
- --paired: opt-in flag for paired-repo involvement (cross-repo branch in linked counterpart). Default = this-repo-only.
- --skip-checkout: opt-in flag to skip all git branch resolution. Only records `--branch` value. Use when caller already has the branch checked out and wants no git side effects. (Mostly redundant now that step 5 auto-detects current HEAD, but still respected.)

**Sanity guard:** if resolved `{branch_name}` equals resolved `{base_branch}`, fail: `new-feature: feature branch and base branch are the same ('{branch}') — refusing to create feature on a base branch`. Override by passing `--branch=` explicitly to a different branch.

**Note on schema naming:** The persisted JSON field is still `frontend.*` (in meta.json and features.json) for back-compat with `/complete-feature`, `/start-feature`, `/list-features`, `/pause-feature`, `/reopen-feature`. The CLI/UX uses `--paired` because the linkage is bidirectional. Treat `frontend` in JSON as a misnomer for "paired counterpart" until those consumers are updated.

## Steps

1. Validate .giantmem/features/ exists, if not inform user to run /ws-init

2. **Determine status automatically**

   Read `.giantmem/features/features.json` (create it as `{}` if it doesn't exist).

   Check if any feature in the cache has `"status": "in_progress"`.
   - If yes → this feature's status is `pending`
   - If no → this feature's status is `in_progress`

   Tell the user which status was auto-selected and why (e.g., "Creating as pending — feature X is currently in_progress" or "Creating as in_progress — no active feature").

3. Create .giantmem/features/{name}/ directory + .giantmem/features/{name}/specs/ subdirectory (empty for now).

4. Create proposal.md based on status. Reference template: `~/.claude/templates/proposal.md`. Behavior split: intent + scope + approach go in proposal.md; behavior contracts (Requirements + Scenarios) go in `features/{name}/specs/{domain}/spec.md` as delta-spec — written by user/Claude later, NOT by `/new-feature`.

**4a. If status is `in_progress`:**

```markdown
---
type: proposal
feature: {name}
status: ready
created: {today}
updated: {today}
---

# Proposal: {Title}

## Open Questions for User

<!--
ALWAYS at top. Numbered list. Mark each [BLOCKING] or [non-blocking].
Remove this section once empty. Buried questions get missed.
-->
1. ...

## Intent

<!-- one paragraph: the problem this solves -->

## Scope

In scope:
-

Out of scope:
-

## Approach

<!-- high-level technical direction. Implementation details belong in design.md. -->

## Behavior Deltas

Tracked separately in `features/{name}/specs/{domain}/spec.md` (delta-spec, `ADDED`/`MODIFIED`/`REMOVED`).
On `/complete-feature`, deltas merge into `.giantmem/specs/{domain}/spec.md` (source-spec).
```

**4b. If status is `pending`:**

Minimal stub. User is queuing this for later. Fill the Intent line with whatever discovery context they provided (don't leave the placeholder if they explained why).

```markdown
---
type: proposal
feature: {name}
status: draft
created: {today}
updated: {today}
---

# Proposal: {Title}

## Open Questions for User

<!--
ALWAYS at top. Numbered list. Mark each [BLOCKING] or [non-blocking].
Remove this section once empty. Buried questions get missed.
-->
1. ...

## Intent

{user's reason for queuing this, or "<!-- describe what this feature does and why -->" if none given}

## Discovery Context

{what prompted this stub — e.g., which feature was being worked on, what was discovered}

## Scope

In scope:
-

Out of scope:
-
```

**4c. Create features/{name}/tasks.md:**

```markdown
---
type: tasks
feature: {name}
status: draft
created: {today}
updated: {today}
---

# Tasks

<!--
status auto-derives from checkbox %:
  0%       = draft
  0 < x < 100% = ready
  100%     = done
no manual status updates needed — `giantmem artifact list -f {name}` reflects live %.
-->

## 1. {Section}

- [ ] 1.1 ...
```

**4d. Do NOT scaffold delta-specs.** `features/{name}/specs/` dir exists but stays empty until user writes behavior. `/complete-feature` skips merge step silently when empty (loose-rules per decisions).

5. **Resolve and check out branch (in_progress only, skip for pending)**

   Branch creation only applies when status is `in_progress`. Pending features defer branch creation to `/start-feature`.

   **5a. Resolve `{branch_name}`:**
   - If `--branch` passed, use it.
   - Else interactive: prompt with current HEAD as default.
   - Else non-interactive: use current HEAD (`git rev-parse --abbrev-ref HEAD`).

   **5b. Resolve `{base_branch}`:**
   - If `--base` passed, use it.
   - Else detect remote default: `git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||'`.
   - If unset, try `develop`, `stage`, `main`, `master` in that order, picking first that `git ls-remote --exit-code --heads origin {candidate}` succeeds on.
   - Interactive: prompt with detected default. Non-interactive: silently use detected default.
   - If nothing resolves, fail: `new-feature: could not detect base branch, pass --base explicitly`.

   **5c. Sanity guard:**
   - If `{branch_name}` == `{base_branch}`, fail: `new-feature: feature branch and base branch are the same ('{branch}') — refusing to create feature on a base branch. Pass --branch= explicitly.`

   **5d. Branch resolution (auto-detect existing branches):**

   1. Check current branch: `git rev-parse --abbrev-ref HEAD`. If it matches `{branch_name}`, branch is already checked out — record it and move on, do not run any git commands.
   2. Else check local: `git show-ref --verify --quiet refs/heads/{branch_name}`. If found → `git checkout {branch_name}`.
   3. Else check remote: `git ls-remote --exit-code --heads origin {branch_name}`. If found → `git fetch origin {branch_name} && git checkout -b {branch_name} origin/{branch_name}`.
   4. Else create from base: `git fetch origin {base} && git checkout -b {branch_name} origin/{base}`.
   5. If `--skip-checkout` flag present, short-circuit 1-4 — only record the branch name, run no git commands.

   Report which branch (always), base (always), and whether a new branch was created vs reused.

6. **Paired-counterpart prompt (in_progress only, skip for pending)**

   **6a. Determine if current repo has a paired counterpart.**

   `--paired` means this feature requires a parallel branch in a linked sibling repo (cross-repo). Intra-repo UI/harness work does NOT use `--paired`.

   Run `git rev-parse --show-toplevel` and match against this hardcoded bidirectional map:

   | Current path prefix | Paired counterpart root | Counterpart base | Worktree create cmd |
   |---|---|---|---|
   | `~/dev/python/cc-wt/` | `~/dev/javascript/frontend-wt/` | `master` | `fewta {branch} master` |
   | `~/dev/javascript/frontend-wt/` | `~/dev/python/cc-wt/` | `stage` | `cwta {branch} stage` |

   (`fewta` / `cwta` come from `~/dotfiles/shell/scripts/worktrees/wt-frontend.sh` and `wt-customcheckout.sh` — registered via `wt_register fewt` / `wt_register cwt`, where `<prefix>a` is the "add worktree" verb.)

   The `--base` flag refers to the CURRENT-repo base branch. The counterpart base is fixed per-row in the table above.

   If current worktree path does NOT start with a listed prefix → no counterpart available. Skip the rest of step 6, set `frontend.enabled = false`, move on. Do not prompt, even if `--paired` was passed (warn user the flag was ignored).

   **6b. Counterpart-capable repo, resolve intent.**

   - If `--no-paired` present → this-repo-only. Set `frontend.enabled = false`. Done.
   - If `--paired` present → counterpart involvement. Continue to 6c.
   - If neither flag present:
     - Interactive: prompt
       ```
       Does this feature include changes in the paired counterpart repo?
       1. No (this repo only)
       2. Yes
       ```
     - Non-interactive (no TTY): default to this-repo-only. Set `frontend.enabled = false`. Done.

   **6c. Counterpart involvement — create paired worktree.**

   - Look up the row for the current repo. `{counterpart_root}` and `{counterpart_base}` come from that row.
   - If interactive, ask for counterpart branch name (default: same as current-repo branch). Non-interactive: use current-repo branch name.
   - Try the row's worktree create cmd (e.g., `fewta {branch} master` for BE→FE, `cwta {branch} stage` for FE→BE).
   - If the helper is not on PATH, fall back to:
     ```bash
     cd {counterpart_root}.bare && git worktree add -b {counterpart_branch} ../{counterpart_branch} origin/{counterpart_base}
     ```
   - Record in JSON (using legacy `frontend.*` field name — see note in Arguments):
     - `frontend.enabled = true`
     - `frontend.branch = {counterpart_branch}`
     - `frontend.base_branch = {counterpart_base}`
     - `frontend.worktree = {counterpart_root}{counterpart_branch}`

7. Create facts.md (with frontmatter):

```markdown
---
type: facts
feature: {name}
status: ready
created: {today}
updated: {today}
---

# {name} facts

## Branch

branch: {branch_name or "pending"}
base: {base_branch or "tbd"}

## Paired Counterpart

paired: {true or false}
counterpart_branch: {counterpart_branch or "n/a"}
counterpart_worktree: {counterpart_root + counterpart_branch, or "n/a"}
counterpart_base: {counterpart_base or "n/a"}

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

When paired counterpart is enabled (field name stays `frontend` for back-compat):

```json
{
  "frontend": {
    "enabled": true,
    "branch": "{counterpart_branch}",
    "base_branch": "{counterpart_base}",
    "worktree": "{counterpart_root}{counterpart_branch}"
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
         "branch": "{counterpart_branch or ""}",
         "base_branch": "{counterpart_base or ""}",
         "worktree": "{counterpart_root + counterpart_branch, or ""}"
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
   - Format: `| [{name}]({name}/) | {status} | | {builds_on or "-"} | {paired counterpart branch if enabled, otherwise -} |`

12. **Rebuild `.giantmem/artifacts.json`** — run `giantmem artifact reindex` from the repo root. Captures the new `proposal.md` + `tasks.md` + `facts.md` (+ delta-specs once user populates `specs/`) as typed entries. Skip silently if `giantmem` binary not on PATH; print warning.

13. Display the created structure and confirm:
   - If `pending`: note that `/start-feature {name}` will transition it to `in_progress` and create the branch when ready.
   - If `in_progress`: confirm the branch checkout.
   - If paired counterpart enabled: confirm the counterpart worktree was created and show the path.
   - Run `giantmem artifact list -f {name}` and show the result so the user sees the new typed artifacts.
