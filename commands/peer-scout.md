---
description: "Dispatch a sub-agent to explore or act in a paired peer repo. Isolated context; main session stays clean. Requires a prior /pair-repo."
argument-hint: "<peer-short-name> \"<question or task>\" [--mode explore|edit|parallel] [--agent <type>]"
---

Run a sub-agent scoped to a paired peer repo. Default: `Explore` agent for read-only investigation. Use `--mode edit` for changes, `--mode parallel` to spawn one agent per paired repo in the same message.

## Arguments

- `peer-short-name`: must match an entry in `peers.md`. If only one peer paired, may be omitted.
- `"<question or task>"`: free-text brief. Quoted.
- `--mode`:
  - `explore` (default) → `Explore` agent, read-only, returns structured summary.
  - `edit` → `general-purpose` agent, may modify peer repo files.
  - `parallel` → spawn one agent per paired repo in a single message (use with caution — best for "check how X works in both repos").
- `--agent <type>`: override subagent_type (e.g., `kai:backend-engineer`, `debugger`). Skips default routing.

## Steps

1. **Locate peers.md**
   - Active feature in `features.json` → `.giantmem/features/{active}/peers.md`.
   - Else → `.giantmem/context/peers.md`.
   - If missing or empty: error "No paired repos. Run /pair-repo <path> first." Stop.

2. **Resolve peer**
   - Parse `peers.md` for `## <name>` sections. Extract `path`, `role`, `branch`, `active_feature`.
   - If `peer-short-name` provided: must match one entry.
   - If omitted + exactly one peer: use it.
   - If omitted + multiple peers: list them, ask user to pick. Stop.

3. **Build sub-agent prompt**

   Template:
   ```
   Peer repo: <peer-short-name> @ <peer-path>
   Peer branch: <branch>   role vs parent: <role>
   Peer active feature: <active_feature or "-">

   Parent repo: <current-repo-short-name> @ <current-path>
   Parent active feature: <parent-active or "-">

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

   Role-specific substitutions (inject into `Direction` + `Focus` lines):

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
   - `parallel`: same template per peer, with one sub-agent per paired repo, dispatched in a single message. Each peer's role drives its own Direction/Focus block.

4. **Dispatch**
   - `--mode explore` → `Agent(subagent_type="Explore", description="peer-scout <peer>: <first 4 words of task>", prompt=<template>)`
   - `--mode edit` → `Agent(subagent_type="general-purpose", ...)`
   - `--mode parallel` → ONE message with N `Agent` tool calls (one per peer). Each gets the template with its peer's metadata filled in.
   - `--agent <type>` override → pass through as `subagent_type`.

5. **Return summary**
   - Surface sub-agent's report inline.
   - Append: "Paired context preserved. Ready for follow-up or to act on findings in parent repo."

## Examples

Read-only exploration:
```
/peer-scout billing-api "how does the merchant auth JWT get validated on inbound webhook requests?"
```

Parallel check across two paired repos:
```
/peer-scout "who calls /api/v2/subscriptions/update and with what payload shape?" --mode parallel
```

Edit in peer (caution):
```
/peer-scout billing-api "update the webhook_secret env var name from WEBHOOK_KEY to WEBHOOK_SECRET in config + tests" --mode edit
```

Use specialist agent:
```
/peer-scout billing-api "review the new auth middleware for security gaps" --agent kai:code-reviewer
```

## Notes

- This command does NOT maintain a shared file. Sub-agent report = ephemeral, lives in main session context.
- If you need the finding preserved, ask main session to write it to `research/` or the feature's `plan.md` after the scout returns.
- For heavy cross-cutting edits (contract change hitting 10 files across both repos), prefer: main session drafts the plan, then dispatches one `--mode edit` agent per repo in parallel with matching briefs.
