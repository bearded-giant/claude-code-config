# MR loop commands

Worktree-scoped command for GitLab MR lifecycle. One MR per session — matches `git branch --show-current`. Run inside the worktree where the MR's code lives.

`/post-merge-sweeper` and `/pr-pruner` removed 2026-08-30 (never used). Restore from git history if needed.

## `/babysit`

Address open review threads on this worktree's MR. Loop: `/loop 5m /babysit` while review active.

Resolves MR via `glab --source-branch=$BRANCH --state=opened`. Fetches unresolved discussions (`resolved=false`, author != self).

Classifies + acts:

| Class | Action |
|---|---|
| `actionable_simple` (rename / typo / nit / null check) | fix |
| `actionable_complex` (design / ambiguous) | reply `[babysit] needs your input`, skip |
| `informational` | skip |

Flow: rebase → edit → `py-check`/`ts-check` → commit `review: ...` → push → reply `addressed in <sha>` → resolve. Max 5 threads/run. Skip Draft MRs unless `[babysit-ok]` in description.

## Safety

Never push to `main`/`master`/`stage`, never force-push, never amend, never checkout foreign branch. Exit 0 on auth/network/conflict/ambiguity.

## Recommended bring-up

```bash
claude -p "/babysit"                          # one-shot, observe
/loop 5m /babysit                             # only after one-shot looks correct
```

## Composes with

`kai:glab` (glab syntax), `kai:gitlab-inline-comments` (DiffNote replies), `kai:debugging-pipelines` (red pipeline escalation), `kai:open-mr` (MR creation), `py-check`/`ts-check`, `caveman-commit`, `ship-it` (MR desc + open), `loop`.

## Files

`commands/babysit.md` — stowed to `~/.claude/commands/`.
