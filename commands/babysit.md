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
   glab mr list --source-branch="$BRANCH" --state=opened --output=json
   ```
   - Zero results → exit clean: `no open MR for branch <BRANCH>`
   - Multiple results → exit clean: `ambiguous: <n> MRs from this branch — manual triage needed`
   - One result → proceed. Capture `iid`, `project_id`, `web_url`.

2. **Fetch unresolved discussions**:
   ```
   glab api "projects/<project_id>/merge_requests/<iid>/discussions" --paginate
   ```
   Filter: `resolved=false` AND `system=false` AND last note author != yourself. Zero actionable threads → exit clean.

3. **Classify each thread** before touching code. Read the thread context (file path + line if present). Bucket into:
   - `actionable_simple` — rename, typo, missing test case, obvious null check, dead code, lint-style nit. Safe to one-shot.
   - `actionable_complex` — design pushback, ambiguous scope, requires user judgment. **Reply with `[babysit] needs your input — leaving for human` and skip.**
   - `informational` — "looks good", "nit just FYI", no requested change. Skip.

4. **Sync branch first** — once, before any edits:
   ```
   git fetch origin
   git pull --rebase --no-edit
   ```
   On conflict → abort rebase, post one summary thread note `[babysit] rebase conflict — manual fixup needed`, exit clean.

5. **Per actionable_simple thread**:
   1. Make the edit. Run `py-check` / `ts-check` skill on touched files.
   2. Commit using caveman-commit format. Subject prefix `review:` (e.g., `review: rename foo to bar`).
   3. Push: `git push`
   4. Reply on thread:
      ```
      glab api -X POST "projects/<project_id>/merge_requests/<iid>/discussions/<discussion_id>/notes" -f body="addressed in <short-sha>"
      ```
   5. Resolve thread:
      ```
      glab api -X PUT "projects/<project_id>/merge_requests/<iid>/discussions/<discussion_id>" -f resolved=true
      ```

6. **Pipeline check** — after final push, query:
   ```
   glab api "projects/<project_id>/pipelines?ref=$BRANCH&order_by=updated_at&per_page=1"
   ```
   If pipeline newly red from this push, leave a thread note `[babysit] pipeline red after my fix — <job-url>` and bail. If pipeline green or unrelated red, no note needed.

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
MR !1234 (feat-xyz): 2 threads addressed, 1 deferred, pipeline green
```

Followed by deferred-thread URLs (so user can jump straight there).

## Failure modes — exit clean, never error

- glab auth expired → log + exit 0
- network error → log + exit 0
- merge conflict → post note + exit 0
- ambiguous review thread → reply on thread + skip
- multiple MRs from same branch → log + exit 0

Loop runners require clean exits. Stack traces here kill the loop next iteration.
