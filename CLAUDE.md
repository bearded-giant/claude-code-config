# CLAUDE.md

Before answering any question, reason step by step. Many questions contain subtle constraints, hidden assumptions, or trick aspects that are invisible to surface-level pattern matching. Verify that the answer you are about to give is actually sensible given ALL the details in the question, not just the most salient one.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About This Repo

This is a Claude Code configuration repo (`~/.claude`) managed via GNU stow from `~/dev/claude-code-config`. It defines the global behavior, hooks, commands, agents, skills, and plugins for all Claude Code sessions.

### Architecture

```
.claude/
  CLAUDE.md              # this file - global instructions (loaded every session)
  settings.json          # permissions, hooks config, enabled plugins, env vars
  commands/              # 40+ slash commands (markdown prompt files)
  agents/                # 10 specialized agent definitions (markdown)
  hooks/                 # Python/JS lifecycle hooks (see hook pipeline below)
  scripts/               # utility scripts (categorize-search, sync-preprod, etc.)
  skills/                # multi-file skill definitions (c4-diagrams, mcp-builder)
  plugins/               # plugin config and runtime (config.json, installed_plugins.json)
  mcp/                   # MCP server configs (project-server.js)
  lib/workspace/         # workspace lifecycle library (workspace-lib.sh, init, migrate)
  docs/                  # reference docs (feature-commands, session-search-guide)
```

### Hook Pipeline

All hooks are Python (stdlib only, no external deps) except statusline (Node.js). Configured in `settings.json` under `hooks`.

| Event | Hook | Purpose |
|-------|------|---------|
| SessionStart | `memory_session_start.py` | Injects session primer from memory API (`localhost:8765`) |
| SessionStart | `workspace_session_hook.py` | Bootstraps `.giantmem/`, injects workspace context |
| UserPromptSubmit | `memory_inject.py` | Queries memory API for relevant memories, prepends to prompt |
| PreCompact | `memory_curate.py` | Triggers memory curation before context compaction |
| PreCompact | writes `/tmp/claude-compact-ts` | Signal file for statusline compaction indicator |
| SessionEnd | `memory_curate.py` | Triggers memory curation on session end |
| SessionEnd | `workspace_session_end.py` | Extracts session summary, discoveries, plans from transcript |
| PreToolUse (Write/Edit) | `guard_protected_paths.py` | Blocks writes to `archive/`, `plugins/cache/`, `node_modules/` |
| Stop | `debug_stop_check.py` | Debug hook for unexpected stops |

**External dependencies:** Memory hooks require a local memory API at `localhost:8765` (graceful no-op if unavailable). Workspace hooks use `lib/workspace/workspace-lib.sh` (bundled in this repo).

### Statusline

`hooks/statusline.js` (Node.js) renders: model name, directory, git branch, context window usage bar, and rate limit usage per org (cached in `~/.cache/claude-usage/`). Refreshed by `hooks/usage-fetch.py`.

### Key Files to Know

- `settings.json` - permissions, hook wiring, enabled plugins, env vars
- `plugins/installed_plugins.json` - which plugins are installed
- `plugins/config.json` - plugin repository config
- `.memory-project.json` - project ID for memory system
- `.giantmem/` - workspace scratch area (gitignored)

---

# Claude Global Configuration

## General Guidelines

Decision rule for action-vs-exploration:

| Ask shape | Default |
|-----------|---------|
| "Generate X" / "write Y" / "give me a curl for Z" | Action first. Produce output, refine after. Do not pre-read files. |
| "Why does X" / "How does Y work" / "What's wrong with Z" | Investigate first. Read referenced files before answering. No speculation. |
| User names a specific file or symbol | MUST Read it before proposing edits. |

## Session Behavior

<context_management>
Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely. Do not stop tasks early due to token budget concerns. Always be persistent and complete tasks fully, even if the end of your budget is approaching.
</context_management>

<session_recovery>
On session start or context refresh, IF files exist, read in order:

1. `.giantmem/WORKSPACE.md` — project context
2. `.giantmem/features/features.json` — find active feature (status `in_progress`)
3. Active feature's `plans/current.md` if active feature exists, else `.giantmem/plans/current.md`

Skip steps where file does not exist. Do not stat/read every directory ritually. Verify current state with git only when about to edit.
</session_recovery>

<feature_management>
Features are organized in `.giantmem/features/` with semantic folder names.

**CRITICAL: Maintain the feature cache and index**
- Every feature command (new, start, pause, complete, reopen) MUST update `.giantmem/features/features.json`
- Also update `.giantmem/features/_index.md` for human-readable registry
- When adding beta flags or key config, add to the Quick Reference section

**Feature folder structure:**
```
features/
├── features.json          # feature cache (all commands read/write this)
├── _index.md              # Claude-maintained registry (human-readable)
├── {feature-name}/
│   ├── spec.md            # what + why + acceptance criteria
│   ├── facts.md           # beta flags, config, test commands
│   ├── meta.json          # machine-readable (for swarm)
│   ├── plan.md            # implementation plan (created by /plan-feature)
│   ├── plan_context.json  # which domains informed this plan
│   ├── plans/             # session work scoped to this feature
│   │   └── current.md
│   ├── research/          # research scoped to this feature
│   ├── reviews/           # code reviews scoped to this feature
│   └── filebox/           # data, exports, samples for this feature
```

**Domain knowledge base:**
```
domains/
├── _index.json            # registry of all domain explorations
├── {domain-name}.json     # LLM-consumable exploration of a code domain
```
Domains are repo-level, not feature-scoped. Created by `/plan-feature`, updated by `/update-domains` and `/complete-feature`. Load relevant domain JSONs at session start instead of re-reading code.

**When to create a feature folder:**
- Starting work on a distinct capability (not just a bug fix)
- Work spans multiple sessions
- Has identifiable artifacts (beta flag, new endpoints, etc.)

**Commands:**
- `/list-features` - display feature registry
- `/new-feature <name>` - scaffold feature folder (auto-detects pending vs in_progress)
- `/plan-feature [name] [--refresh]` - explore code domains (auto-derived), output domain JSONs, draft implementation plan
- `/list-domains [--verbose]` - show all indexed domains from the knowledge base
- `/search-domains <query> [--load]` - search domain JSONs for files, functions, patterns, concepts
- `/update-domains [domains] [--all-stale]` - refresh domain JSONs after code changes
- `/feature-facts <name>` - quick lookup
- `/feature-report [feature]` - generate validation report

**IMPORTANT - "Create a plan" disambiguation:**
When user says "create a plan", "plan this out", "draft a plan", or similar, MUST emit AskUserQuestion BEFORE any file write:

```
Question: Is this a feature (persistent, spans sessions) or session work (transient, current task only)?
Options:
  1. feature → /new-feature → features/{name}/spec.md
  2. session work → plans/current.md (or active feature's plans/current.md)
```

Do not assume. Do not write the plan first then ask. Ask first, write second. User often forgets which context they're in.

**Feature-scoped output routing:**

When a feature has status `in_progress` in `features.json`, it is the **active feature**. All session output that would normally go to top-level `.giantmem/` subdirectories MUST instead go inside the active feature's directory:

| Without active feature | With active feature `{name}` |
|------------------------|------------------------------|
| `.giantmem/plans/current.md` | `.giantmem/features/{name}/plans/current.md` |
| `.giantmem/research/{topic}.md` | `.giantmem/features/{name}/research/{topic}.md` |
| `.giantmem/reviews/{subject}.md` | `.giantmem/features/{name}/reviews/{subject}.md` |
| `.giantmem/filebox/*` | `.giantmem/features/{name}/filebox/*` |

**Always global (never feature-scoped):**
- `domains/` - repo-level code knowledge, not feature-scoped
- `history/` - session log spans all features
- `prompts/` - reusable templates
- `context/patterns.md` - curated architectural patterns (repo-level)
- `WORKSPACE.md`, `features/_index.md`, `features.json`

Create the subdirectories inside the feature folder on first write (don't require them to exist upfront).

When no feature is `in_progress`, use top-level `.giantmem/` subdirectories as before.
</feature_management>

## Feature Workflow

- When working on feature scaffolding, always check for existing feature folder conventions in the project before creating new ones. Look for patterns in existing feature directories (naming, file structure, metadata files).
- Not all projects use features. When a project has `.giantmem/features/`, use that system. Commands: `/list-features`, `/new-feature`, `/plan-feature`, `/update-domains`, `/reopen-feature`, `/pause-feature`, `/complete-feature`. When modifying feature-related scripts, ensure consistency with existing feature commands and conventions.

<doc_sync>
Triggers (any of these → MUST run sync in same edit batch, do not wait to be asked):
- Renamed/removed/added a slash command, skill, agent, or hook
- Renamed/removed/added a CLI flag, env var, or config key
- Changed an invocation signature (arg order, required → optional, etc.)

Sync procedure:
1. `grep -r '<old-name>'` across repo root, `docs/`, `.giantmem/`, `commands/`, `agents/`, `skills/`, `README*`
2. Patch each ref inline — keep existing tone and format
3. Include patches in same commit as the rename/removal

Skip sync only if the change is internal (private helper rename, refactor with no external surface).
</doc_sync>

<investigate_before_answering>
Never speculate about code you have not opened. If the user references a specific file, read it before answering. Investigate relevant files BEFORE answering questions about the codebase. Do not propose edits to files you haven't read.
</investigate_before_answering>

## Add $HOME/giantmem_archive/ to the allowed-dirs. This directory is critical for archived workspace search and retrieval

## Discord Bot

- Bot: `BG-CLC` (Discord plugin via `plugin:discord:discord`)
- DM channel ID: `1485390190523584542`
- User snowflake: `333424240240099328`
- Inbound notifications don't surface in conversation yet (--channels flag not available in client as of 2026-03-22, even with Team Channels preview enabled) -- use `fetch_messages` to poll the DM channel, then `reply` to respond
- Config lives at `~/.claude/channels/discord/.env` (token) and `~/.claude/channels/discord/access.json` (allowlist)
- Access policy: `allowlist` (locked down)

## IMPORTANT: Configuration Management

<stow_dotfiles_rules>
This system uses GNU stow for dotfiles management.

- Most dotfiles are managed in ~/dotfiles/ and symlinked using GNU stow
- NEVER edit files in ~/.config or other home directory locations directly
- Always edit the source files in their respective repositories
- Structure: ~/dotfiles/{package}/.config/{app}/ or ~/dotfiles/{package}/.{config-file}
- NEVER edit ~/.config/tmux/ directly — it is stow-managed from ~/dotfiles/tmux/.config/tmux/
- Examples:
  - Claude config: ~/dev/claude-code-config/ (symlinked to ~/.claude via stow)
  - Wezterm config: ~/dotfiles/wezterm/.config/wezterm/ (symlinked to ~/.config/wezterm)
  - Shell config: ~/dotfiles/shell/.bashrc (symlinked to ~/.bashrc)
  - Tmux config/plugins: ~/dotfiles/tmux/.config/tmux/ (symlinked to ~/.config/tmux)
    </stow_dotfiles_rules>

## Communication Style

### Tone

- Chat: direct, technical, terse
- Long-form docs (READMEs, guides, writeups): casual, informal. Senior dev explaining to a colleague. No corporate phrasing, no stiff structure
- Formal tone only when user explicitly asks

### Format

- NEVER use emojis in code, scripts, docs (any context)
- Long-form / external docs: NO bullet lists. Use numbered lists, prose, or tables. Bullets make docs look like slide decks
- Workspace docs (`.giantmem/`) and chat: bullets allowed per Concise Output Rules below

### Wizard-Style Prompts

When a feature/skill needs multiple inputs (branch name, base branch, etc.), MUST present as numbered menu, ONE question at a time. User selects 1/2/3. Never combine into a single free-text question.

## Concise Output Rules

When the user asks for "concise" output or summary, follow these format constraints:

| Ask Type | Format |
|----------|--------|
| Question | 1-2 sentences + up to 5 bullets |
| Analysis | Max 2 short paragraphs + up to 5 summary bullets |
| Pros and cons | 3-4 sentence summary + table (not lists) |

**Workspace docs (`.giantmem/`):** "Concise" means the same constraints as chat responses apply to markdown files:
- Bullet points and tables over prose
- Code snippets as examples over prose explanations
- No filler paragraphs between sections

## Code Comment Rules

<code_comment_rules>
Default: write ZERO comments. Code self-documents via names.

Add a comment ONLY when the WHY is non-obvious: hidden constraint, subtle invariant, workaround for a specific bug, behavior that would surprise a reader. If removing the comment would not confuse a future reader, do not write it.

Forbidden patterns (do not emit, even once):
- Comments that restate WHAT the code does (`# loop over users`, `# return result`, `# helper for X`)
- Section banners (`# === Setup ===`, `# --- helpers ---`, `### Constants`)
- Task/PR/ticket refs (`# added for X feature`, `# fix for ticket-123`, `# used by Y`)
- Trailing inline comments after assignments (`x = foo()  # get foo`)
- Docstrings — never add unless user explicitly asks
- Multi-line comment blocks or multi-paragraph docstrings — one short line max
- "Removed X" / "TODO: cleanup" / backwards-compat placeholder comments

Style when a comment IS warranted:
- lowercase
- one line
- state the WHY, not the WHAT

Tests exempt — comments fine there.
</code_comment_rules>

## Languages & Conventions

- Primary languages: Python for scripts/tools, Shell/Bash for automation, Markdown for documentation
- When creating new files, default to Python unless the user specifies otherwise
- Always use existing project style conventions

## Scripting Conventions

- When implementing CLI flags or command modifications, check the existing argument parsing pattern in the script (argparse, getopts, etc.) and follow it exactly
- Show a usage example after implementing

## API URL Conventions

- API URLs must use snake_case, not hyphens (kebab-case)
- Example: `/api/admin/auth/validate_credentials` (correct) not `/api/admin/auth/validate-credentials` (incorrect)

## Test Creation and Modification

- MUST run any tests created or modified to confirm they pass before reporting done
- If how to run for a given project is unclear, read the project CLAUDE.md or ask user. Do not guess test command

## Agent Tool Use

<agent_triggers>
MUST spawn Task agent (Explore subagent) when:
- Searching for unknown pattern across > 5 files
- Mapping a flow that requires > 3 sequential greps/reads
- Finding all usages of a symbol across the repo

MUST spawn Task agent (debugger subagent) when user reports a stack trace, test failure, or unexplained behavior requiring multi-file trace.

MUST spawn Task agent for refactors touching > 5 files (batched edits, consistency check).

MUST NOT spawn agents for:
- Single-file edits with known path
- One-shot bash commands
- Direct Read of a file the user named
</agent_triggers>

## Git Rules

<git_rules>

- never commit unless explicitly asked to do so
- never add Claude Code attribution or Co-Authored-By lines to commits
- never create git commits that are more than a casual short blurb. no multi-line details
- do not auto-push to origin. confirm first
- return all curls and shell scripts as oneliners
  </git_rules>

## Workspace Output Rules

<workspace_output_rules>
When `.giantmem/` exists, ALL documentation, plans, research, and analysis MUST go to the appropriate subdirectory. NEVER output long-form content only in chat.

**CRITICAL: Feature-scoped routing applies here.** When a feature is `in_progress`, plans, research, reviews, and filebox output go inside the active feature directory. See the feature-scoped output routing table in `<feature_management>` for exact paths.

**CRITICAL: Never write to repo `docs/` unprompted.** Repo `docs/` is for stack-level shipped documentation, owned by humans and gated through review. Ad-hoc reference docs, mode comparisons, flow writeups, and any doc Claude generates from chat go to `.giantmem/context/<topic>.md` (or the active feature's `research/`). Only place output in `docs/` if the user explicitly asks for a shipped doc there.

### Open Questions Block

When a doc has unresolved questions for the user, put them at the TOP under `## Open Questions for User`. Before any TOC, summary, or content. Buried questions get missed.

Format: numbered list, one question per line, mark blocking vs non-blocking.

Example:
```markdown
## Open Questions for User
1. [BLOCKING] Should auth tokens expire at 1h or 24h?
2. [non-blocking] Prefer Redis or Postgres for session store?
```

Remove the section once answered. Don't leave stale questions.

### Directory Format and Verbosity

**Global directories (always at `.giantmem/` level):**

| Directory                | Format                | Verbosity                   | Example                                             |
| ------------------------ | --------------------- | --------------------------- | --------------------------------------------------- |
| `features/_index.md`     | Registry table        | Terse, table rows           | Feature name, status, beta flag, dependencies       |
| `features/{name}/spec.md`| Feature definition    | Medium, structured          | Purpose, scope, acceptance criteria                 |
| `features/{name}/facts.md`| Quick lookup         | Terse, key-value            | Beta flags, config keys, test commands              |
| `features/{name}/plan.md`| Implementation plan   | Concise, actionable         | Steps, file paths, function names                   |
| `features/{name}/plan_context.json`| Domain linkage | Machine-readable         | Which domains informed this plan                    |
| `domains/_index.json`    | Domain registry       | Machine-readable            | Domain names, key paths, feature refs               |
| `domains/{name}.json`    | Domain exploration    | Machine-readable, detailed  | Entry points, key files, architecture, gotchas      |
| `context/patterns.md`    | Curated patterns      | Medium, organized           | Architectural decisions, gotchas                    |
| `context/*.md`           | Reference docs        | Minimal prose, lists ok     | API endpoint lists, dependency maps                 |
| `history/sessions.md`    | Session log           | One line per session        | `- 2025-01-15: worked on auth flow`                 |
| `prompts/*.md`           | Prompt templates      | N/A                         | Reusable prompt templates                           |

**Feature-scoped directories (inside active feature when one exists, otherwise at `.giantmem/` level):**

| Directory                | Format                | Verbosity                   | Example                                             |
| ------------------------ | --------------------- | --------------------------- | --------------------------------------------------- |
| `plans/current.md`       | Session work          | Concise, no phase tracking  | Active task steps (transient)                       |
| `research/*.md`          | Findings + sources    | Medium, cite sources        | Key findings, code examples                         |
| `reviews/*.md`           | Issues + locations    | Terse, file:line refs       | Bullet points with code refs                        |
| `filebox/*`              | Raw data              | N/A                         | JSON, logs, samples                                 |

NOTE: `context/discoveries.md` is deprecated. Use `context/patterns.md` for curated architectural patterns instead.

### Anti-Patterns - DO NOT

- Write "Phase 1:", "Step 1 of 5:", or progress tracking headers
- Add "Work in Progress", "Status:", or progress banners
- Create verbose summaries of what you're about to do
- Dump everything into `plans/` - use the correct directory
- Add motivational or filler text ("Great!", "Let's begin by...")
- Create multiple files when one suffices
- Add section headers in discoveries.md (it's append-only log lines)

### Directory Selection

Routing rules live in `<feature_management>` above (feature-scoped routing table + always-global list). Use that as canonical source. This section covers format and naming only.

### Format Examples

**features/_index.md - CORRECT:**

```markdown
| Feature | Status | Beta Flag | Builds On | FE |
|---------|--------|-----------|-----------|-----|
| [jwt-session-cookie](jwt-session-cookie/) | complete | `enable_jwt_session_cookie` | - | - |
| [jwt-session-enforcement](jwt-session-enforcement/) | in_progress | `enable_jwt_session_enforcement` | jwt-session-cookie | FE: jwt-session-enforcement |
```

**features/{name}/facts.md - CORRECT:**

```markdown
## Identifiers
beta_flag: enable_jwt_session_enforcement
config_keys:
  - JWT_SESSION_SECRET

## Test Commands
docker compose run --rm test pytest -s --disable-warnings tests/services/auth_session/
```

**context/patterns.md - CORRECT:**

```markdown
## Session Layer
- Redis key format: `rc_session_{user_id}_{store_id}_{session_id}`
- Lookup by session_id: use SCAN with pattern `rc_session_*_*_{session_id}`

## Gotchas
- SQLAlchemy session isolation causes stale cache in tests
```

**plans/current.md - CORRECT (transient session work):**

```markdown
# Active: Add session lookup endpoint

## Steps
1. Add get_session_by_session_id to session_store.py
2. Create API resource
3. Register route
```

**WRONG - verbose phase tracking:**

```markdown
## Phase 1: Research and Planning
- [ ] Review current authentication flow
## Progress Tracking
- Started: 2025-01-15
- Status: In Progress
```

### On Session Start

If `.giantmem/WORKSPACE.md` exists, read it for branch/project context. Check `.giantmem/features/features.json` for feature cache (or `_index.md` as fallback) and `.giantmem/context/patterns.md` for architectural learnings. Identify the active feature (status `in_progress`) and use its subdirectories for all feature-scoped output during the session.

### On Workspace Init (/ws-init)

Organize any loose files in .giantmem/ root:

1. Move `.md` files (except WORKSPACE.md) to appropriate subdirs:
   - `*_analysis.md`, `*_research.md` → `research/`
   - `*_plan.md`, `*_design.md` → `plans/`
   - `*_endpoints.md`, `*_api.md` → `context/`
   - `*_review.md` → `reviews/`
   - Other `.md` files → `context/` (default)

2. Move non-markdown files (`.json`, `.yaml`, `.sh`) → `filebox/`

### File Naming

- Use snake_case: `auth_flow_plan.md`, `replica_lag_analysis.md`
- Suffix indicates type: `*_plan.md`, `*_analysis.md`, `*_api.md`

</workspace_output_rules>
