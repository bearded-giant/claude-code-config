# MR loop commands

Worktree-scoped command for GitLab MR lifecycle. One MR per loop: the branch checked out in the worktree passed as the argument, else the session cwd. One session can loop several MRs with one `/loop 5m /babysit <worktree path>` each.

## `/babysit`

Address open review threads on the worktree's MR. Runs as a forked subagent, so a loop fire costs a fresh context, not the host session's. Loop: `/loop 5m /babysit [<worktree path>]`; it stops itself at READY (pipeline green, and on Greptile MRs, Greptile has reviewed the head, posting `@greptile review` itself, max 3 rounds) or BLOCKED (red pipeline, conflict, round cap, Greptile silent 15 min). In a repo whose worktree-base `CLAUDE.md` carries a `## Merge and release: standing user grant` section, READY continues into that grant's merge, tag, tag-pipeline watch and smoke steps inside the fork, ending `RELEASED <tag>` or `BLOCKED`. A loop fire runs as a local command, so its output reaches the terminal but never the host session's model. On READY, BLOCKED, RELEASED, sign-off, a dirty-tree hold or a skip, the fork schedules a one-shot plain-text prompt (`CronCreate`, two minutes out) that hands the host its report, once per state and head sha. A dirty worktree is never touched: thread edits wait for a clean tree, and the gate, merge, tag and smoke still run.

Resolves MR via `glab --source-branch=$BRANCH --state=opened`. Fetches unresolved discussions (`resolved=false`, author != self).

Classifies + acts:

| Class | Action |
|---|---|
| `actionable_simple` (rename / typo / nit / null check) | fix |
| `actionable_complex` (design / ambiguous) | defer to the output (no MR note), skip; sign off with `/babysit <path> signoff <n>` |
| `informational` | skip |

Flow: rebase → edit → `py-check`/`ts-check` → commit `review: ...` → push → reply one line per addressed item (`config/voice.md`) → resolve. Max 5 threads/run. Skip Draft MRs unless `[babysit-ok]` in description.

## Safety

Never push to `main`/`master`/`stage`, never force-push, never amend, never checkout foreign branch. Exit 0 on auth/network/conflict/ambiguity.

## Recommended bring-up

```bash
claude -p "/babysit"                          # one-shot, observe
/loop 5m /babysit <worktree path>             # only after one-shot looks correct
```

## Composes with

`kai:glab` (glab syntax), `kai:gitlab-inline-comments` (DiffNote replies), `kai:debugging-pipelines` (red pipeline escalation), `kai:open-mr` (MR creation), `py-check`/`ts-check`, `caveman-commit`, `ship-it` (MR desc + open; GitLab with `glmon-jirad` enabled syncs a Jira ticket; starts `/loop 5m /babysit <worktree>` in Greptile repos, or any GitLab repo in autonomous mode (`/auto`)), `greptile` (`@greptile review` trigger, `.greptile/` rules), `loop`.

## Files

`commands/babysit.md` — stowed to `~/.claude/commands/`.
