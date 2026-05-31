# BG's Claude Code Configuration

My personal Claude Code configuration with custom commands, hooks, agents, skills, and plugins. Managed via GNU stow from `~/dev/claude-code-config` and symlinked to `~/.claude`.

## Dependencies

This config is **not** standalone. It requires a companion repo for workspace lifecycle, archive search, and worktree management.

| Repo | What it provides |
|------|-----------------|
| [claude-code-config](https://github.com/bearded-giant/claude-code-config) (this repo) | CLAUDE.md, hooks, commands, agents, skills, settings, MCP configs |
| [giant-tooling](https://github.com/bearded-giant/giant-tooling) | Workspace library, giantmem-archive, domain search, worktree helpers |

The workspace library (`workspace-lib.sh`) lives in giant-tooling and is symlinked into this repo at `lib/workspace/`. Session hooks, slash commands, and archive scripts all depend on it.

## Install

```bash
git clone https://github.com/bearded-giant/claude-code-config.git
cd claude-code-config
./install.sh
```

Clone it wherever you want. The install script detects its own location and clones giant-tooling as a sibling directory. To put giant-tooling somewhere else:

```bash
./install.sh --tooling-dir ~/my/path/giant-tooling
```

The install script handles everything:

1. Checks prerequisites (git, stow, python3)
2. Clones [giant-tooling](https://github.com/bearded-giant/giant-tooling) as a sibling directory if missing
3. Creates symlink: `lib/workspace/` -> `giant-tooling/workspace/`
4. Runs stow to wire `~/.claude`
5. Builds the initial search index
6. Prints any shell env lines you need to add

After install, restart Claude Code.

### Shell setup

The install script will tell you what to add. Typically:

```bash
export GIANT_TOOLING_DIR="$HOME/dev/giant-tooling"
source "$GIANT_TOOLING_DIR/workspace/workspace-lib.sh"

alias gmq='$GIANT_TOOLING_DIR/giantmem-archive/giantmem-search.py'
alias giantmem-archive='$GIANT_TOOLING_DIR/giantmem-archive/giantmem-archive.sh'
alias domains='$GIANT_TOOLING_DIR/domain-search/domains'
```

### Prerequisites

Required: git, stow, python3 (3.10+), Claude Code CLI

Optional: fzf (interactive search picker), bat (search previews)

## Structure

```
.claude/
  CLAUDE.md              # global instructions (loaded every session)
  settings.json          # permissions, hooks, MCP servers, env vars
  commands/              # 40+ slash commands
  agents/                # 10 specialized agent definitions
  hooks/                 # Python/JS lifecycle hooks
  scripts/               # utility scripts (session-search, sync-preprod)
  skills/                # multi-file skill definitions
  plugins/               # plugin config and runtime
  mcp/                   # MCP server configs
  lib/workspace/         # -> giant-tooling/workspace/ (symlink)
  docs/                  # reference docs
```

## Hook Pipeline

All hooks are Python (stdlib only) except statusline (Node.js). Configured in `settings.json`.

| Event | Hook | Purpose |
|-------|------|---------|
| SessionStart | `sync_settings.py` | Merges repo `settings.json` into live `~/.claude/settings.json` (see note below) |
| SessionStart | `session_prime.py` | Injects giantmem workspace/feature primer |
| SessionStart | `workspace_session_hook.py` | Bootstraps `.giantmem/`, injects workspace context |
| UserPromptSubmit | `giantmem_recall.py` | Injects top giantmem FTS5 hits for the prompt (cross-project recall) |
| SessionEnd | `session_end_ingest.py` | Ingests the session transcript into giantmem |
| SessionEnd | `workspace_session_end.py` | Extracts session summary, indexes into search DB |
| PostToolUse | `live_index.py` | Indexes `.giantmem/` + harness memory `*.md` writes into giantmem live.db |
| PreToolUse | `guard_protected_paths.py` | Blocks writes to protected directories |

Unlike everything else here, `settings.json` is **not** a stow symlink. Claude Code rewrites that file at runtime (theme, model, plugin toggles, survey state), so a symlink either gets clobbered by the app's atomic save or pollutes the git tree with machine-local state. Instead `sync_settings.py` runs each session start and merges: the repo wins for structural config (hooks, env, statusLine, mcpServers, marketplaces, permission mode); `enabledPlugins` and `permissions.allow`/`ask` are unioned so runtime additions survive; and `model`, `effortLevel`, `theme`, `feedbackSurveyState` stay whatever the live file says. Edit structural config in the repo and it goes live next session — no restow, no manual copy. It only writes the home file, never the repo copy, so `git status` stays clean.

## Key Commands

### Search and History

| Command | Purpose |
|---------|---------|
| `/session-search` | Search/list Claude JSONL sessions across projects (use `--list` for listing) |
| `/ws-history` | Show recent workspace sessions or `--search <q>` to grep |
| `/server-logs <env> [N]` | Grab N lines of preprod/prestage server logs |

### Analysis (read-only)

| Command | Purpose |
|---------|---------|
| `/swarm <task>` | Parallel multi-model analysis with Haiku workers |
| `/arch-discover` | Map architecture before refactoring |
| `/arch-brainstorm` | Two-phase architecture decisions |

### Execution (read-write)

| Command | Purpose |
|---------|---------|
| `/swarm-exec <plan>` | Parallel execution with validation (never commits) |
| `/scope` | Phased scope documents for migrations |

### Features

| Command | Purpose |
|---------|---------|
| `/new-feature <name>` | Scaffold a feature folder |
| `/plan-feature` | Explore code domains, draft implementation plan |
| `/list-features` | Show feature registry |
| `/complete-feature` | Mark feature complete, update tracking |

### Workspace

| Command | Purpose |
|---------|---------|
| `/ws-init` | Initialize `.giantmem/` workspace |
| `/ws-archive` | Archive workspace to `~/giantmem_archive/` |

## Archive Search

Unified FTS5 search across workspace archives, session transcripts, and domain knowledge. See [giant-tooling/docs/search-usage.md](https://github.com/bearded-giant/giant-tooling/blob/main/docs/search-usage.md) for full usage.

```bash
gmq search "jwt refresh"                # search everything
gmq search "jwt refresh" -s session     # sessions only
gmq search "auth flow" --topic auth     # by session topic
gmq stats                               # index breakdown
```

Also available as MCP tool `search_archive` for agent use.

## License

MIT
