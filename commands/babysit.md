---
description: Auto-address open review threads on the MR for the CURRENT worktree branch. Scoped to one MR — the one whose source branch == current branch. Idempotent — safe to /loop inside a worktree. Trigger phrases - "babysit this MR", "address review comments", "/babysit", or invoked via `/loop 5m /babysit`.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

Address open review comments on the MR for **this** worktree's branch.

## Worktree scoping model

This command is worktree-scoped by design. One session/loop handles exactly one MR — the one matching the current branch. Run separate `/loop /babysit` instances in each worktree to cover multiple MRs in parallel.

## Preconditions

- `glab auth status` succeeds (skip + log if not)
- In a git repo with a GitLab remote (skip + log if not)
- Current branch is **not** `main` / `master` / `stage` — if it is, exit clean with `not on a feature branch — nothing to babysit`
- `git status --porcelain` is clean — if dirty, **abort** and report (do not stash user work)

## Steps

1. **Resolve current branch and MR** —
   ```
   BRANCH="$(git branch --show-current)"
   glab mr list --source-branch="$BRANCH" -F json   # opened is the default state
   ```
   - Zero results → exit clean: `no open MR for branch <BRANCH>`
   - Multiple results → exit clean: `ambiguous: <n> MRs from this branch — manual triage needed`
   - One result → proceed. Capture `iid`, `project_id`, `web_url`.

2. **Fetch unresolved discussions**:
   ```
   glab api "projects/<project_id>/merge_requests/<iid>/discussions" --paginate
   ```
   Keep a thread if `system=false` AND it still requests a change (`resolved=false`, or a `resolvable=false` MR-level note that asks for one) AND **either**:
   - its last non-system note author is someone other than you, **or**
   - any note you authored on it contains the token `[babysit-do]`.

   Skip a thread whose last note is yours and carries **no** `[babysit-do]` token — you are mid-conversation, leave it. Zero kept threads → exit clean.

   `[babysit-do]` is your opt-in handle. A reply you write as `[babysit-do] <instructions>` marks that thread for action; the text after the token becomes the spec and overrides classification.

3. **Classify each kept thread** before touching code. Read the thread context (file path + line if present). Bucket into:
   - `directed` — you replied with `[babysit-do] <instructions>`. Implement exactly what your instruction says; the reviewer's note is background. Highest priority, overrides the buckets below.
   - `actionable_simple` — rename, typo, missing test case, obvious null check, dead code, lint-style nit. Safe to one-shot.
   - `actionable_complex` — design or refactor request. Split by how concrete the direction is:
     - **concrete direction** (reviewer named the target, e.g. "use request hooks for `internal_chat_api_bp`", "move to its own blueprint") → attempt it, scoped strictly to what was asked.
     - **ambiguous / open question** (e.g. "is this the right layer?", "should this live elsewhere?") → reply `[babysit] needs your input — leaving for human` and skip.
   - `informational` — "looks good", "nit just FYI", no requested change. Skip.

4. **Sync branch first** — once, before any edits:
   ```
   git fetch origin
   git pull --rebase --no-edit
   ```
   On conflict → abort rebase, post one summary thread note `[babysit] rebase conflict — manual fixup needed`, exit clean.

5. **Plan-gate** each `directed` and `actionable_complex` thread before editing (`actionable_simple` skips the gate — always safe to one-shot):
   1. Write a 2–4 step plan from the reviewer comment + your `[babysit-do]` directive. Spec source: `directed` → your `[babysit-do]` text; concrete `actionable_complex` → the reviewer's stated direction.
   2. Classify the plan **CLEAN** vs **NEEDS-SIGN-OFF** (moderate bar). NEEDS-SIGN-OFF if the plan would:
      - change a public contract (response code, route, payload shape), **or**
      - alter request/response **precedence or ordering** — e.g. a `before_request` hook that runs ahead of an auth view decorator, middleware reordering, changing which check fires first, **or**
      - touch a repo **High-Risk File** (see the repo's CLAUDE.md High-Risk Files), **or**
      - be unverifiable by existing tests or a trivially-added one.
      CLEAN otherwise — including multi-file moves/renames the test suite already covers.
   3. **NEEDS-SIGN-OFF** → post the plan as a thread note prefixed `[babysit] plan — needs your sign-off`, leave the thread **unresolved**, and **do not touch code**. (The attention signal in step 7 fires at end of run.)

6. **Execute** each CLEAN thread (and every `actionable_simple`):
   1. Build the edit, scoped to exactly what was asked — do not expand into adjacent refactors.
   2. Run `py-check` / `ts-check` skill on touched files.
   3. Commit using caveman-commit format. Subject prefix `review:` (e.g., `review: rename foo to bar`). If the repo's commit-msg hook needs a JIRA key, prefix it (derive from branch name or sibling commits). If push is then rejected **by the commit-msg / pre-push policy hook only** (not a non-fast-forward), retry once with `git push --no-verify` — py-check already ran in 6.2.
   4. Push: `git push`
   5. Reply on thread:
      ```
      glab api -X POST "projects/<project_id>/merge_requests/<iid>/discussions/<discussion_id>/notes" -f body="addressed in <short-sha>"
      ```
   6. Resolve thread if `resolvable=true`:
      ```
      glab api -X PUT "projects/<project_id>/merge_requests/<iid>/discussions/<discussion_id>" -f resolved=true
      ```
      MR-level notes (`resolvable=false`) can't be resolved via API — reply only.

7. **Raise attention if anything was left for you** — once, at end of run. If any thread was deferred (NEEDS-SIGN-OFF, `actionable_complex` ambiguous, push rejected, pipeline red, rebase conflict):
   ```
   python3 ~/.claude/hooks/request_attention.py "MR !<iid> (<branch>): <n> thread(s) need your sign-off"
   ```
   Flags the tmux window + sends a desktop notification when the session stops. If babysit fully handled every thread, do **not** call it — silent success.

8. **Pipeline check** — after final push, query:
   ```
   glab api "projects/<project_id>/pipelines?ref=$BRANCH&order_by=updated_at&per_page=1"
   ```
   If pipeline newly red from this push, leave a thread note `[babysit] pipeline red after my fix — <job-url>`, raise attention (step 7), and bail. If pipeline green or unrelated red, no note needed.

## Safety rails

- **Never push to** `main` / `master` / `stage`. Step 0 should already prevent this.
- **Never force-push.** If `git push` rejects (non-fast-forward), do not `--force` — post one summary note `[babysit] push rejected — branch diverged`, exit clean.
- **Never amend** existing commits.
- **Never check out a different branch.** Stay on `$BRANCH` for the whole run.
- **Cap**: max 5 threads addressed per run. Anything more → user attention warranted; post a summary note and exit.
- **Skip if MR is Draft** unless MR description contains `[babysit-ok]`.

## Output

Single line:
```
MR !1234 (feat-xyz): 2 addressed, 1 needs sign-off, pipeline green
```
If anything needs sign-off, step 7 already fired the attention signal — name the deferred threads + their URLs below the summary so the user can jump straight there.

Followed by deferred-thread URLs (so user can jump straight there).

## Failure modes — exit clean, never error

- glab auth expired → log + exit 0
- network error → log + exit 0
- merge conflict → post note + exit 0
- ambiguous review thread → reply on thread + skip
- multiple MRs from same branch → log + exit 0

Loop runners require clean exits. Stack traces here kill the loop next iteration.
