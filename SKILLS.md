# Claude Code Skills

## History & Discovery

| Skill | Purpose |
|-------|---------|
| `/ws-history` | Show recent workspace sessions or `--search <q>` to grep |
| `/session-search {query}` | Search conversation content globally; `--list` for listing |

## Architecture

| Skill | Purpose |
|-------|---------|
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
| `/burn` | Burn down `claude:`-marked doit todos, sequence-first then priority (`--list`, `--priority`, `--max`, `--dry-run`) |

## Workspace

| Skill | Purpose |
|-------|---------|
| `/ws-init` | Bootstrap .giantmem/ structure |
| `/ws-archive` | Archive .giantmem/ to ~/giantmem_archive/ |
| `/rules` | Re-inject output rules mid-session |
| `/notion-publish [path \| --feature X \| --dirty \| --index \| --dry-run]` | Push .giantmem/ docs into the personal Notion page tree `Claude Artifacts / repo / worktree / feature`; policy in `config/notion-publish.yaml` (auto on write vs on request), never asks; upserts by frontmatter `notion:`; regenerates both index surfaces (catalog page + `Docs catalog` DB rows) after every push, or on `--index` |
| `obsidian-note` | Write Claude-authored md into the Obsidian vault `~/Recharge-Notes/areas/<area>/` with the vault frontmatter contract plus `created`; `scripts/note.py new` (title, area, tags, project auto from git) and `list` (filter area/project/tag/since). Fires on "note this", "write this up", "save to obsidian", any md deliverable that is not feature state. Never Desktop; Notion only on explicit publish |

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
| `/greptile [review [mr] [--force] \| init \| rule <note-url> \| sync [mr-url]]` | `review` posts `@greptile review` on the branch's MR (skips if head already reviewed). Own `.greptile/`: scaffold, invalid suggestion → repo rule (asks), auto-approve risk sync; babysit calls it for `greptile` threads |

## Development

| Skill | Purpose |
|-------|---------|
| `/mcp-builder` | Build MCP servers in TypeScript or Python |
| `/mdlive` | Preview markdown as live-reloading HTML in browser; on request only, never auto-fires |
| `/keybindings-help` | Customize keyboard shortcuts |
