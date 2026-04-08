Search Claude JSONL conversation content across projects.

Run the search script and display results to the user:

```bash
~/.claude/scripts/session-search $ARGUMENTS
```

## Argument Parsing

The script handles all argument parsing. Pass `$ARGUMENTS` through directly.

Examples the user might type:
- `/session-search cookie` -- search last 30 days
- `/session-search cookie --days 7` -- search last 7 days
- `/session-search cookie --project agent-chat` -- filter to project
- `/session-search "preprod session" --all` -- search all time
- `/session-search cookie --limit 5` -- cap results

The script uses named args. Map user input to `--query`:
- `/session-search cookie` -> `--query cookie`
- `/session-search cookie --days 7` -> `--query cookie --days 7`

## What to Show

Run the script and display its output verbatim. The script handles formatting, ranking, and resume commands. Do not add extra commentary unless the user asks follow-up questions.

ARGUMENTS: $ARGUMENTS
