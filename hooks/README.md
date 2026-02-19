# Claude Code Hooks

Hooks that run at various Claude Code lifecycle events.

## workspace_session_end.py

**Hook:** `SessionEnd`

Extracts session metadata from transcript and creates session summary files. Auto-initializes workspace structure if `.giantmem/` doesn't exist.

### Output Files

| File | Description |
|------|-------------|
| `.giantmem/history/sessions/{timestamp}_{session_id}.md` | Detailed session file |
| `.giantmem/history/sessions.md` | Index with one-liner entries |
| `.giantmem/context/discoveries.md` | Appended findings |
| `.giantmem/plans/current.md` | Updated if plans detected |

### Session File Contents

```markdown
# Session: 2026-01-06 14:30 - 15:45

## Summary
Topic: workspace
Brief: update session hook to auto-init workspace

## User Prompts
- first user message...
- second user message...

## Files Touched
### Modified
- /path/to/file.py
### Created
- /path/to/new_file.py
### Read
- /path/to/read_file.py

## Tool Usage
- Edit: 5
- Read: 12
- Bash: 3

## Commands Run
- `git status`
- `pytest tests/`

## Discoveries Extracted
- [architecture] services use dependency injection
- [gotcha] tests require docker

## Metadata
- Session ID: abc12345
- Generated: 2026-01-06 15:45:30
```

### Topic Detection

Topics are determined by keyword frequency analysis of user prompts and assistant content.

**Available Topics:**

| Topic | Keywords |
|-------|----------|
| `auth` | auth, login, jwt, token, password, credential, oauth, permissions |
| `api` | api, endpoint, route, rest, graphql, request, response |
| `database` | database, sql, query, migration, model, schema, table |
| `test` | test, spec, pytest, jest, coverage, mock, fixture |
| `bug` | bug, fix, error, issue, debug, broken, failing |
| `feature` | feature, implement, add, create, new, build |
| `refactor` | refactor, cleanup, reorganize, restructure, rename |
| `config` | config, setting, env, environment, setup, install |
| `docs` | document, readme, comment, explain, describe |
| `perf` | performance, optimize, speed, slow, fast, cache |
| `ui` | ui, frontend, component, style, css, render, display |
| `deploy` | deploy, ci, cd, pipeline, docker, kubernetes |
| `workspace` | workspace, scratch, hook, session, claude, mcp, plugin |

**Topic Selection Logic:**

1. Count keyword matches for each topic in session content
2. If `WORKSPACE.md` has a Purpose section with topic keywords, add +5 bonus weight to that topic
3. Select highest-scoring topic (minimum threshold: 3 matches)
4. Fallback to workspace topic if defined, otherwise `general`

**Workspace Topic Hint:**

If `.giantmem/WORKSPACE.md` contains a filled-in Purpose section:

```markdown
## Purpose
API authentication refactoring
```

The hook extracts topic keywords from Purpose and applies a +5 weight bonus. This helps sessions in a workspace stay consistently categorized.

### Auto-Init Behavior

If `.giantmem/` doesn't exist when session ends, the hook creates:

```
.giantmem/
  .gitkeep
  WORKSPACE.md          # with project name, date, git branch
  context/
  plans/
  history/
    sessions/
  filebox/
  prompts/
  research/
  reviews/
```

### Discovery Extraction

Patterns that trigger discovery extraction:

| Category | Trigger Words |
|----------|---------------|
| `finding` | discovered, found, learned, realized, noticed |
| `architecture` | pattern, architecture, structure |
| `gotcha` | gotcha, caveat, watch out, careful, note that, important |
| `convention` | convention, standard, style, naming |
| `dependency` | dependency, requires, depends on, imports |
| `config` | config, configuration, setting, environment |
| `entry` | entry point, main, bootstrap, init |

## workspace_session_hook.py

**Hook:** `SessionStart`

Injects workspace context at session start. Reads `.giantmem/WORKSPACE.md`, recent sessions, active plans, and discoveries to provide continuity.

## memory_*.py

Memory-related hooks for the claude-mem MCP integration (separate system).
