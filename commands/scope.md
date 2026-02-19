---
description: Create phased scope document for large refactors and stack migrations
---

# Refactor Scope Document

Create a comprehensive scope document for a large refactor or migration.

> **Workflow step 3 of 3:** discover → brainstorm → scope

## Prerequisites

- .giantmem/WORKSPACE.md should describe the project purpose
- .giantmem/context/architecture.md should exist (run /arch-discover first if needed)
- Recommended: run /arch-brainstorm first to decide on approach

## Process

1. Read existing context from .giantmem/
2. Create scope document with phased breakdown
3. Each phase has dependencies and completion checkpoints

## Output Structure

Write to .giantmem/plans/{project}_scope.md (snake_case):

```markdown
# {Project} Scope

## Current State
[Summary from architecture discovery - what exists today]

## Target State
[Desired end state - what success looks like]

## Phase Breakdown

### Phase 1: Foundation
- [ ] 1.1 {task}
- [ ] 1.2 {task}
Dependencies: none
Checkpoint: {how to verify complete}

### Phase 2: Core Migration
- [ ] 2.1 {task}
- [ ] 2.2 {task}
Dependencies: Phase 1
Checkpoint: {verification criteria}

### Phase 3: Integration
- [ ] 3.1 {task}
Dependencies: Phase 2
Checkpoint: {verification criteria}

### Phase N: Deployment
- [ ] N.1 Migration scripts
- [ ] N.2 Rollback procedures
- [ ] N.3 Monitoring/alerting
Dependencies: All prior phases
Checkpoint: Production stable

## Risks & Mitigations
[From architecture discovery + new risks identified]

## Rollback Strategy
[How to revert at each phase if needed]

## Out of Scope
[Explicitly excluded from this refactor]
```

## Task Ordering

Order tasks by layer: data/schema → services → API → UI

Each task should be independently verifiable.

## Next Step

When scope is complete, suggest:
> Scope document ready. Begin implementation with Phase 1, or use /commit when phases complete.

Project: $ARGUMENTS
