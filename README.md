# Claude Code Configuration

Personal Claude Code configuration with custom commands, hooks, agents, skills, and plugins. Managed via GNU stow from `~/dev/claude-code-config` and symlinked to `~/.claude`.

## Dependencies

This config is **not** standalone. It requires a companion repo for workspace lifecycle, archive search, and worktree management.

| Repo | What it provides |
|------|-----------------|
| [claude-code-config](https://gitlab.rechargeapps.net/bryan.grimes/claude-code-config) (this repo) | CLAUDE.md, hooks, commands, agents, skills, settings, MCP configs |
| [giant-tooling](https://github.com/bearded-giant/giant-tooling) | Workspace library, giantmem-archive, domain search, worktree helpers |

The workspace library (`workspace-lib.sh`) lives in giant-tooling and is symlinked into this repo at `lib/workspace/`. Session hooks, slash commands, and archive scripts all depend on it.

## Install

```bash
git clone git@gitlab.rechargeapps.net:bryan.grimes/claude-code-config.git ~/dev/claude-code-config
cd ~/dev/claude-code-config
./install.sh
```

The install script handles everything:

1. Checks prerequisites (git, stow, python3)
2. Clones [giant-tooling](https://github.com/bearded-giant/giant-tooling) to `~/dev/giant-tooling` if missing
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
| SessionStart | `memory_session_start.py` | Injects session primer from memory API |
| SessionStart | `workspace_session_hook.py` | Bootstraps `.giantmem/`, injects workspace context |
| UserPromptSubmit | `memory_inject.py` | Queries memory API for relevant memories |
| PreCompact | `memory_curate.py` | Triggers memory curation before compaction |
| SessionEnd | `memory_curate.py` | Triggers memory curation on session end |
| SessionEnd | `workspace_session_end.py` | Extracts session summary, indexes into search DB |
| PreToolUse | `guard_protected_paths.py` | Blocks writes to protected directories |

## Key Commands

### Search and History

| Command | Purpose |
|---------|---------|
| `/session-search` | Search conversation content across all projects |
| `/session-history` | List JSONL sessions |
| `/ws-history` | Show recent workspace sessions |
| `/ws-history-search` | Search workspace session files |

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
| `/ws-edit` | Edit workspace file |
| `/ws-note` | Add note to workspace |
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
