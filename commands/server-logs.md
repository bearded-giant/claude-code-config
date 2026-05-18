---
description: Grab recent server logs from preprod or prestage VM. Triggers when user says "preprod logs", "prestage logs", "what's in the server log", "tail the logs", "grep logs for X", or asks why something broke in pre-envs.
allowed-tools: Bash, Read
---

Fetch the last N lines of `server.log` from a pre-env VM. Non-blocking snapshot, not a live tail.

## Usage

`$ARGUMENTS` = `<env> [lines]`

- env: `preprod` | `prestage` (required)
- lines: integer, default 200

Examples:
- `/server-logs preprod` → last 200 lines from preprod
- `/server-logs prestage 500` → last 500 lines from prestage

## Steps

1. Parse `$ARGUMENTS`:
   - First token = env (`preprod` or `prestage`). If missing or invalid, ask user which env.
   - Second token = lines. Default 200 if absent.
2. Run: `scripts/pre-envs/grab-logs.sh <env> <lines>`
3. Display output directly. No summarizing or truncating unless user asks.
