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
| `/abandon-feature {name}` | Abandon feature (no spec merge) + archive |
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
| `/review-comment <mr-url>` | Session findings → human-voiced MR/PR comment, approve, post |

## Development

| Skill | Purpose |
|-------|---------|
| `/mcp-builder` | Build MCP servers in TypeScript or Python |
| `/mdlive` | Preview markdown as live-reloading HTML in browser |
| `/keybindings-help` | Customize keyboard shortcuts |
