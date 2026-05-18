# Claude Code Commands

## History & Session Discovery

### Workspace History (current project)

| Command | Purpose |
|---------|---------|
| `/ws-history` | Show recent sessions from .giantmem/history/ |
| `/ws-history {n}` | Show last n sessions |
| `/ws-history {id}` | Show full session details |
| `/ws-history --search {query}` | Grep session files for keywords |

```bash
/ws-history
/ws-history 20
/ws-history abc123
/ws-history --search foo-service
```

### Global Session History (all projects)

| Command | Purpose |
|---------|---------|
| `/session-search {query}` | Search conversation content |
| `/session-search {query} --project {name}` | Search within project |
| `/session-search --list` | List recent JSONL sessions |
| `/session-search --list --project {name}` | List sessions in a project |

```bash
/session-search "bar validation"
/session-search "baz config" --project my-project
/session-search --list
/session-search --list --project my-project
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

Full usage (flags, model trade-offs, tips) inline in `commands/swarm.md`.

### /swarm-exec (Execution)

Parallel implementation with validation. Creates safety branch, never commits.

```
/swarm-exec .giantmem/plans/add-foo-api.md
```

Full usage (plan format, safeguards, tips) inline in `commands/swarm-exec.md`.

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
| `/ws-archive` | Archive to ~/giantmem_archive/ |
| `/rules` | Re-inject output rules |

---

## Cross-Repo Pairing

Single-session pattern. Main thread owns plan, sub-agents do deep dives in peer repo. Replaces deprecated `/sync-feature`.

| Command | Purpose |
|---------|---------|
| `/pair-repo {abs-path} [--role owner\|caller\|sibling]` | Attach peer repo, capture metadata, prime session |
| `/pair-repo --unpair {name}` | Remove peer from record |
| `/peer-scout {name} "<brief>" [--mode explore\|edit\|parallel] [--agent {type}]` | Dispatch sub-agent into paired repo |

```
/pair-repo /Users/bryan/dev/billing-api --role caller
/peer-scout billing-api "how does webhook auth validate JWTs?"
/peer-scout "find all callers of /api/v2/subs/update" --mode parallel
```

Peer record lives at `.giantmem/features/{active}/peers.md` (or `.giantmem/context/peers.md` if no active feature).

---

## Code Quality

| Command | Purpose |
|---------|---------|
| `/ts-check` | Run TypeScript lint, typecheck, tests |
| `/py-check` | Run Python formatting and tests |

```
/ts-check
/py-check
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
| `/create-mr-description` | Generate GitLab MR description |
| `/server-logs <env> [N]` | Tail preprod/prestage server.log |
