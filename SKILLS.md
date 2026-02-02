# Claude Code Skills

## Architecture

| Skill | Purpose |
|-------|---------|
| `/c4-diagrams` | Generate C4 architecture diagrams (Context, Container levels) in Mermaid |

## Workspace

| Skill | Purpose |
|-------|---------|
| `/ws-init` | Bootstrap scratch/ structure in current directory |
| `/ws-note {text}` | Add timestamped note to WORKSPACE.md |
| `/ws-edit` | Open WORKSPACE.md in default editor |
| `/scratch-archive` | Archive scratch/ to ~/scratch_archive/ |
| `/rules` | Re-inject workspace and output rules mid-session |

## Search & Analysis

| Skill | Purpose |
|-------|---------|
| `/categorize-search [csv]` | Categorize `gl search code` CSV results via parallel haiku workers |

## Git & Code

| Skill | Purpose |
|-------|---------|
| `/create-mr` | Generate GitLab MR description from branch commits |
| `/no-comments {files}` | Strip superfluous comments from specified files |

## Plugins: commit-commands

| Skill | Purpose |
|-------|---------|
| `/commit` | Create a git commit |
| `/commit-push-pr` | Commit, push, and open a PR |
| `/clean_gone` | Remove local branches deleted on remote |

## Plugins: feature-dev

| Skill | Purpose |
|-------|---------|
| `/feature-dev` | Guided feature development with codebase understanding |

## Development

| Skill | Purpose |
|-------|---------|
| `/mcp-builder` | Build MCP servers in TypeScript or Python |
