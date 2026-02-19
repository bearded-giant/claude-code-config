# /swarm Command Usage Guide

## What It Is

A hierarchical multi-model analysis system with configurable workers. Opus orchestrates, workers analyze in parallel (or sequentially for Codex), and Opus validates.

**Architecture:**
```
You invoke /swarm [flags] <task>
    |
    v
Opus Orchestrator (coordinator only - no analysis)
    |
    |-- Spawns 3-8 workers IN PARALLEL (haiku) or SEQUENTIAL (codex)
    |     Each worker: explores code + optional consultation
    |
    v
Opus Validator (synthesis)
    |     Resolves conflicts + optional consultation
    |
    v
Convergence check -> iterate if needed (max 5)
    |
    v
Output to swarm-{topic}/ directory (all artifacts retained)
```

## Model Configuration

| Role | Model | Configurable |
|------|-------|--------------|
| Orchestrator | Opus | No (always Opus) |
| Workers | Haiku or Codex | Yes (`--worker=`) |
| Validator | Opus | No (always Opus) |
| Consultation | Haiku or Codex | Yes (`--consult=`) |

### Worker Model Trade-offs

| Worker | Via | Cost | Speed | Parallel |
|--------|-----|------|-------|----------|
| haiku (default) | Task tool | Your $ | Fast | Yes (6 at once) |
| codex | PAL clink | Company $ | Slower | No (sequential) |

### Flags

```bash
--worker=MODEL    # haiku (default) or codex
--consult=MODEL   # haiku, codex, or none (default: none)
```

### Shorthand Syntax

```bash
codex           # --worker=codex
codex+haiku     # --worker=codex --consult=haiku
haiku+codex     # --worker=haiku --consult=codex
```

### Examples

```bash
# Default: haiku workers, no consultation (you pay, parallel)
/swarm analyze src/auth/

# Codex workers (company pays, sequential)
/swarm codex analyze src/auth/

# Haiku workers + codex consultation (parallel + deep validation)
/swarm haiku+codex analyze src/auth/

# Codex workers + haiku consultation (company pays, quick sanity checks)
/swarm codex+haiku analyze src/auth/
```

### Cost Optimization

| Your Goal | Config | Why |
|-----------|--------|-----|
| Fast + cheap | `haiku` (default) | Parallel, your cost |
| Thorough on your budget | `haiku+codex` | Parallel workers, spot consults to Codex |
| Company pays | `codex` | Sequential but shifts cost |
| Company pays + sanity checks | `codex+haiku` | Mostly company, cheap checks |

## What It's For

- **Architecture analysis** before refactoring
- **Code review** against specs or requirements
- **Option comparison** (tech choices, approaches)
- **Deep investigation** of complex systems
- **Multi-dimensional analysis** where parallel perspectives help

Good use cases:
```bash
/swarm analyze src/services/ for refactor risks
/swarm review design.md against PRD.md
/swarm compare RQ jobs vs Celery for our task queue
/swarm codex investigate the auth flow end-to-end
/swarm haiku+codex examine src/api/ for security issues
```

## What It's NOT For

- **Simple questions** - just ask directly
- **Single-file edits** - use normal editing
- **Quick lookups** - use Grep/Glob
- **Writing code** - swarm analyzes, doesn't implement
- **Time-sensitive tasks** - iterations take time

Don't use for:
```bash
# Too simple - just ask
/swarm what does this function do?

# Wrong tool - swarm doesn't write code
/swarm implement a new endpoint

# Overkill - just read the file
/swarm check if auth.py exists
```

## Invocation

```bash
/swarm [flags] <task description> [file/directory references]
```

### Task Types (auto-detected)

| Keywords | Template | Convergence |
|----------|----------|-------------|
| analyze, examine, investigate, explore, architecture | analysis.md | SCORE_STABILITY |
| review, evaluate, assess, check, audit | review.md | ISSUE_SATURATION |
| compare, contrast, vs, versus, between | comparison.md | WINNER_STABILITY |
| (other) | custom.md | PATTERN_ADAPTIVE |

### Full Examples

**Analysis (architecture/refactor prep):**
```bash
/swarm analyze the payment processing in src/payments/
/swarm codex examine src/models/ for coupling issues
/swarm haiku+codex investigate how caching works across the app
```

**Review (validation against requirements):**
```bash
/swarm review src/api/v2/ against openapi.yaml
/swarm codex evaluate the migration script for edge cases
/swarm audit src/auth/ for security issues
```

**Comparison (decision support):**
```bash
/swarm compare PostgreSQL vs MongoDB for our use case
/swarm codex+haiku contrast the old auth flow vs proposed new flow
```

## Output & Artifacts

### Directory Structure

All swarm outputs go to a dedicated directory:

```
.giantmem/research/swarm-{topic}/
├── README.md                    # manifest + config summary
├── analysis.md                  # human-readable final report
├── validator-synthesis.json     # aggregated findings
├── worker-technical.json        # worker output
├── worker-dependencies.json     # worker output
├── worker-dataflow.json         # worker output
├── worker-risks.json            # worker output
├── worker-performance.json      # worker output
└── worker-maintainability.json  # worker output
```

If a feature is detected, outputs go to `.giantmem/features/{name}/swarm-{topic}/`.

### Why Artifacts Are Retained

- **Audit trail**: See exactly what each worker found
- **Debug convergence**: Understand why scores changed between iterations
- **Reuse findings**: Reference specific worker insights later
- **Cost transparency**: See which workers consulted external models

## Tips

### 1. Be Specific About Scope

```bash
# Good - clear scope
/swarm analyze src/services/billing/ for refactor risks

# Vague - workers might scatter
/swarm analyze the codebase
```

### 2. Reference Files Explicitly

```bash
# Good - workers know where to look
/swarm review src/api/routes.py against docs/api-spec.md

# Less effective - workers must search
/swarm review the API against the spec
```

### 3. State Your Goal

```bash
# Good - workers focus on what matters
/swarm analyze src/auth/ to prepare for OAuth2 migration

# Generic - analysis might miss your intent
/swarm analyze src/auth/
```

### 4. Choose Model Based on Cost/Speed

```bash
# Quick scan, you pay
/swarm analyze src/utils/

# Deep analysis, company pays (accepts sequential)
/swarm codex analyze src/auth/

# Best of both: parallel speed + deep consults
/swarm haiku+codex analyze src/payments/
```

### 5. Expect Iteration

First iteration establishes baseline. Real insights often come in iterations 2-3. Don't be surprised by 3-5 iteration runs for complex tasks.

## What Happens Under the Hood

1. **Orchestrator** (Opus) parses flags, detects task type, loads template
2. **Workers** (Haiku via Task OR Codex via clink) analyze aspects
   - Haiku: parallel spawning via Task tool
   - Codex: sequential via PAL clink
   - Optional consultation to secondary model
3. **Validator** (Opus) synthesizes all worker reports
   - Resolves conflicts between workers
   - Optional consultation for validation
   - Calculates convergence metrics
4. If not converged: workers re-spawn focusing on gaps
5. All artifacts written to `swarm-{topic}/` directory

## Limits

- **Max 5 iterations** (cost control)
- **Min 2 iterations** before convergence check
- **3-8 workers** per iteration
- **All artifacts retained** in swarm directory

## Troubleshooting

**Workers not finding files:**
- Use explicit paths: `src/auth/` not "the auth code"
- Check paths exist before invoking

**Convergence stuck:**
- Check which threshold is blocking in output
- Consider if task is too broad
- Some tasks genuinely don't converge - that's useful info

**Taking too long:**
- Use `haiku` workers (parallel) instead of `codex` (sequential)
- Narrow the scope

**Codex/consultation errors:**
- Swarm continues without enhancement
- Check PAL MCP is configured correctly

## Related Commands

| Command | Purpose |
|---------|---------|
| /swarm-exec | Execute plans (read-write counterpart) |
| /arch-discover | Systematic architecture mapping |
| /arch-brainstorm | Two-phase architecture decisions |
| /scope | Phased scope documents for migrations |

**Typical workflow:**
```bash
/arch-discover       -> map the territory
/swarm analyze       -> deep dive on specific areas
write plan           -> based on findings
/swarm review        -> validate plan
/swarm-exec          -> implement (separate command)
```

Swarm analyzes. Swarm-exec implements.
