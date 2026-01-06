---
description: Systematic architecture discovery for understanding complex systems before refactoring
---

# Architecture Discovery

Map an existing complex system to understand it before refactoring.

> **Workflow step 1 of 3:** discover → brainstorm → scope

## Process

1. **Entry Points**
   - Identify main entry points (app factory, CLI, API routes, workers)
   - Document how requests/data enter the system

2. **Trace Dependencies**
   Layer by layer:
   - Data layer: models, schemas, migrations, database connections
   - Service layer: business logic, external integrations, shared utilities
   - API layer: routes, serialization, middleware
   - Background: celery tasks, cron jobs, event handlers

3. **For Each Major Component**
   Document:
   - Responsibility (one sentence)
   - Key dependencies (what it imports/calls)
   - Integration points (external APIs, databases, queues, caches)
   - Coupling issues or technical debt

4. **Patterns & Anti-patterns**
   - What patterns are used consistently?
   - Where does the code deviate from patterns?
   - What would break if refactored naively?

5. **Refactor Risks**
   - Hidden coupling or shared state
   - Implicit dependencies (environment, timing, order)
   - Areas with poor test coverage

## Output

**Primary output:** scratch/context/architecture.md
- Component map (text or mermaid)
- Data flow diagram
- Integration points list
- Refactor risks and gotchas

**Discoveries:** Append to scratch/context/discoveries.md using format:
```
- YYYY-MM-DD HH:MM: [category] terse one-line finding
```
Categories: architecture, pattern, gotcha, dependency, convention, entry, config

Example:
```
- 2025-01-15 10:22: [architecture] services use dependency injection via containers.py
- 2025-01-15 10:25: [gotcha] celery tasks must be imported in __init__.py to register
```

If visual diagrams would help, suggest running /c4-diagrams after.

## Next Step

When discovery is complete, suggest:
> Ready for /arch-brainstorm to analyze approach options, or /scope to create implementation plan.

Focus area: $ARGUMENTS
