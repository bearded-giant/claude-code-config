# MR Loop Commands — babysit / post-merge-sweeper / pr-pruner
<!-- caveman:compressed -->

Three worktree-scoped commands automate GitLab MR lifecycle. Inspired by Boris Cherny's `/loop /babysit` pattern, rewritten for `glab`, scoped to single MR per session.

## Worktree scoping model

All three operate on **one MR per session** — matches `git branch --show-current` via `glab --source-branch=<branch>`. Run inside worktree where MR's code lives. Each worktree → own loop → own MR. Parallelism via N worktrees, not repo-wide scanning.

---

## `/babysit` — `commands/babysit.md`

**Purpose**: address open review threads on this worktree's MR.

**Flow**:
1. Resolve MR via `--source-branch=$BRANCH --state=opened`. 0 or >1 results → exit 0.
2. Fetch unresolved discussions (`resolved=false`, `system=false`, last author != self).
3. Classify each thread:
   - `actionable_simple` (rename / typo / nit / missing null check) → fix
   - `actionable_complex` (design pushback / ambiguous) → reply `[babysit] needs your input` + skip
   - `informational` → skip
4. `git pull --rebase` once. Edit. Run `py-check` / `ts-check`. Commit with `review:` prefix. Push.
5. Reply on thread: `addressed in <short-sha>`. Resolve thread.
6. Pipeline check post-push — newly red → note `[babysit] pipeline red after my fix` + bail.

**Caps**: max 5 threads per run. Skip Draft MRs unless `[babysit-ok]` in description.

**Safety**: never push to `main`/`master`/`stage`. Never force-push. Never amend. Never check out foreign branch.

**Usage**:
```
claude -p "/babysit"            # one-shot
/loop 5m /babysit               # per worktree
```

---

## `/post-merge-sweeper` — `commands/post-merge-sweeper.md`

**Purpose**: open follow-up MR for review threads left unresolved when this worktree's MR merged.

**Flow**:
1. Resolve MR via `--source-branch=$BRANCH --state=merged`, pick most recent within 48h. Older → exit clean.
2. Fetch discussions: `resolved=false` AND `last_note_ts < merged_at` AND author != self.
3. Classify same as babysit.
4. Sweep branch: `followup/${BRANCH}-sweep-$(date +%Y%m%d)`. Skip if exists on remote.
5. Checkout `target_branch` (from MR JSON, no hard-coded `main`), pull, branch off, fix all, push.
6. Open follow-up MR via `glab mr create` (or delegate to `kai:open-mr`):
   - Title: `review: post-merge sweep for !<iid>`
   - Body links each thread + one-line summary of fix
   - Reviewers inherited from source MR
7. Reply on each original thread: `addressed in follow-up !<new-iid>`. Resolve.
8. Return to `$BRANCH`.

**Caps**: 1 follow-up MR per run. 48h window only. Skip if MR author != self.

**Usage**:
```
claude -p "/post-merge-sweeper"
/loop 1h /post-merge-sweeper
```

---

## `/pr-pruner` — `commands/pr-pruner.md`

**Purpose**: close this worktree's MR if stale.

**Staleness rules** (any one enough):
| Reason code | Trigger |
|---|---|
| `hard_stale` | 14d no commits/comments/pipelines AND latest pipeline red or none |
| `approved_abandoned` | approved 21d+ ago, no merge, 30+ commits behind default |
| `draft_rot` | marked Draft, no commits in 30d |
| `superseded` | another later own MR overlaps >70% of files |

**Never prune** when:
- Any thread has unresolved activity in last 7d
- MR description contains `do-not-prune`
- Labels include `keep` / `wip` / `holding`
- Author != self

**Flow**:
1. Resolve MR via `--source-branch=$BRANCH --state=opened`.
2. Gather signals (commits / notes / pipelines / approvals / labels / changes).
3. Supersede check against own other open MRs (only step using `--author=@me`).
4. Verdict → exit if `not_stale`.
5. Confirm via `AskUserQuestion` when interactive. Auto-close when `CLAUDE_LOOP_RUN=1`.
6. Post closing comment with reason-templated body. `glab mr close`. **Branch left intact.**

**Env toggles**:
- `PR_PRUNER_DRY_RUN=1` → print verdict, no action
- `CLAUDE_LOOP_RUN=1` → skip confirm (loop mode)

**Usage**:
```
PR_PRUNER_DRY_RUN=1 claude -p "/pr-pruner"   # safe first run
claude -p "/pr-pruner"                        # interactive
/loop 1h /pr-pruner
```

---

## Composability

| Command | Composes with | Where it plugs in |
|---|---|---|
| `babysit` | `kai:glab` | reference for `glab api` syntax |
| `babysit` | `py-check` / `ts-check` | post-edit quality gate |
| `babysit` | `caveman-commit` | commit message format |
| `babysit` | `kai:gitlab-inline-comments` | DiffNote-anchored thread replies |
| `babysit` | `kai:debugging-pipelines` | escalation when pipeline goes red |
| `post-merge-sweeper` | `kai:open-mr` | step 6 MR creation (delegate) |
| `post-merge-sweeper` | `create-mr-description` | richer MR body for follow-up |
| `pr-pruner` | `AskUserQuestion` | interactive confirm |
| all three | `loop` skill | recurring execution |

## Recommended bring-up

1. `PR_PRUNER_DRY_RUN=1 claude -p "/pr-pruner"` — see verdict on current MR
2. `claude -p "/babysit"` — one-shot, observe output
3. `/loop 5m /babysit` — only after one-shot looks correct
4. `/loop 1h /post-merge-sweeper`
5. `/loop 1h /pr-pruner`

## Why model A (worktree-scoped) vs model B (repo-wide)

| | A. worktree-scoped (chosen) | B. repo-wide |
|---|---|---|
| MRs per run | 1 (current branch) | all your open MRs in repo |
| Branch checkout thrash | none — stays on branch | yes — `glab mr checkout` each |
| Conflict with user mid-edit | impossible | possible on other branches |
| Parallel via worktrees | natural — one loop per WT | redundant |
| Forgotten MR coverage | needs WT open | covers everything |

Boris's setup closer to B (one loop covers all PRs). A chosen because user's mental model is "this session/worktree owns one MR" and checking out foreign branches in active worktree unsafe.

## Failure mode posture

All three exit 0 on auth / network / conflict / ambiguity. Loop runners die silently when command crashes — clean exits mandatory. Reasons logged to stdout so loop history auditable.

## File locations

- `commands/babysit.md`
- `commands/post-merge-sweeper.md`
- `commands/pr-pruner.md`

Stowed from `~/dev/claude-code-config/` → `~/.claude/commands/`.

Committed in `f27eea2` (`commands: worktree-scoped babysit + post-merge-sweeper + pr-pruner`).