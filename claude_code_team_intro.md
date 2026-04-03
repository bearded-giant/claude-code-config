# Claude Code Team Intro

## Setup

1. Install: `curl https://pkg.claude.ai/install.sh | bash`
2. Auth: `claude auth login` (supports `--sso` for teams)
3. Verify: `claude --version`
4. Update: `claude update`

## Core Slash Commands

| Command | What it does |
|---------|-------------|
| `/init` | Generate a CLAUDE.md for the project (discovers build/test commands, conventions) |
| `/compact` | Compress conversation to reclaim context space |
| `/cost` | Show token usage and cost for the session |
| `/clear` | Fresh conversation |
| `/config` | Change model, permission mode, effort level mid-session |
| `/help` | Show all commands |
| `/memory` | Browse/edit CLAUDE.md files and auto memory |
| `/review` | Code review |
| `/doctor` | Diagnose installation issues |
| `/rename` | Rename the current session |
| `/vim` | Toggle vim-style editing mode |

## Key Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Esc Esc` | Rewind / undo last action |
| `Shift+Tab` | Toggle permission modes (normal / auto-accept / plan) |
| `Ctrl+C` | Cancel generation |
| `Ctrl+R` | Search command history |
| `Ctrl+L` | Clear screen |
| `Ctrl+O` | Toggle verbose output |
| `?` | Show all shortcuts for your terminal |

## CLAUDE.md -- The Big One for Teams

Three levels, all loaded automatically into every session:

| Level | Location | Shared? | Purpose |
|-------|----------|---------|---------|
| Project | `./CLAUDE.md` or `.claude/CLAUDE.md` | Yes (git) | Team conventions, build/test commands, architecture notes |
| User | `~/.claude/CLAUDE.md` | No | Personal preferences, workflows |
| Organization | System-level path | Yes (IT-managed) | Company-wide policies, compliance |

Run `/init` on each repo to bootstrap the project-level file. This is the single highest-leverage thing for team consistency.

### Path-Scoped Rules

Place markdown files in `.claude/rules/` with frontmatter to scope them:

```markdown
---
paths:
  - "src/api/**/*.ts"
---

# API Rules
- All endpoints require input validation
- Use standard error response format
```

## Permission Modes

| Mode | Behavior | When to use |
|------|----------|-------------|
| Normal (default) | Asks before each tool use | Day-to-day development |
| Plan mode | Shows plan first, executes after approval | Risky changes, code review |
| Auto-accept | Pre-approved tools run without prompting | Trusted environments, speed |

Toggle with `Shift+Tab` during a session, or start with `--permission-mode plan`.

Configure allowed/denied tools in `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": ["Read", "Bash(git:*)"],
    "deny": ["Bash(rm:*)"]
  }
}
```

## Useful CLI Flags

| Flag | Purpose | Example |
|------|---------|---------|
| `-p "query"` | Non-interactive print mode (CI/scripts/piping) | `claude -p "explain this file" < file.ts` |
| `-c` | Continue last conversation | `claude -c` |
| `-n "name"` | Name the session for easy resume | `claude -n "auth-refactor"` |
| `--resume` | Resume a specific past session | `claude --resume auth-refactor` |
| `--model` | Use a specific model | `claude --model opus` |
| `--effort` | Set reasoning effort (low/medium/high) | `claude --effort high` |
| `--add-dir` | Add additional working directories | `claude --add-dir ../shared-lib` |
| `--debug` | Enable debug logging | `claude --debug` |

## Context Window Management

Context is finite. Key strategies:

1. `/compact` -- compress conversation history, reclaim space (auto-compact also available)
2. `/cost` -- check token usage before starting long tasks
3. Be specific -- "fix line 45 in auth.py" beats "fix the auth module"
4. Subagents handle isolated investigations in separate context windows automatically

## MCP Server Integration

Model Context Protocol connects external tools (databases, APIs, monitoring).

```bash
claude mcp list              # view configured servers
claude mcp add               # add a new server (interactive)
```

Configure shared MCP servers in `.claude/settings.json` so the whole team gets them.

## IDE Integrations

| IDE | How |
|-----|-----|
| VS Code | Install "Claude Code" extension from marketplace |
| JetBrains | Install from plugin marketplace (IntelliJ, WebStorm, PyCharm, etc.) |

Both provide sidebar integration and terminal access.

## Hooks (Automation)

Hooks run shell commands in response to events. Configured in `settings.json`.

| Hook Event | Example Use |
|-----------|-------------|
| `PostToolUse` (matcher: Edit) | Auto-format code after every edit |
| `PreToolUse` | Block edits to protected files |
| `SessionStart` | Load environment, print status |

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [{ "type": "command", "command": "npx prettier --write {{filePath}}" }]
      }
    ]
  }
}
```

## Quick Reference Cheat Sheet

```
STARTING
  claude                        new session
  claude -n "feature-name"      named session
  claude -c                     continue last session
  claude --resume               pick a past session

DURING SESSION
  /init                         generate CLAUDE.md
  /config                       change settings
  /cost                         check token usage
  /compact                      reclaim context space
  /memory                       browse/edit instructions
  /review                       code review
  Shift+Tab                     toggle permission mode
  Esc Esc                       rewind/undo
  ?                             show all shortcuts

CI / SCRIPTING
  claude -p "query"             non-interactive output
  cat file | claude -p "..."    pipe input
```

## Best Practices

1. Invest in your CLAUDE.md -- it's the biggest lever for consistent team output
2. Start specific -- clear prompts get better results than vague ones
3. Use plan mode before major changes -- verify the approach before execution
4. Compact early -- don't wait until context is exhausted
5. Name sessions you'll want to resume later
6. Put team conventions in `.claude/settings.json` and commit it to the repo
