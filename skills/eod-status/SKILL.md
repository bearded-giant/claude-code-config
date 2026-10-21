---
name: eod-status
description: Draft the end-of-day status DM to my manager from Slack (manager DM, the manager's asks, my own messages), my GitLab MRs and reviews, my GitHub PRs, release-central deploys that carry my MRs, and the Claude activity (workstreams, vault notes, artifacts, handoffs) in the vault daily notes. Sends the draft to my self-DM only, for a hand copy to the manager. `--days N` writes a rollup for the last N days (3, 7). Learns standing rules from `eod: <rule>` self-DMs and from edits to sent updates. Auto-fires when user says "eod status", "eod update", "draft my eod", "end of day update", "status for mike", "rollup for the last N days", "weekly rollup", or invokes /eod-status. Flags: --days, --dry-run, --no-notify.
---

# eod-status

Ported from a teammate's EOD drafter. One script gathers the facts, a headless `claude -p` reads Slack and composes, code validates the template, and a second headless call DMs the result to me. It never writes to the manager's DM.

```
/eod-status                 # today's update, sent to my self-DM
/eod-status --dry-run       # print the draft only: no Slack send, no state change
/eod-status --days 3        # rollup for the last 3 days
/eod-status --days 7        # weekly rollup
```

## Run

1. `cd ~/.claude/skills/eod-status/scripts && python3 eod.py <flags> --no-notify` with `run_in_background: true`. A run takes 2-6 minutes (one haiku gather, one compose, one haiku send).
2. On exit 0, print the draft from stdout in a fenced block. A real run also landed it in the self-DM; say so. On exit 1, quote the last `ERROR` line of the output.
3. `--dry-run` when the ask says preview, dry run, or "don't send".

## Window

- `--days 1` (default): since the same time on the previous weekday, so a Monday run covers Friday onward.
- `--days N`: N calendar days back, pushed to Friday when that lands on a weekend. The opener becomes `Rollup from me for the last N days:`, topics roll up to outcomes, and the previous daily draft is not fed in.
- Learning reads back to the last successful real run, so a skipped day still picks up `eod:` notes.

## Sources

| Source | How | On failure |
|---|---|---|
| Slack | headless `claude -p`, slack plugin read tools only, from `scripts/.claude/settings.json` | run fails |
| GitLab MRs I authored | `glab api merge_requests?author_username=...` + approvals | run fails |
| GitLab MRs I review | `glab api merge_requests?reviewer_username=...`, own MRs dropped | marked unavailable |
| GitHub PRs | `gh search prs --author=@me` and `--reviewed-by=@me` | marked unavailable |
| release central | MCP over curl: releases in the window whose risk report lists my MRs (author name or MR URL), rollout status, my own ship/rollback actions | marked unavailable, no deploy claims |
| Claude activity | vault `daily/<date>.md` `## CLAUDE SESSIONS` (counts per workstream) and `## CLAUDE LINKS` (vault notes and handoffs with a 400-char excerpt, artifact titles) | empty |

The compose prompt (`scripts/prompt.md`) holds the template, grounding rules, and my Slack voice from `config/voice.md`. Every bullet needs a cited source; code rejects a draft that breaks the template or cites fewer sources than bullets, retries once, then fails.

## Config and state

`~/.config/eod-status/` (`EOD_STATUS_HOME` overrides):

- `config.json`: `name`, `gitlab_user`, `email`, `self_user`, `self_dm`, `manager`, `manager_user`, `manager_dm`. Slack IDs stay out of the repo. `self_dm` must match the channel the send returns, or the run errors.
- `lessons.md`: standing rules, one per line, plain text. Edit or delete by hand.
- `proposals.json`, `state.json`, `drafts/<date>.md`, `rollups/<date>-<N>d.md`, `dry-run.md`, `logs/`.

## Teaching

- DM myself `eod: <rule>` (top level or in a thread). The next run adds it to `lessons.md`; later rules win on conflict.
- After I send an update to the manager, the next run diffs it against that day's draft. Edits that generalize come back to the self-DM as numbered suggestions; reply `eod: accept P3` or `eod: reject P3`.

## Schedule

Weekdays 3pm ET via launchd, optional:

```
sed "s|__HOME__|$HOME|g" ~/.claude/skills/eod-status/scripts/eod-status.plist > ~/Library/LaunchAgents/local.eod-status.plist
launchctl load ~/Library/LaunchAgents/local.eod-status.plist
launchctl kickstart gui/$(id -u)/local.eod-status   # run now
```

`run.sh` pins PATH and Homebrew python, kills a run after 40 minutes, and logs to `logs/cron.log`. A failed run posts a desktop notification (`terminal-notifier`) whose click retries.

## Tests

`uv run --no-project --with pytest python -m pytest -q skills/eod-status/scripts`
