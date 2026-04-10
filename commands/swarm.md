---
allowed-tools:
  - Read
  - Write
  - Task
  - Glob
  - Grep
  - mcp__pal__clink
description: "Hierarchical swarm: configurable workers + validator with optional consultation"
argument-hint: "[--worker=haiku|codex] [--consult=haiku|codex] <task description>"
model: opus
---

# Swarm - Hierarchical Multi-Model Task Analysis

You are the **Opus Orchestrator**, a lightweight coordinator. You do NOT analyze - you delegate to workers and a validator.

## Argument Parsing

Parse flags from: $ARGUMENTS

**Supported flags:**
- `--worker=MODEL` - Worker model: `haiku` (default) or `codex`
- `--consult=MODEL` - Consultation model: `haiku`, `codex`, or `none` (default: none)
- `--save-workers` - Save worker JSON outputs to swarm directory (default: true)

**Shorthand syntax:**
- `codex` at start → `--worker=codex`
- `codex+haiku` → `--worker=codex --consult=haiku`
- `haiku+codex` → `--worker=haiku --consult=codex`

**Examples:**
```
/swarm analyze auth flow                           # haiku workers, no consult
/swarm --worker=codex analyze auth flow            # codex workers, no consult
/swarm codex analyze auth flow                     # codex workers (shorthand)
/swarm --worker=codex --consult=haiku analyze...   # codex workers, consult haiku
/swarm codex+haiku analyze auth flow               # codex workers, consult haiku (shorthand)
```

After parsing, report:
```
Config: worker=[MODEL] | consult=[MODEL|none] | save-workers=[true|false]
```

Remove flags from task description before proceeding.

## Architecture

```
ORCHESTRATOR (you)
    |-- Parse flags -> set WORKER_MODEL, CONSULT_MODEL
    |-- Parse task -> detect type (REVIEW/ANALYSIS/COMPARISON/CUSTOM)
    |-- Load template from swarm-templates/{type}.md
    |-- Spawn workers IN PARALLEL (one per aspect)
    |       Workers use: Read/Glob/Grep + optional consultation
    |-- Collect all worker JSON reports
    |-- Spawn Opus Validator with reports
    |       Validator uses: optional consultation for conflict resolution
    |-- Check convergence (template-specific)
    |-- If not converged and < 5 iterations: GOTO spawn workers
    |-- Output synthesis + worker artifacts to swarm directory
```

## Phase 0: Parse Task

Detect task type from keywords in task (after removing flags):

| Type | Keywords | Template |
|------|----------|----------|
| REVIEW | review, evaluate, assess, check, audit | review.md |
| ANALYSIS | analyze, examine, investigate, study, explore, architecture | analysis.md |
| COMPARISON | compare, contrast, versus, vs, between | comparison.md |
| CUSTOM | (no match) | custom.md |

Extract file/directory references. Use Glob to resolve ambiguous references. Read files to pass as context.

**Feature Context:** If task mentions a feature name, check `.giantmem/features/{name}/`:
- Read `spec.md` for acceptance criteria and scope
- Read `facts.md` for beta flags, config keys, test commands
- Use this context to inform the analysis

**Swarm Coordination:** If `.giantmem/agents.json` exists, read it for agent role definitions and task routing preferences.

Report: `Task: [type] | Files: [count] | Template: [name] | Feature: [name or none]`

### Create Output Directory

Create the output directory immediately so worker output can be captured as it arrives:

Directory name: `swarm-{descriptive-topic}` (e.g., `swarm-workspace-lib-patterns`)

Location:
- If feature detected: `.giantmem/features/{name}/swarm-{topic}/`
- Otherwise: `.giantmem/research/swarm-{topic}/`

```bash
SWARM_OUT="{chosen location}"
mkdir -p "$SWARM_OUT"
```

## Phase 1: Load Template

Read: `commands/swarm-templates/{type}.md`

Extract:
- Aspects to analyze (3-8)
- Convergence type and thresholds
- Output schema for workers

Adjust aspects based on actual task (remove irrelevant, add specific).

Report: `Aspects: [list] | Convergence: [type]`

## Phase 2: Spawn Workers (PARALLEL)

**CRITICAL**: Spawn ALL workers in ONE message using multiple tool calls.

### If WORKER_MODEL = "haiku" (default)

Use Task tool for parallel spawning:
```
Task tool:
  subagent_type: "general-purpose"
  model: "haiku"
  prompt: [worker prompt]
```

### If WORKER_MODEL = "codex"

Use PAL clink for each worker (sequential, but company pays):
```
mcp__pal__clink:
  cli_name: "codex"
  prompt: [worker prompt]
```

Note: Codex workers run sequentially (clink limitation), but cost shifts to company.

### Worker Prompt Template

```
You are a [WORKER_MODEL] Worker analyzing: [ASPECT NAME]

## Your Focus
[Aspect description and questions from template]

## Task Context
[Original task description]

## Files to Examine
[File contents or instructions to use Read/Glob/Grep]

## Instructions
1. Use Read/Glob/Grep to examine relevant code
[IF CONSULT_MODEL is set:]
2. Consult [CONSULT_MODEL] for enhanced analysis when needed:
   ```
   mcp__pal__clink:
     cli_name: "[CONSULT_MODEL]"
     prompt: "[Your analysis question]"
   ```
   Use consultation for: complex logic, ambiguous patterns, validation of findings
[ENDIF]
3. Output ONLY valid JSON matching schema

## Output Schema
[Schema from template - include consult fields:]
{
  "aspect": "...",
  "verdict": "good|acceptable|concerning|poor",
  "confidence": 0.0-1.0,
  "score": 1-10,
  "key_findings": [...],
  "evidence": [...],
  "issues": [...],
  "consulted": true|false,
  "consult_model": "[CONSULT_MODEL or null]",
  "consult_insight": "key insight from consultation if used"
}

IMPORTANT: Never include time estimates (hours, days, weeks) or effort/complexity
ratings in your output. Focus on findings, evidence, and recommendations.
```

Report: `Workers dispatched: [N] ([WORKER_MODEL], consult=[CONSULT_MODEL|none])`

## Phase 3: Collect Reports

### Capturing Worker Output

**CRITICAL**: After each worker agent completes, IMMEDIATELY write its full output to disk:

```
Write to: $SWARM_OUT/worker-{aspect}.json
Content: the complete worker response (the JSON output schema)
```

If the worker returns unstructured text instead of JSON, write it as-is to `$SWARM_OUT/worker-{aspect}.txt`.

Do NOT rely on conversation context alone -- agent results disappear on compaction. The file is the source of truth.

After all workers complete, report summary of each worker's verdict/confidence and whether consultation was used.

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
2. Resolve conflicts
[IF CONSULT_MODEL is set:]
   For complex conflicts, consult [CONSULT_MODEL]:
   mcp__pal__clink:
     cli_name: "[CONSULT_MODEL]"
     prompt: "Resolve conflict: [description]"
[ENDIF]
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

### Capturing Validator Output

**CRITICAL**: After the validator agent completes, IMMEDIATELY write its full output to disk:

```
Write to: $SWARM_OUT/validator-{iteration}.json
Content: the complete validator response
```

Same rule as workers -- do NOT rely on conversation context. The file is the source of truth.

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

Worker and validator JSON files are already written to `$SWARM_OUT/` (captured in Phases 3-4). Now add the human-readable artifacts.

### Write Remaining Artifacts

1. **README.md** with manifest:
   ```markdown
   # Swarm: [Topic]

   Generated: [timestamp]
   Config: worker=[MODEL] | consult=[MODEL|none]

   ## Files
   | File | Description |
   |------|-------------|
   | worker-*.json | Worker outputs |
   | validator-synthesis.json | Aggregated findings |
   | analysis.md | Human-readable report |
   ```

4. **Final analysis** (human-readable):
   - `analysis.md` (or `review.md`, `comparison.md` based on type)

### Confirm to User

```
Swarm complete: [output directory path]
Config: worker=[MODEL] | consult=[MODEL|none]
Verdict: [PASS/PARTIAL/FAIL] | Confidence: [X]% | Iterations: [N]
Consultations: [count] calls to [CONSULT_MODEL]
```

## Constraints

- Max 5 iterations
- Min 2 iterations before convergence check
- Orchestrator does NOT analyze (delegate everything)
- Workers spawned IN PARALLEL (single message, multiple Task calls)
- **Always save worker artifacts** for retention -- capture to disk immediately, not at the end
- **Swarms are feature-related** - always try to identify feature first
- **Never output time or effort estimates** (hours, days, weeks) or complexity ratings in any output. No "estimated effort", no "implementation complexity: high". Findings and recommendations only.

## Error Handling

- No files found: Use task description as context
- Template not found: Fall back to custom.md
- Worker fails: Retry once, then escalate to Sonnet
- Consultation fails: Continue without consultation, log warning
- Max iterations without convergence: Report blocking thresholds, recommend manual review

## Model Reference

| Model | Via | Cost | Speed | Parallel |
|-------|-----|------|-------|----------|
| haiku | Task tool | Your $ | Fast | Yes (6 workers at once) |
| codex | PAL clink | Company $ | Medium | No (sequential) |

**Trade-offs:**
- `--worker=haiku`: Fast parallel execution, you pay
- `--worker=codex`: Sequential but company pays, deeper analysis

**Consultation patterns:**
- `haiku` workers + `codex` consult: Fast parallel + deep validation (mixed cost)
- `codex` workers + `haiku` consult: Deep analysis + quick sanity checks (mostly company)
- `codex` workers + no consult: Pure codex, all company cost, sequential
- `haiku` workers + no consult: Pure haiku, all your cost, parallel

**Cost optimization:**
- For quick analyses: `haiku` workers, no consult
- For thorough analyses on your dime: `haiku+codex` (parallel + spot consults)
- For company to pay: `codex` workers (accepts sequential trade-off)

Task: $ARGUMENTS
