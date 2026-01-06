# Claude Code Commands

## Architecture Workflow

For complex refactors and stack migrations:

```
/arch-discover {system}     → understand existing system
/arch-brainstorm {decision} → analyze options, get recommendations
/scope {project}            → create phased implementation plan
```

Each command reads context from the previous. Can also be used standalone.

### /arch-discover

Map an existing system before refactoring.

```
/arch-discover auth system
/arch-discover payment processing flow
```

Output: `scratch/context/architecture.md`

### /arch-brainstorm

Two-phase architecture decision support. Analyzes constraints, asks clarifying questions, then recommends approach.

```
/arch-brainstorm migrating to async workers
/arch-brainstorm replacing legacy ORM
```

Output: `scratch/plans/{topic}_analysis.md`

### /scope

Create phased scope document for large refactors.

```
/scope auth-service-migration
/scope checkout-redesign
```

Output: `scratch/plans/{project}_scope.md`

---

## Workspace Commands

| Command | Purpose |
|---------|---------|
| `/ws-init` | Bootstrap scratch/ structure |
| `/ws-note {text}` | Add note to WORKSPACE.md |
| `/ws-edit` | Open WORKSPACE.md |
| `/scratch-archive` | Archive to ~/scratch_archive/ |
| `/rules` | Re-inject output rules |

## Other

| Command | Purpose |
|---------|---------|
| `/create-mr` | Generate GitLab MR description |
| `/no-comments` | Strip superfluous comments from files |
| `/c4-diagrams` | Generate C4 architecture diagrams |
