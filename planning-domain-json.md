# Feature: Domain JSON Knowledge Base

Structured, LLM-consumable code exploration output that persists across sessions and accumulates into a searchable repo knowledge base.


## Problem

Claude re-reads the same code every session. Exploration output is prose buried in chat history. No structured way to carry forward what was learned about a codebase.


## Solution

Domain JSONs -- structured explorations of bounded code areas (auth layer, payment flow, etc.) stored as repo-level assets. Created during feature planning, searchable via CLI and SQLite FTS5, loadable as context in future sessions.


## What was built

### Claude Code commands (claude-code-config/commands/)

| Command | Purpose |
|---------|---------|
| `/plan-feature [name] [--refresh]` | Derive domains from spec + codebase, explore with code-explorer agents, write domain JSONs, draft implementation plan |
| `/list-domains [--verbose]` | Table view of all indexed domains from `_index.json` |
| `/search-domains <query> [--load]` | Search across domain JSONs for files, functions, patterns. `--load` reads matched JSONs into context |
| `/update-domains [domains] [--all-stale] [--for=feature]` | Refresh stale domain JSONs after code changes |
| `/complete-feature` (updated) | Now auto-refreshes domains whose files were modified during the feature |

### Standalone CLI (giant-tooling/domain-search/domains)

Terminal tool for use outside Claude Code. Reads live workspace files and archived SQLite FTS5.

| Subcommand | What it does |
|------------|-------------|
| `domains list` | Table of all domains in current workspace |
| `domains show <name>` | Pretty-print a domain with colored output |
| `domains search <query>` | Search live workspace domains |
| `domains archive <query>` | Search archived domains across all projects via SQLite FTS5 |
| `domains export <name> [-o file]` | Dump domain as shareable markdown |
| `domains fzf` | Interactive picker with preview pane |

### scratch-archive integration (giant-tooling/scratch-archive/)

| File | Change |
|------|--------|
| `scratch-search.py` | Added `domains` to valid types, `flatten_domain_json()` for FTS-friendly indexing, extended ingest to glob `domains/*.json` |
| `scratch-archive.sh` | Updated rg indexer to catch `domains/*.json`, added `domains` to type validation |

### CLAUDE.md updates

Session recovery now loads `domains/_index.json` at startup. Feature folder structure documented with `plan.md` and `plan_context.json`. Directory format table and selection guide updated. Command list updated.


## Data model

### scratch/domains/_index.json

Registry of all domain explorations. Lightweight enough to load at session start.

```json
{
  "repo": "customcheckout",
  "last_updated": "2026-02-16",
  "domains": {
    "auth_session": {
      "file": "auth_session.json",
      "description": "Authentication and session management layer",
      "last_explored": "2026-02-16",
      "key_paths": ["src/services/auth_session/", "src/api/auth/"],
      "features": ["jwt-session-cookie", "jwt-session-enforcement"]
    }
  }
}
```

### scratch/domains/{name}.json

Full domain exploration. One per code area.

```json
{
  "domain": "auth_session",
  "description": "Authentication and session management layer",
  "last_explored": "2026-02-16",
  "explored_for_features": ["jwt-session-enforcement"],
  "entry_points": [
    { "path": "...", "type": "api_endpoint", "description": "..." }
  ],
  "key_files": [
    { "path": "...", "purpose": "...", "exports": [], "patterns": [], "dependencies": [] }
  ],
  "architecture": {
    "layers": [], "data_flow": "...", "patterns": [], "key_decisions": []
  },
  "data_models": { "tables": [], "cache_keys": [], "schemas": {} },
  "dependencies": { "internal": [], "external": [] },
  "gotchas": []
}
```

### scratch/features/{name}/plan.md

Implementation plan for a feature. References which domains informed it.

### scratch/features/{name}/plan_context.json

Links feature to domains. Records which were created, refreshed, or reused.

```json
{
  "feature": "jwt-session-enforcement",
  "domains_referenced": ["auth_session", "merchant_api"],
  "domains_created": ["auth_session"],
  "domains_refreshed": [],
  "domains_reused": ["merchant_api"],
  "planned_at": "2026-02-16"
}
```


## Key design decisions

1. **Domains are repo-level, not feature-scoped.** They accumulate into a knowledge base. Features reference them but don't own them.

2. **Domains are auto-derived.** Claude reads the feature spec and codebase structure, proposes domains, user confirms. No upfront domain knowledge required.

3. **7-day staleness threshold.** Domains explored within 7 days are reused by default. `--refresh` forces re-exploration.

4. **Commands and CLI are independent.** Both read the same JSON files. The contract is the data format, not shared code. Commands use Claude's native tools. CLI is standalone Python.

5. **FTS5 indexing flattens JSON into labeled lines.** `domain: auth_session`, `key_file: src/...`, `gotcha: ...` -- searches naturally against structured fields.


## Data flow

```
/plan-feature
  -> code-explorer agents analyze codebase
  -> domain JSONs written to scratch/domains/
  -> plan.md + plan_context.json written to feature dir
  -> _index.json updated

scratch-archive archive
  -> copies scratch/domains/ to ~/scratch_archive/{project}/{branch}/{ts}/
  -> scratch-search.py ingest flattens JSON into SQLite FTS5

domains archive "query"
  -> hits FTS5 for fast text match
  -> reads actual JSON files for structured output

session start
  -> Claude reads _index.json
  -> loads domain JSONs relevant to active feature
  -> no re-reading code
```
