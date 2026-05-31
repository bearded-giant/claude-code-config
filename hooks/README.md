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

## debug_stop_check.py

**Hook:** `Stop`

Prevents Claude from stopping when there are active (unresolved) debug sessions. Works with the persistent debug state protocol in `agents/debugger.md`.

Checks `.giantmem/debug/` and any `features/{name}/debug/` directories for markdown files that don't have a filled-in Resolution section. If found, blocks the stop and tells Claude to update `next_action` or move the file to `debug/resolved/`.

Skips the check when `stop_hook_active` is true (already continuing from a prior stop hook) to prevent infinite loops.

## guard_protected_paths.py

**Hook:** `PreToolUse` (matcher: Write, Edit, MultiEdit)

Blocks writes to protected directories: `archive/`, `plugins/marketplaces/`, `plugins/cache/`, `node_modules/`. Returns a block decision with a reason explaining the path is read-only. Prevents swarm workers and main sessions from accidentally modifying third-party or archived code.

## giantmem_recall.py

UserPromptSubmit hook. Sanitizes the prompt into a keyword OR-query, runs `giantmem find --live --json` (FTS5 over workspace docs across all worktrees), and prepends the top hits — cross-project recall. Best-effort: prints nothing on miss/timeout so the prompt is never blocked. Tunable via `GIANTMEM_RECALL_LIMIT` / `GIANTMEM_RECALL_SINCE`. Replaced the dead RLabs `:8765` hooks (`memory_inject`, `memory_session_start`, `memory_curate`).

## Hook Wiring Summary

All hooks are configured in `settings.json`. Here's the full map:

| Event | Scripts | Context injection? |
|-------|---------|-------------------|
| SessionStart | `giantmemd start`, `sync_settings.py`, `session_prime.py`, `memory_index_sweep.py`, `workspace_session_hook.py`, `ensure_personal_claude.py` | Yes (one-time) |
| UserPromptSubmit | `giantmem_recall.py`, `clear_attention.py` | Yes (top FTS5 hits per prompt) |
| PreCompact | `precompact_capture.py`, timestamp file | No (stderr + file) |
| SessionEnd | `session_end_ingest.py`, `workspace_session_end.py` | No (stderr + file writes) |
| PreToolUse | `guard_protected_paths.py` (Write/Edit/MultiEdit) | No (JSON decision only) |
| Stop | `debug_stop_check.py` | No (JSON decision only) |

Recall and workspace hooks all run on one local backend: giantmem (SQLite FTS5 + sqlite-vec). `giantmem_recall.py` reads it for cross-project recall; `session_prime.py`, `session_end_ingest.py`, `live_index.py`, and `precompact_capture.py` write sessions, `.giantmem/` artifacts, and harness memory files (`~/.claude/projects/<slug>/memory/*.md`, tagged `dir_type=memory`) into it.

Durability + speed: SessionStart runs `giantmemd start` (a unix-socket daemon that kills ~700ms cold starts, so per-prompt recall is sub-ms) and `memory_index_sweep.py` (re-indexes every memory md into live.db, so a `giantmem index live` rebuild or a file from another machine never permanently loses memory).

Off-machine backup is handled by `scripts/giantmem-restic-backup.sh` on a launchd timer (`com.bryan.giantmem-restic`, every 6h), not a hook. It restic-snapshots the durable sources (`~/.claude/projects` memory md + session transcripts) and the giantmem DBs to an sftp repo on the Tailscale VPS (`sftp:bryan@claude-vps:/home/bryan/giantmem-restic`), deduplicated + encrypted. The repo password lives in the macOS keychain (`giantmem-restic`). The DBs are rebuildable from the sources via `giantmem ingest`, so the sources are what matter. Restore: set `RESTIC_REPOSITORY`/`RESTIC_PASSWORD_COMMAND`, then `restic snapshots` + `restic restore latest --target <dir>`.
