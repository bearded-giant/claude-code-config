---
description: Systematic architecture discovery for understanding complex systems before refactoring
---

# Architecture Discovery

Map an unfamiliar system (entry points, layers, dependencies, risks) before refactoring.

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

**Primary output:** `.giantmem/context/architecture.md`
- Component map (text or mermaid)
- Data flow diagram
- Integration points list
- Refactor risks and gotchas

**Curated patterns:** Add any reusable architectural patterns or gotchas worth keeping to `.giantmem/context/patterns.md` (see `workspace-rules` skill for format).

For visual diagrams, invoke the `c4-diagrams` skill (auto-fires on "diagram this" / "map this system").

## Next Step

When discovery is complete, suggest:
> Ready for /arch-brainstorm to analyze approach options, or /scope to create implementation plan.

Focus area: $ARGUMENTS
