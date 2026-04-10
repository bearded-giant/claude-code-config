---
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Task
description: "Convert research, analysis, or rough ideas into a structured plan for /swarm-exec"
argument-hint: "<file path or inline description>"
model: opus
---

# Swarm Plan - Convert Input to Execution Plan

You take rough input (swarm analysis, research files, scope docs, inline descriptions) and produce a structured plan that `/swarm-exec` can consume directly.

> **Workflow position:** analyze → **plan** → execute
> `/swarm` → `/swarm-plan` → `/swarm-exec`

## Input

Parse: $ARGUMENTS

Accept any of:
- Swarm analysis output: `.giantmem/research/swarm-{topic}/analysis.md` or `worker-*.json`
- Research file: `.giantmem/research/*.md` or `.giantmem/features/{name}/research/*.md`
- Scope doc: `.giantmem/plans/*_scope.md`
- Feature spec: `.giantmem/features/{name}/spec.md`
- Arch brainstorm: `.giantmem/plans/*_brainstorm.md`
- Inline description: `"add preferences API with CRUD endpoints"`

If a file path is given, read it. If a directory is given (e.g., a swarm output dir), read all files in it.

Report:
```
Input: [file path or "inline"]
Type: [swarm-analysis | research | scope | feature-spec | brainstorm | inline]
```

## Phase 1: Extract Intent

From the input, extract:
- **Goal**: What is being built or changed (1-2 sentences)
- **Requirements**: Concrete things that must exist when done
- **Constraints**: Anything called out as off-limits or required patterns
- **Existing context**: File paths, function names, patterns mentioned in the input

If the input is vague, work with what's there. Do NOT invent requirements. Flag gaps in the output.

## Phase 2: Ground in Codebase

This is the critical step. The plan must reference real paths and real patterns.

### 2a. Resolve file paths

For every file the input mentions or implies:
- Use Glob to confirm it exists
- If it doesn't exist and needs to be created, find the correct directory by looking at sibling files
- Verify import paths, module names, directory structure

### 2b. Read patterns

For each area the plan touches, read 1-2 existing files in that area to understand:
- Naming conventions (classes, functions, files)
- Import patterns
- Registration patterns (blueprints, routes, models, etc.)
- Test patterns (fixtures, assertions, file naming)

### 2c. Identify integration points

Find the files that need modification to wire new code in:
- Route registration files
- Model imports
- Config files
- Test configuration

Use Task agents for parallel codebase exploration when touching 3+ areas:

```
Task tool:
  subagent_type: "Explore"
  prompt: "Find [pattern] in [area]. Report: file paths, naming conventions, registration patterns."
```

Report:
```
Codebase scan: [N] areas examined, [N] files read
Patterns: [brief summary of conventions found]
```

## Phase 3: Build Work Units

Decompose the goal into work units. Each work unit is:
- A single coherent chunk of work (one model, one service, one endpoint group)
- Assignable to one worker
- Has clear inputs and outputs

For each work unit, specify:
1. **What**: Description of what to implement
2. **Files to create**: Full paths, with a one-line description of contents
3. **Files to modify**: Full paths, with what changes
4. **Conventions to follow**: Specific patterns from Phase 2 (class naming, imports, etc.)
5. **Context needed**: What existing code the worker should read first

## Phase 4: Dependency Analysis

Map dependencies between work units:
- Which units can run in parallel (no shared files, no import dependencies)
- Which must be sequential (model before service, service before API)
- Group into parallel execution groups

```
Example:
  Group 1 (parallel): [model, config]
  Group 2 (parallel): [service] (depends on group 1)
  Group 3 (parallel): [api, tests] (depends on group 2)
```

## Phase 5: Write Plan

### Output location

- If active feature exists: `.giantmem/features/{name}/plans/swarm-plan.md`
- Otherwise: `.giantmem/plans/swarm-plan-{topic}.md`

### Output format

This is the exact format `/swarm-exec` consumes:

```markdown
# {Goal Title}

## Goal
{1-2 sentence description of what this accomplishes}

## Source
{Path to the input file this plan was derived from, or "inline"}

## Files to Create
- `{path}` - {what it contains and why}
- `{path}` - {what it contains and why}

## Files to Modify
- `{path}` - {what changes and why}
- `{path}` - {what changes and why}

## Work Units

### 1. {Unit Name}
**Create:** `{path}`
**Modify:** `{path}` (if any)
**Read first:** `{path}` (for patterns)
**What:** {specific implementation description, referencing conventions}

### 2. {Unit Name}
**Create:** `{path}`
**Read first:** `{path}`
**What:** {description}

## Dependencies
{Unit name} must complete before {unit name}.
{Unit name} and {unit name} can run in parallel.

## Parallel Groups
1. [{unit names}] - no dependencies
2. [{unit names}] - depends on group 1
3. [{unit names}] - depends on group 2

## Tests
- `{test file path}` - {what it tests}
- `{test file path}` - {what it tests}

## Success Criteria
- {concrete, verifiable criterion}
- {concrete, verifiable criterion}
- All new tests pass
- Existing tests still pass

## Gaps
{Anything from the input that was too vague to plan. Omit section if none.}
```

### Report to user

```
Plan written: {output path}
Work units: {N}
Parallel groups: {N}
Files to create: {N}
Files to modify: {N}

Next: /swarm-exec {output path}
```

## Constraints

- Every file path in the plan must be verified against the codebase (exists or correct directory for new files)
- Never invent requirements beyond what the input states
- Never include time or effort estimates
- Work unit descriptions must include the specific conventions to follow (from Phase 2), not just "follow existing patterns"
- If the input is too vague to produce file-level specifics, say so in the Gaps section rather than guessing
- Keep the plan concise -- workers need instructions, not essays

## Error Handling

**Input file not found:** Ask user for correct path.
**Codebase area doesn't exist:** Flag in Gaps section. The plan may be for greenfield work -- note which directories need to be created.
**Ambiguous input:** Produce the plan for what's clear, list ambiguities in Gaps. Don't block on unknowns.

Plan: $ARGUMENTS
