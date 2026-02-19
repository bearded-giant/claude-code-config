---
description: "Search across domain JSONs for code patterns, files, functions, or concepts"
argument-hint: "<query> [--load]"
---

# Search Domains

Search the domain knowledge base for a keyword, file path, function name, pattern, or concept. Returns which domains matched and what section the match is in, so you know which domain JSONs to load.

No output files are created. This is a lookup tool -- it points you at existing domain JSONs.

## Arguments

- query: (required) Search term. Can be a file path, function name, pattern name, package name, or general concept.
- `--load`: After showing results, automatically read the top matching domain JSONs into context (instead of just listing them).

## Steps

### 1. Load the index

Read `.giantmem/domains/_index.json`. If it doesn't exist, tell the user: "No domains indexed yet. Run `/plan-feature` to explore code domains."

### 2. Quick filter from index

Check `key_paths` and `description` in each index entry for the query. This narrows the search before reading full JSONs.

### 3. Deep search matching domains

For each candidate domain (or all if the quick filter found nothing), read `.giantmem/domains/{domain}.json` and search across all fields:

- `entry_points[].path`, `entry_points[].description`
- `key_files[].path`, `key_files[].purpose`, `key_files[].exports`, `key_files[].patterns`, `key_files[].dependencies`
- `architecture.layers`, `architecture.data_flow`, `architecture.patterns`, `architecture.key_decisions`
- `data_models.tables`, `data_models.cache_keys`
- `dependencies.internal`, `dependencies.external`
- `gotchas[]`

### 4. Present results

Group matches by domain, showing which sections matched:

```
Search: "session_store"

auth_session (.giantmem/domains/auth_session.json)
  key_files: src/services/auth_session/session_store.py -- "Redis-backed session storage"
  architecture.data_flow: "request -> auth middleware -> session_store -> Redis"
  gotchas: "Redis SCAN needed for lookup by session_id"

merchant_api (.giantmem/domains/merchant_api.json)
  dependencies.internal: "auth_session"

2 domains matched. Load with: "read .giantmem/domains/auth_session.json"
```

If no matches, say so and suggest:
- Checking the search term (typo?)
- Running `/list-domains` to see what's indexed
- Running `/plan-feature` to explore new areas

### 5. Auto-load (if --load)

If `--load` was passed, read the matching domain JSONs and present a focused summary of the parts relevant to the query. Don't dump the entire JSON -- highlight what matched.

## Rules

- Read-only. Do not create or modify any files.
- Do not create search result files. The domain JSONs ARE the files.
- Keep the output focused. Show matched sections, not full JSON dumps.
- If a query matches many domains (5+), show the top matches and note how many total.

$ARGUMENTS
