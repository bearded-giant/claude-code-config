---
allowed-tools:
  - Read
  - Write
  - Task
  - Glob
  - Grep
  - mcp__pal__clink
description: "Hierarchical swarm: Opus orchestrator -> Haiku workers (Gemini) -> Opus validator (Codex)"
argument-hint: "<task description with optional file/directory references>"
model: opus
---

# Swarm - Hierarchical Multi-Model Task Analysis

You are the **Opus Orchestrator**, a lightweight coordinator. You do NOT analyze - you delegate to:
1. **Haiku Workers**: Fast parallel analysts (Gemini-enhanced via PAL clink)
2. **Opus Validator**: Deep synthesis (Codex-enhanced via PAL clink)

## Architecture

```
ORCHESTRATOR (you)
    |-- Parse task -> detect type (REVIEW/ANALYSIS/COMPARISON/CUSTOM)
    |-- Load template from swarm-templates/{type}.md
    |-- Spawn Haiku workers IN PARALLEL (one per aspect)
    |       Workers use: Read/Glob/Grep + Gemini via PAL clink
    |-- Collect all worker JSON reports
    |-- Spawn Opus Validator with reports
    |       Validator uses: Codex via PAL clink
    |-- Check convergence (template-specific)
    |-- If not converged and < 5 iterations: GOTO spawn workers
    |-- Output synthesis to conversation
```

## Phase 0: Parse Task

Detect task type from keywords in: $ARGUMENTS

| Type | Keywords | Template |
|------|----------|----------|
| REVIEW | review, evaluate, assess, check, audit | review.md |
| ANALYSIS | analyze, examine, investigate, study, explore, architecture | analysis.md |
| COMPARISON | compare, contrast, versus, vs, between | comparison.md |
| CUSTOM | (no match) | custom.md |

Extract file/directory references. Use Glob to resolve ambiguous references. Read files to pass as context.

Report: `Task: [type] | Files: [count] | Template: [name]`

## Phase 1: Load Template

Read: `commands/swarm-templates/{type}.md`

Extract:
- Aspects to analyze (3-8)
- Convergence type and thresholds
- Output schema for workers

Adjust aspects based on actual task (remove irrelevant, add specific).

Report: `Aspects: [list] | Convergence: [type]`

## Phase 2: Spawn Haiku Workers (PARALLEL)

**CRITICAL**: Spawn ALL workers in ONE message using multiple Task tool calls.

For each aspect, spawn:
```
Task tool:
  subagent_type: "general-purpose"
  model: "haiku"
  prompt: [see worker prompt below]
```

### Worker Prompt Template

```
You are a Haiku Worker analyzing: [ASPECT NAME]

## Your Focus
[Aspect description and questions from template]

## Task Context
[Original task: $ARGUMENTS]

## Files to Examine
[File contents or instructions to use Read/Glob/Grep]

## Instructions
1. Use Read/Glob/Grep to examine relevant code
2. Consult Gemini for enhanced analysis:
   ```
   mcp__pal__clink:
     cli_name: "gemini"
     prompt: "[Your analysis question]"
   ```
3. Output ONLY valid JSON matching schema

## Output Schema
[Schema from template]
```

Report: `Workers dispatched: [N] (parallel, Gemini-enabled)`

## Phase 3: Collect Reports

Wait for all workers. Parse JSON responses.

Report summary of each worker's verdict/confidence.

## Phase 4: Spawn Opus Validator

```
Task tool:
  subagent_type: "general-purpose"
  model: "opus"
  prompt: [see validator prompt below]
```

### Validator Prompt Template

```
You are the Opus Validator. Synthesize worker reports and calculate convergence.

## Worker Reports
[All worker JSON outputs]

## Convergence Context
Type: [from template]
Iteration: [N]
Previous metrics: [if iteration > 1]

## Your Tasks
1. Aggregate findings by aspect
2. Resolve conflicts (use Codex via PAL clink if needed):
   mcp__pal__clink:
     cli_name: "codex"
     prompt: "Resolve conflict: [description]"
3. Validate critical issues
4. Calculate convergence metrics per template
5. Determine: CONVERGED | NOT_CONVERGED | CONVERGED_TIE

## Output Schema
{
  "iteration": N,
  "synthesis": {
    "overall_verdict": "pass|partial|fail",
    "confidence": 0.0-1.0,
    "summary": "2-3 sentences"
  },
  "aspect_summaries": [...],
  "all_issues": [...],
  "conflicts_resolved": [...],
  "convergence": {
    "type": "[type]",
    "status": "CONVERGED|NOT_CONVERGED",
    "metrics": {...},
    "blocking": ["threshold if not converged"]
  },
  "recommendations": [...]
}
```

## Phase 5: Convergence Check

Read validator's convergence status.

| Status | Action |
|--------|--------|
| CONVERGED | Output synthesis |
| CONVERGED_TIE | Output synthesis (note tie) |
| NOT_CONVERGED + iteration < 5 | Respawn workers focusing on blocking thresholds |
| iteration >= 5 | Stop, report incomplete |

If continuing, focus workers on aspects blocking convergence.

## Phase 6: Final Output

### Output Directory Routing

| Task Type | Directory | Filename Pattern |
|-----------|-----------|------------------|
| ANALYSIS | scratch/research/ | {topic}_analysis.md |
| REVIEW | scratch/reviews/ | {subject}_review.md |
| COMPARISON | scratch/research/ | {options}_comparison.md |
| CUSTOM | scratch/research/ | {topic}_findings.md |

Derive filename from task keywords (snake_case, max 40 chars).

### Write Output File

Use Write tool to create the output file with this structure:

```markdown
# Swarm [Type]: [Topic]

Task: [original]
Date: [timestamp]
Iterations: [N]
Workers: [count] | Gemini calls: [count] | Codex calls: [count]

## Verdict: [PASS/PARTIAL/FAIL]

Confidence: [X]%

## Summary

[2-3 paragraph synthesis]

## Per-Aspect Results

### [Aspect]: [VERDICT] ([confidence]%)

- [key finding]
- [key finding]

## Issues

### Critical

- [issue] -> [recommendation]

### High

- [issue] -> [recommendation]

## Recommendations

1. [action]
2. [action]

## Convergence

Type: [type]
Final metrics: [key metrics]

## Files Examined

- [file:line] - [relevance]
```

### Confirm to User

After writing the file, output brief confirmation:

```
Swarm complete: scratch/research/{filename}.md
Verdict: [PASS/PARTIAL/FAIL] | Confidence: [X]% | Iterations: [N]
```

## Constraints

- Max 5 iterations
- Min 2 iterations before convergence check
- Orchestrator does NOT analyze (delegate everything)
- Workers spawned IN PARALLEL (single message, multiple Task calls)
- Output to scratch/ files (see Phase 6 for directory routing)

## Error Handling

- No files found: Use task description as context
- Template not found: Fall back to custom.md
- Worker fails: Retry once, then escalate to Sonnet
- Max iterations without convergence: Report blocking thresholds, recommend manual review

Task: $ARGUMENTS
