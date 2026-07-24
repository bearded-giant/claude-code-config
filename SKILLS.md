# Claude Code Skills

## History & Discovery

| Skill | Purpose |
|-------|---------|
| `/ws-history` | Show recent workspace sessions or `--search <q>` to grep |
| `/session-search {query}` | Search conversation content globally; `--list` for listing |

## Architecture

| Skill | Purpose |
|-------|---------|
| `/arch-discover` | Map existing system before refactoring |
| `/arch-brainstorm` | Two-phase architecture decision support |
| `/scope` | Create phased scope documents |
| `/c4-diagrams` | Generate C4 architecture diagrams in Mermaid |

## Swarm

| Skill | Purpose |
|-------|---------|
| `/swarm` | Hierarchical multi-model analysis (usage inline at bottom of file) |
| `/swarm-plan` | Convert analysis/research into exec plan |
| `/swarm-exec` | Parallel execution with validation (usage inline at bottom of file) |

## Feature Management

| Skill | Purpose |
|-------|---------|
| `/new-feature {name}` | Create feature folder with templates |
| `/list-features` | Display feature registry |
| `/feature-facts {name}` | Quick lookup of feature details |
| `/complete-feature {name}` | Mark feature complete |
| `/feature-report {name}` | Generate QA validation report |

## Todos

| Skill | Purpose |
|-------|---------|
| `/burn` | Burn down `claude:`-marked doit todos, priority-first (`--list`, `--priority`, `--max`, `--dry-run`) |

## Workspace

| Skill | Purpose |
|-------|---------|
| `/ws-init` | Bootstrap .giantmem/ structure |
| `/ws-archive` | Archive .giantmem/ to ~/giantmem_archive/ |
| `/rules` | Re-inject output rules mid-session |

## Code Quality

| Skill | Purpose |
|-------|---------|
| `/ts-check` | TypeScript lint, typecheck, tests |
| `/py-check` | Python formatting and tests |

## Search & Analysis

| Skill | Purpose |
|-------|---------|
| `/categorize-search {csv}` | Categorize `gl search code` results |

## Git & CI

| Skill | Purpose |
|-------|---------|
| `/server-logs <env> [N]` | Tail preprod/prestage server.log |

## Development

| Skill | Purpose |
|-------|---------|
| `/mcp-builder` | Build MCP servers in TypeScript or Python |
| `/mdlive` | Preview markdown as live-reloading HTML in browser |
| `/keybindings-help` | Customize keyboard shortcuts |

## Plugins: commit-commands

| Skill | Purpose |
|-------|---------|
| `/commit` | Create a git commit |
| `/commit-push-pr` | Commit, push, and open a PR |
| `/clean_gone` | Remove local branches deleted on remote |

## Plugins: feature-dev

| Skill | Purpose |
|-------|---------|
| `/feature-dev` | Guided feature development |
