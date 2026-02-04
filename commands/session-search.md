Search Claude JSONL conversation content across projects.

## Arguments

- query: Search term (required)
- project: (optional) Filter by project path substring

## Steps

1. Identify JSONL files to search:
   - All projects: ~/.claude/projects/*/*.jsonl
   - Or filtered by project substring if provided

2. Search JSONL files for query:
   - Use grep/ripgrep for efficiency
   - Focus on assistant message content (where Claude's explanations live)
   - Case-insensitive search

3. For each match:
   - Extract project name from path
   - Extract session ID from filename
   - Show surrounding context (the actual text)

4. Display matches grouped by session:

```
## edgerouter / b3f4d541 (2026-01-28)
"...the JWKS endpoint returns keys in JWK format, which lua-resty-jwt
can parse directly. The validation flow is: fetch JWKS → cache by kid →
validate signature..."

## edgerouter / a6bc1ba2 (2026-01-25)
"...for the tertiary pool logic, we need to check the route segments..."
```

5. Show how to resume: `claude --resume {session-id}`

## Performance Note

JSONL files can be large. Consider:
- Limiting to recent files (last 30 days) by default
- Using ripgrep for speed
- Adding --all flag to search everything


ARGUMENTS: $ARGUMENTS
