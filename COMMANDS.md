# Claude Code Commands

## History & Session Discovery

### Workspace History (current project)

| Command | Purpose |
|---------|---------|
| `/ws-history` | Show recent sessions from .giantmem/history/ |
| `/ws-history {n}` | Show last n sessions |
| `/ws-history {id}` | Show full session details |
| `/ws-history-search {query}` | Search session files for keywords |

```bash
/ws-history
/ws-history 20
/ws-history abc123
/ws-history-search foo-service
```

### Global Session History (all projects)

| Command | Purpose |
|---------|---------|
| `/session-history` | List recent JSONL sessions |
| `/session-history {project}` | Filter by project name |
| `/session-search {query}` | Search conversation content |
| `/session-search {query} {project}` | Search within project |

```bash
/session-history
/session-history my-project
/session-search "bar validation"
/session-search "baz config" my-project
```

---

## Architecture Workflow

For complex refactors and stack migrations:

```
/arch-discover {system}     -> understand existing system
/arch-brainstorm {decision} -> analyze options, get recommendations
/scope {project}            -> create phased implementation plan
```

### /arch-discover

Map an existing system before refactoring.

```
/arch-discover foo-service
/arch-discover bar processing flow
```

Output: `.giantmem/context/architecture.md`

### /arch-brainstorm

Two-phase architecture decision support. Analyzes constraints, asks clarifying questions, then recommends approach.

```
/arch-brainstorm migrating foo to async
/arch-brainstorm replacing bar-orm
```

Output: `.giantmem/plans/{topic}_analysis.md`

### /scope

Create phased scope document for large refactors.

```
/scope foo-service-migration
/scope bar-redesign
```

Output: `.giantmem/plans/{project}_scope.md`

---

## Swarm Commands

### /swarm (Analysis)

Spawns 3-8 Haiku workers in parallel for deep analysis. Opus validates.

```
/swarm analyze src/foo/ for migration risks
/swarm review design.md against requirements.md
/swarm compare redis vs memcached for sessions
```

See `/swarm-usage` for full documentation.

### /swarm-exec (Execution)

Parallel implementation with validation. Creates safety branch, never commits.

```
/swarm-exec .giantmem/plans/add-foo-api.md
```

See `/swarm-exec-usage` for full documentation.

---

## Feature Management

| Command | Purpose |
|---------|---------|
| `/new-feature {name}` | Create feature folder with templates |
| `/list-features` | Display feature registry |
| `/feature-facts {name}` | Quick lookup of feature details |
| `/complete-feature {name}` | Mark feature complete, update index |
| `/feature-report {name}` | Generate QA validation report |

```
/new-feature foo-integration
/list-features
/feature-facts foo-integration
/complete-feature foo-integration
```

---

## Workspace Commands

| Command | Purpose |
|---------|---------|
| `/ws-init` | Bootstrap .giantmem/ structure |
| `/ws-note {text}` | Add note to WORKSPACE.md |
| `/ws-edit` | Open WORKSPACE.md |
| `/ws-archive` | Archive to ~/giantmem_archive/ |
| `/rules` | Re-inject output rules |

---

## Code Quality

| Command | Purpose |
|---------|---------|
| `/ts-check` | Run TypeScript lint, typecheck, tests |
| `/py-check` | Run Python formatting and tests |
| `/no-comments {files}` | Strip superfluous comments |

```
/ts-check
/py-check
/no-comments src/foo.py src/bar.py
```

---

## Search & Analysis

| Command | Purpose |
|---------|---------|
| `/categorize-search {csv}` | Categorize `gl search code` results |

---

## Git & CI

| Command | Purpose |
|---------|---------|
| `/create-mr` | Generate GitLab MR description |
