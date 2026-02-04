Display previous sessions from scratch/history/sessions.md.

## Arguments

- count: (optional) Number of sessions to show, default 10
- session_id: (optional) Short session ID to view details

## Steps

1. Check if scratch/history/sessions.md exists
   - If not, inform user no history found

2. If argument looks like a session ID (8 hex chars):
   - Find matching file in scratch/history/sessions/
   - Display full session details
   - Show how to resume: `claude --resume {full-session-id}`

3. Otherwise, display recent sessions:
   - Parse sessions.md for entries
   - Show last N entries (default 10, or specified count)
   - Format as table:

```
| Date       | Tag       | ID       | Description                              |
|------------|-----------|----------|------------------------------------------|
| 2026-01-28 | config    | cf328fa4 | ccstatusline display issue...            |
| 2026-01-27 | workspace | 678a304f | statusline.js usage shows 76%...         |
```

4. Show tip: `/history {id}` for session details


ARGUMENTS: $ARGUMENTS
