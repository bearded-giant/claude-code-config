---
description: Two-phase architecture analysis - analyze constraints and risks before proposing solutions
---

# Architecture Brainstorm

Analyze architecture decisions thoroughly before proposing solutions.

> **Workflow step 2 of 3:** discover → brainstorm → scope
> Prereq: Run /arch-discover first if system is unfamiliar.

## Phase 1: Analysis

Before proposing solutions, investigate:

1. **Problem Definition**
   - What is the actual problem vs. symptoms?
   - Is this architecture, performance, integration, or migration?
   - What are the contributing factors?

2. **Context Gathering**
   - Read scratch/context/ for prior discoveries
   - Review relevant code sections
   - Identify existing patterns and conventions

3. **Constraints**
   - Existing system dependencies
   - Performance/scale requirements
   - Team familiarity with potential solutions
   - Timeline and rollback requirements

4. **Clarifying Questions**
   Ask about:
   - Requirements: What must the solution accomplish?
   - Constraints: Technical limitations, deadlines?
   - Priorities: Performance vs. maintainability vs. speed?
   - Scope: Does this need to solve related problems?

Output your Phase 1 findings, then **STOP and wait for answers** before continuing.

## Phase 2: Recommendations

After receiving answers:

1. Propose 2-3 approaches with clear trade-offs
2. Recommend one with reasoning tied to stated constraints
3. Identify risks and mitigations for recommended approach

**Output:**
- Write analysis to scratch/plans/{topic}_analysis.md (snake_case)
- Append key architectural decisions to scratch/context/discoveries.md:
  ```
  - YYYY-MM-DD HH:MM: [architecture] decision summary
  ```

## Output Style

- Be thorough but concise
- Focus on root causes, not symptoms
- Tie recommendations to specific constraints discussed

## Next Step

When recommendation is accepted, suggest:
> Ready for /scope to create phased implementation plan.

Topic: $ARGUMENTS
