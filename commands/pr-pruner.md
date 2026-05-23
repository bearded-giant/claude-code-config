---
description: Close the MR for THIS worktree's branch if it's stale. Scoped to one MR — the one whose source branch == current branch. Trigger phrases - "prune this MR", "close this MR if dead", "/pr-pruner", or invoked via `/loop 1h /pr-pruner`.
allowed-tools: Bash, Read, Grep, Glob, AskUserQuestion
---

Close this worktree's MR if it's gone stale.

## Worktree scoping model

One session/loop handles exactly one MR — the one matching the current branch. Each worktree decides for itself whether its own MR is dead.

## Preconditions

- `glab auth status` ok
- In a git repo with a GitLab remote
- Current branch is **not** `main` / `master` / `stage` — exit clean if it is
- Read-mostly until close — does not touch the working tree

## Staleness rules

This MR is a **prune candidate** when ANY of:

1. **Hard stale**: no commits, no comments, no pipeline runs in last **14 days**, AND latest pipeline is failing or no pipeline.
2. **Approved-but-abandoned**: approved 21+ days ago, no merge attempt, branch behind default by 30+ commits.
3. **Draft-rot**: marked Draft, last commit 30+ days ago, no activity since.
4. **Superseded**: another open MR by @me touches >70% of the same files AND was opened later than this one.

**Never** prune when:

- Any thread has an unresolved discussion with activity in last 7 days (mid-conversation)
- Author != @me
- MR description contains `do-not-prune`
- Labels include `keep` / `wip` / `holding`

## Steps

1. **Resolve current branch and MR**:
   ```
   BRANCH="$(git branch --show-current)"
   glab mr list --source-branch="$BRANCH" --state=opened --output=json
   ```
   - Zero results → exit clean: `no open MR for branch <BRANCH>`
   - Multiple results → exit clean: `ambiguous`
   - One result → capture `iid`, `project_id`, all MR fields. Proceed.

2. **Gather signals** via `glab api`:
   - Last commit timestamp: `projects/<project_id>/merge_requests/<iid>/commits` (take max)
   - Last note timestamp: `projects/<project_id>/merge_requests/<iid>/notes`
   - Last pipeline status: `projects/<project_id>/merge_requests/<iid>/pipelines`
   - Approval state: `projects/<project_id>/merge_requests/<iid>/approvals`
   - Labels from MR JSON
   - Changed files: `projects/<project_id>/merge_requests/<iid>/changes`

3. **Detect supersede** — only when relevant. List own other open MRs and compare changed-files overlap:
   ```
   glab mr list --author=@me --state=opened --output=json
   ```
   If any later-opened MR overlaps >70% of files, mark `superseded` with that MR's iid.

4. **Apply rules** — produce a single reason code (`hard_stale`, `approved_abandoned`, `draft_rot`, `superseded`) or `not_stale`.

5. **If not_stale** → exit clean: `MR !<iid> still active — no action`.

6. **Confirm before closing** when interactive:
   - Use `AskUserQuestion`: "Close MR !<iid> (<reason>)? Reason: <one-line context>".
   - Detect /loop mode via env `CLAUDE_LOOP_RUN=1`. When set, **auto-close** without prompting.

7. **Close**:
   1. Post comment:
      ```
      glab api -X POST "projects/<project_id>/merge_requests/<iid>/notes" -f body="<closing-comment>"
      ```
      Templates by reason:
      - `hard_stale`: `Closing — no activity in 14d, pipeline red. Reopen if still needed.`
      - `approved_abandoned`: `Closing — approved 21d+ ago, branch is now 30+ commits behind. Cut a fresh MR if still relevant.`
      - `draft_rot`: `Closing draft — no commits in 30d. Reopen when ready.`
      - `superseded`: `Closing — superseded by !<other-iid>.`
   2. Close:
      ```
      glab mr close <iid>
      ```
   3. **Do NOT delete the branch.** The worktree is still on it; user decides cleanup.

## Safety rails

- **Never close an MR you didn't author.**
- **Never delete branches.**
- **Always post a comment before closing.**
- **Honor labels** (`keep`, `wip`, `holding`) and the `do-not-prune` description marker.
- **Dry-run**: if env `PR_PRUNER_DRY_RUN=1`, print the verdict and exit. No comment, no close.

## Output

Active case:
```
MR !1234 (feat-xyz): not_stale — no action
```

Prune case:
```
MR !1100 (refactor-auth-v2): hard_stale (last activity 21d ago, pipeline red) → closed
```

Dry-run case:
```
MR !1100: WOULD close (hard_stale) — dry run, no action
```

## Failure modes — exit clean

Auth/network errors → log + exit 0. Never crash the loop.
