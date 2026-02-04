# Claude Code Configuration

Personal Claude Code configuration with custom commands, hooks, and workflows.

## Installation

Clone and symlink to `~/.claude`:

```bash
git clone https://github.com/youruser/claude-code-config.git
ln -s /path/to/claude-code-config ~/.claude
```

Or with GNU stow (if in dotfiles):
```bash
cd ~/dotfiles
stow claude-code
```

## Structure

```
.claude/
  CLAUDE.md              # global instructions (loaded every session)
  settings.json          # permissions and tool config
  commands/              # custom slash commands
  agents/                # agent configurations
  hooks/                 # lifecycle hooks
  scripts/               # utility scripts
  skills/                # reusable skill definitions
  mcp/                   # MCP server configs
```

## Key Commands

### History & Discovery

| Command | Purpose |
|---------|---------|
| `/ws-history` | Show recent workspace sessions |
| `/ws-history-search` | Search workspace session files |
| `/session-history` | List JSONL sessions across projects |
| `/session-search` | Search conversation content globally |

### Analysis (Read-Only)

| Command | Purpose |
|---------|---------|
| `/swarm <task>` | Hierarchical multi-model analysis with parallel Haiku workers |
| `/arch-discover` | Map architecture before refactoring |
| `/arch-brainstorm` | Two-phase architecture decisions |

### Execution (Read-Write)

| Command | Purpose |
|---------|---------|
| `/swarm-exec <plan>` | Parallel execution with validation (never commits) |
| `/scope` | Create phased scope documents for migrations |

### Workspace

| Command | Purpose |
|---------|---------|
| `/ws-init` | Initialize scratch workspace |
| `/ws-edit` | Edit workspace file |
| `/ws-note` | Add note to workspace |

## Swarm System

Two-command system for analysis and execution:

```
/arch-discover src/      # map the territory
/swarm analyze src/      # deep parallel analysis
write plan               # based on findings
/swarm review plan.md    # validate plan
/swarm-exec plan.md      # execute (creates branch, never commits)
git diff                 # you review
git commit               # you commit
```

### /swarm (Analysis)

Spawns 3-8 Haiku workers in parallel, each analyzing an aspect. Opus validator synthesizes findings. Iterates until convergence (max 5).

```bash
/swarm analyze src/auth/ for OAuth2 migration risks
/swarm review design.md against requirements.md
/swarm compare Redis vs Memcached for sessions
```

### /swarm-exec (Execution)

Implements plans with parallel workers. Creates safety branch, runs tests, validates changes.

**Safeguards:**
- NEVER commits (you review and commit)
- NEVER pushes (you push when ready)
- Creates `swarm-exec/{timestamp}` branch
- Stops if working tree is dirty

```bash
/swarm-exec scratch/plans/add-preferences-api.md
```

## Hooks

Lifecycle hooks in `hooks/`:
- `startup.sh` - runs on session start
- Pre/post tool hooks available

## Requirements

- Claude Code CLI
- PAL MCP (optional, for Gemini/Codex enhancement)
- Git

## Customization

1. Edit `CLAUDE.md` for global instructions
2. Add commands to `commands/`
3. Modify `settings.json` for permissions

## License

MIT
