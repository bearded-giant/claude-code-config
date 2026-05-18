---
description: Search or list Claude JSONL sessions across all projects. Triggers when user says "find that session about X", "where did I talk about Y", "list my recent claude sessions", "show sessions in project Z", or wants to resume an old conversation.
allowed-tools: Bash
---

Search Claude JSONL conversation content across projects, or list recent sessions by project.

## Argument Parsing

Pass `$ARGUMENTS` directly to the script. Script handles parsing.

- `--list [--project X] [--limit N]` → list mode: enumerate recent sessions (no content search)
- `<query> [flags]` → search mode (default)

Common flags:
- `--days N` → recency window (default 30)
- `--all` → all time
- `--project <substring>` → filter by project path substring
- `--limit N` → cap results

Examples:
- `/session-search cookie` → search last 30 days for "cookie"
- `/session-search cookie --days 7` → search last 7 days
- `/session-search "preprod session" --all` → search all time
- `/session-search --list --project agent-chat` → list recent sessions in agent-chat
- `/session-search --list --limit 5` → 5 most recent across all projects

## Steps

1. Run: `~/.claude/scripts/session-search $ARGUMENTS`
2. Display output verbatim. Script handles formatting, ranking, and resume hints.

ARGUMENTS: $ARGUMENTS
