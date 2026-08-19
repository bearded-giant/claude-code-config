---
description: "Dispatch a sub-agent to explore or act in another repo by path. Isolated context; main session stays clean."
argument-hint: "<abs-path-to-repo> \"<question or task>\" [--role owner|caller|sibling] [--mode explore|edit|parallel] [--agent <type>]"
---

Run a sub-agent scoped to another repo on disk. Default: `Explore` agent for read-only investigation. Use `--mode edit` for changes, `--mode parallel` to spawn one agent per path in the same message.

Use this when the peer repo has NO live Claude session. If a session is already running there, `SendMessage` to it instead — it has warm context.

## Arguments

- `abs-path-to-repo`: absolute path to the peer repo root. Multiple paths allowed with `--mode parallel` (space-separated).
- `"<question or task>"`: free-text brief. Quoted.
- `--role`: relationship from the **parent's perspective** (parent = current repo). Drives the Direction/Focus lines in the brief. Default `sibling`.
  - `owner`: parent **calls** peer. Peer is downstream.
  - `caller`: peer **calls** parent. Parent is the service.
  - `sibling`: bidirectional or unknown.

  Mnemonic: role describes the **peer**.
- `--mode`:
  - `explore` (default) → `Explore` agent, read-only, returns structured summary.
  - `edit` → `general-purpose` agent, may modify peer repo files.
  - `parallel` → one agent per path, single message.
- `--agent <type>`: override subagent_type (e.g. `kai:backend-engineer`, `debugger`). Skips default routing.

## Steps

1. **Probe the peer** — `~/.claude/scripts/peer-probe <path>` via ONE Bash call. Emits `git_root`, `short_name`, `branch`, `dirty`, `active_feature`, `layout`, `has_claude_md`.
   - Non-zero exit (`error=not_a_directory` / `error=not_a_git_repo`) → stop, report. Do not continue.
   - `git_root` == current repo's `git rev-parse --show-toplevel` → error "Same repo — no scout needed." Stop.
   - Do NOT re-run `git -C`, `ls`, or inline-python parse `features.json`. Probe is the single source.

   Path not accessible via `permissions.additionalDirectories`? Sub-agents inherit the same gate — tell the user to `/add-dir <path>` or relaunch with `--add-dir`, then stop.

2. **Build sub-agent prompt**

   ```
   Peer repo: <short_name> @ <git_root>
   Peer branch: <branch>   role vs parent: <role>
   Peer active feature: <active_feature or "-">

   Parent repo: <current-repo-short-name> @ <current-path>

   Direction: <role-direction-line, see below>
   Focus: <role-focus-line, see below>

   Task:
   <user-supplied brief>

   Constraints:
     - Work only within the peer repo path. Do not touch parent repo files.
     - <mode-specific constraint, see below>
     - Report back: findings, file:line refs, next suggested step for parent session.
     - Keep response under 400 words unless the task genuinely needs more.
   ```

   Role-specific substitutions:

   - `role=owner` (parent calls peer; peer is downstream):
     - Direction: "Parent repo calls into this peer. Peer exposes an interface parent depends on."
     - Focus: "Exposed contracts, endpoint signatures, request/response shapes, auth requirements, error codes, version assumptions. Report what parent needs to know to call peer correctly."

   - `role=caller` (peer calls parent; parent is the service):
     - Direction: "This peer calls into the parent repo. Parent exposes an interface peer depends on."
     - Focus: "Call sites of parent's interface, payload construction, response/error handling, retry and timeout behavior, cached assumptions about parent's shape. Report how changes in parent would break peer."

   - `role=sibling` (bidirectional or unknown):
     - Direction: "Symmetric relationship. No directional assumption."
     - Focus: "Report findings as asked; flag whichever direction matters for the task."

   Mode-specific constraints:
   - `explore`: "Read-only. Grep/Read/Glob only. No edits, no Write, no Bash side effects. Git log/status OK for context."
   - `edit`: "Edits allowed. Do not commit. Do not push. List every file modified in the report."
   - `parallel`: same template per path, one sub-agent each, dispatched in a single message.

3. **Dispatch**
   - `--mode explore` → `Agent(subagent_type="Explore", description="peer-scout <short_name>: <first 4 words of task>", prompt=<template>)`
   - `--mode edit` → `Agent(subagent_type="general-purpose", ...)`
   - `--mode parallel` → ONE message with N `Agent` calls, one per path.
   - `--agent <type>` override → pass through as `subagent_type`.

4. **Return summary** — surface the sub-agent's report inline.

## Examples

Read-only exploration:
```
/peer-scout /Users/bryan/dev/billing-api "how does the merchant auth JWT get validated on inbound webhook requests?" --role owner
```

Parallel check across two repos:
```
/peer-scout /Users/bryan/dev/billing-api /Users/bryan/dev/frost "who calls /api/v2/subscriptions/update and with what payload shape?" --mode parallel
```

Edit in peer (caution):
```
/peer-scout /Users/bryan/dev/billing-api "rename WEBHOOK_KEY to WEBHOOK_SECRET in config + tests" --mode edit
```

Specialist agent:
```
/peer-scout /Users/bryan/dev/billing-api "review the new auth middleware for security gaps" --agent kai:code-reviewer
```

## Notes

- No shared file, no registry. Sub-agent report is ephemeral, lives in main session context.
- Need a finding preserved? Ask the main session to write it to `research/` or the feature's plan after the scout returns.
- Don't remember the path? `/recent-repos` lists live repos and hands back paths.
- Heavy cross-cutting edits (contract change hitting 10 files across both repos): main session drafts the plan, then dispatches one `--mode edit` agent per repo in parallel with matching briefs.
