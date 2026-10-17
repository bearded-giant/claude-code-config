---
name: jira-status
description: Quick read-only check of the Jira ticket behind the current branch or an MR, via `glmon-jirad --lookup` (one call, about a second). Auto-fires when user says "jira status", "what is the jira status for this branch", "is there a ticket", "does this branch have a ticket", "ticket for this MR", "what ticket is this", or invokes /jira-status. Optional arg - a branch name, an MR URL, or group/project!iid.
---

# jira-status

One command, run from the repo the user means (the current working directory unless they name another). No other tools.

```bash
glmon-jirad --lookup                      # current checkout + branch
glmon-jirad --lookup <branch>             # another branch in this checkout
glmon-jirad --lookup <mr-url>             # any MR
glmon-jirad --lookup <group/project!iid>
```

A worktree parent (holds `.bare`) is not a checkout: run it inside the worktree for the branch the user means.

Print the output verbatim in a fenced block. Add one plain sentence only when a line needs translating for the user. Never re-query Jira or GitLab another way to double-check: the lookup is the source.

## Reading it

Ticket found, two lines:

```
PE-1601  In Review  <summary>  <browse url>
identity/recharge-auth!77  opened  pipeline success  expects In Review: in sync
```

| Verdict | Meaning |
|---|---|
| `in sync` | ticket status matches what the MR state implies |
| `drift: the next jirad tick moves it` | MR changed since the last tick; launchd fixes it within 5 minutes |
| `drift: jirad is disabled` | MR and ticket disagree and nothing will fix it until `glmon-jirad --enable` |
| `held at <status> by hand, jirad leaves it` | someone moved it to a status jirad never touches (In QA, In Monitoring, ...) |
| `not created by jirad, so it is left alone` | key came from a ticket someone made by hand; jirad only links it |

No ticket, one line naming why: excluded namespace (by design), no MR yet (ticket comes when the MR opens), MR closed without one, jirad disabled, MR predates `jira.since` (`glmon-jirad --mr <ref>` creates one), or the next tick creates it.

## Failure

Report the error line and stop. Do not substitute the Jira MCP or `glab`.

| Error | Fix to tell the user |
|---|---|
| `glmon-jirad: command not found` | `cd ~/dev/python/gitlab-tools/gitlab-monitor && make install-dev` |
| `jira config missing: <keys>` | set them in the `jira` block of `~/.config/gitlab-monitor/config.json`; token goes in `~/.config/gitlab-monitor/jira_token` (0600) or `JIRA_API_TOKEN` |
| `not a checkout with a <host> remote` | GitHub or non-GitLab repo: no ticket by design |
| `<key>: jira lookup failed: <code>` | 404 means the key in the title has no ticket; 401 means the token is bad |
