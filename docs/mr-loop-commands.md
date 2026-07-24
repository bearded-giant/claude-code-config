# MR loop commands

Three worktree-scoped commands for GitLab MR lifecycle. One MR per session — matches `git branch --show-current`. Run inside the worktree where the MR's code lives.

## Commands

| Command | What | When |
|---|---|---|
| `/babysit` | Address open review threads on this worktree's MR | `/loop 5m /babysit` while review active |
| `/post-merge-sweeper` | Open follow-up MR for threads unresolved at merge time | `/loop 1h /post-merge-sweeper` (48h window) |
| `/pr-pruner` | Close stale MRs (no auto-delete of branch) | `/loop 1h /pr-pruner` |

## `/babysit`

Resolves MR via `glab --source-branch=$BRANCH --state=opened`. Fetches unresolved discussions (`resolved=false`, author != self).

Classifies + acts:

| Class | Action |
|---|---|
| `actionable_simple` (rename / typo / nit / null check) | fix |
| `actionable_complex` (design / ambiguous) | reply `[babysit] needs your input`, skip |
| `informational` | skip |

Flow: rebase → edit → `py-check`/`ts-check` → commit `review: ...` → push → reply `addressed in <sha>` → resolve. Max 5 threads/run. Skip Draft MRs unless `[babysit-ok]` in description.

## `/post-merge-sweeper`

Resolves MR via `--state=merged`, most recent within 48h. Fetches unresolved discussions where `last_note_ts < merged_at`. Same classifier as babysit.

Branch: `followup/${BRANCH}-sweep-$(date +%Y%m%d)`. Skips if remote exists. Checks out `target_branch` (from MR JSON — no hard-coded `main`), branches off, fixes all, pushes. Opens follow-up MR via `glab` (or `kai:open-mr`); title `review: post-merge sweep for !<iid>`. Replies on each original thread `addressed in follow-up !<new-iid>`, resolves.

1 follow-up MR/run. 48h window only. Skip if `author != self`.

## `/pr-pruner`

Resolves MR via `--state=opened`. Staleness rules (any one triggers):

| Reason | Trigger |
|---|---|
| `hard_stale` | 14d no activity AND pipeline red/none |
| `approved_abandoned` | approved 21d+ ago, 30+ commits behind default |
| `draft_rot` | Draft + no commits in 30d |
| `superseded` | another own later MR overlaps >70% of files |

Never prune: unresolved thread activity in last 7d, `do-not-prune` in desc, labels `keep`/`wip`/`holding`, `author != self`.

Env toggles:
- `PR_PRUNER_DRY_RUN=1` — print verdict only
- `CLAUDE_LOOP_RUN=1` — skip confirm (auto-close in loop mode)

Branch left intact after close.

## Safety

All three: never push to `main`/`master`/`stage`, never force-push, never amend, never checkout foreign branch. Exit 0 on auth/network/conflict/ambiguity.

## Recommended bring-up

```bash
PR_PRUNER_DRY_RUN=1 claude -p "/pr-pruner"   # safe verdict check
claude -p "/babysit"                          # one-shot, observe
/loop 5m /babysit                             # only after one-shot looks correct
/loop 1h /post-merge-sweeper
/loop 1h /pr-pruner
```

## Composes with

`kai:glab` (glab syntax), `kai:gitlab-inline-comments` (DiffNote replies), `kai:debugging-pipelines` (red pipeline escalation), `kai:open-mr` (MR creation), `py-check`/`ts-check`, `caveman-commit`, `ship-it` (MR desc + open), `loop`.

## Files

`commands/{babysit,post-merge-sweeper,pr-pruner}.md` — stowed to `~/.claude/commands/`.
