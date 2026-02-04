List Claude JSONL sessions from ~/.claude/projects/.

## Arguments

- project: (optional) Filter by project path substring (e.g., "edgerouter", "claude-code-config")
- count: (optional) Number of sessions to show, default 15

## Steps

1. List directories in ~/.claude/projects/

2. If project filter provided:
   - Filter to directories containing that substring

3. For each matching project, find JSONL files:
   - Extract session ID from filename
   - Get file modification time
   - Try to extract summary from first few lines (look for "summary" type)

4. Sort by modification time, show most recent N

5. Display as table:

```
| Date       | Project              | Session ID | Summary                          |
|------------|----------------------|------------|----------------------------------|
| 2026-01-28 | lua-edgerouter       | b3f4d541   | JWT validation implementation    |
| 2026-01-27 | claude-code-config   | cf328fa4   | statusline configuration         |
```

6. Show tip: `claude --resume {session-id}` to continue a session


ARGUMENTS: $ARGUMENTS
