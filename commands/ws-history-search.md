Search workspace session files for keywords, files created, or discoveries.

## Arguments

- query: Search term (required)

## Steps

1. Check if scratch/history/sessions/ exists
   - If not, inform user no session files found

2. Search across all session files in scratch/history/sessions/:
   - Grep for the query term (case-insensitive)
   - Look in: User Prompts, Files Touched, Commands Run, Discoveries

3. Display matches grouped by session:

```
## Session 2026-01-28 (cf328fa4)
- [User Prompt] "I want to add jwks validation..."
- [File] scratch/features/jwks-fetch/spec.md

## Session 2026-01-23 (7de9712f)
- [Discovery] jwks endpoint returns PEM format
```

4. Show session IDs so user can do `/ws-history {id}` for full details


ARGUMENTS: $ARGUMENTS
