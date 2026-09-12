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

Also ask-gates team-shared agent config: git-tracked `CLAUDE.md` / `AGENTS.md` / `INSTRUCTIONS.md` and anything under a checked-in `.claude/` in repos outside the personal roots (`~/dev/claude-code-config`, `~/dotfiles`, `~/.claude`). Returns `permissionDecision: ask` so the edit surfaces a confirmation prompt instead of landing silently. Untracked files (e.g. `.claude/settings.local.json`, `CLAUDE.local.md`) stay freely editable.

## standing_constraints.py

**Hook:** `UserPromptSubmit`

Prints `config/standing-constraints.md` verbatim every prompt — re-asserts scope / artifact-vs-execution / precedence invariants late in context so they survive conflicts with project-level instructions. Edit the md file to change the injected rules (keep in sync with the matching CLAUDE.md sections). Override path via `CLAUDE_STANDING_CONSTRAINTS`. Best-effort: missing file prints nothing.

## giantmem_recall.py

UserPromptSubmit hook. Two arms run concurrently: a keyword OR-query through `giantmem find -s memory --json` (FTS5 bm25 over live workspace docs plus archived memory docs) and the full prompt through `giantmem artifact search --repo all --json` (chunked bge vectors; only real `vector_score > 0` hits kept, so a cold daemon degrades to FTS). Repo-first: current-repo hits fill first, at most `GIANTMEM_RECALL_CROSS_MAX` (default 1) lines come from other repos, worktree siblings of one doc collapse to one line. Output is packed into `GIANTMEM_RECALL_BUDGET` tokens (default 600, `ceil(len/4)`), with `GIANTMEM_RECALL_LIMIT` lines (default 8) as a ceiling and `GIANTMEM_RECALL_SNIPPET_CHARS` (default 400) per passage. Best-effort: prints nothing on miss/timeout so the prompt is never blocked. Query terms present in more than `GIANTMEM_RECALL_MAX_DF` of `live_docs` (default 0.2; `session`, `giantmem`, `config` in this corpus) are dropped before the FTS arm runs, so the overlap floor counts only discriminative terms. Other tunables: `GIANTMEM_RECALL_SINCE`, `GIANTMEM_RECALL_MIN_OVERLAP`, `GIANTMEM_RECALL_SEMANTIC`. Every injected line is also appended to `live.db.recall_log` (session, rank, signal, slot, path); `giantmem recall report --since 30d` joins that against the session transcript and `live_docs` writes to report precision per signal, slot, and rank, so ranker changes are compared on numbers. Regression checks: `python3 hooks/giantmem_recall_check.py`. Replaced the dead RLabs `:8765` hooks (`memory_inject`, `memory_session_start`, `memory_curate`).

## Hook Wiring Summary

All hooks are configured in `settings.json`. Here's the full map:

| Event | Scripts | Context injection? |
|-------|---------|-------------------|
| SessionStart | `giantmemd start`, `sync_settings.py`, `session_prime.py`, `doit_session_prime.py`, `memory_ingest.py`, `workspace_session_hook.py`, `ensure_personal_claude.py` | Yes (one-time) |
| UserPromptSubmit | `standing_constraints.py`, `giantmem_recall.py`, `clear_attention.py` | Yes (standing constraints + top FTS5 hits per prompt) |
| PreCompact | `precompact_capture.py`, timestamp file | No (stderr + file) |
| SessionEnd | `session_end_ingest.py`, `workspace_session_end.py` | No (stderr + file writes) |
| PreToolUse | `guard_protected_paths.py` (Write/Edit/MultiEdit) | No (JSON decision only) |
| Stop | `debug_stop_check.py` | No (JSON decision only) |

Recall and workspace hooks all run on one local backend: giantmem (SQLite FTS5 + sqlite-vec). `giantmem_recall.py` reads it for cross-project recall; `session_prime.py`, `session_end_ingest.py`, `live_index.py`, and `precompact_capture.py` write sessions, `.giantmem/` artifacts, and harness memory files (`~/.claude/projects/<slug>/memory/*.md`, tagged `dir_type=memory`) into it.

Durability + speed: SessionStart runs `giantmemd start` (a unix-socket daemon that kills ~700ms cold starts, so per-prompt recall is sub-ms) and `memory_ingest.py` (detached `giantmem db ingest --source memory-md`, which lands every memory md in archives.db, the durable, backed-up store; `live_index.py` still writes them into live.db on PostToolUse for same-session recall, and the recall hook's `find -s memory` reads both).

Backup is handled by the giant-tooling db-backup script (`giantmem/scripts/giantmem-db-backup.sh`) on a launchd timer (`com.bryan.giantmem-db-backup`, every 2h), not a hook. Per db it takes a consistent `sqlite3 .backup` of `live.db` + `archives.db`, runs `PRAGMA integrity_check`, gpg-encrypts (asymmetric, key `33F36CDDD530C52910A4608D61258A79557ECB4A`), and publishes to iCloud Drive (`giantmem-db-backups/`), overwriting the single current copy only after validation (one `.prev` kept). No VPS/tailscale. The DBs already hold the ingested sessions + memory md, so they are the backed-up unit. Restore: `gpg --decrypt live.db.gpg > live.db` — needs the private key, stored in 1Password.
