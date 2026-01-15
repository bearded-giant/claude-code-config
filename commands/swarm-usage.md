# /swarm Command Usage Guide

## What It Is

A hierarchical multi-model analysis system that parallelizes task work across Haiku workers, enhanced with Codex via PAL MCP. Uses iterative convergence to ensure thorough analysis.

**Architecture:**
```
You invoke /swarm
    |
    v
Opus Orchestrator (coordinator only - no analysis)
    |
    |-- Spawns 3-8 Haiku workers IN PARALLEL
    |     Each worker: explores code + consults Codex
    |
    v
Opus Validator (synthesis)
    |     Resolves conflicts + consults Codex
    |
    v
Convergence check -> iterate if needed (max 5)
    |
    v
Output to conversation
```

## What It's For

- **Architecture analysis** before refactoring
- **Code review** against specs or requirements
- **Option comparison** (tech choices, approaches)
- **Deep investigation** of complex systems
- **Multi-dimensional analysis** where parallel perspectives help

Good use cases:
```
/swarm analyze src/services/ for refactor risks
/swarm review design.md against PRD.md
/swarm compare RQ jobs vs Celery for our task queue
/swarm investigate the auth flow end-to-end
/swarm examine src/api/ for security issues
```

## What It's NOT For

- **Simple questions** - just ask directly
- **Single-file edits** - use normal editing
- **Quick lookups** - use Grep/Glob
- **Writing code** - swarm analyzes, doesn't implement
- **Time-sensitive tasks** - iterations take time
- **Tasks needing human judgment** - swarm provides analysis, you decide

Don't use for:
```
# Too simple - just ask
/swarm what does this function do?

# Wrong tool - swarm doesn't write code
/swarm implement a new endpoint

# Overkill - just read the file
/swarm check if auth.py exists
```

## Invocation

```
/swarm <task description> [file/directory references]
```

### Task Types (auto-detected)

| Keywords | Template | Convergence |
|----------|----------|-------------|
| analyze, examine, investigate, explore, architecture | analysis.md | SCORE_STABILITY |
| review, evaluate, assess, check, audit | review.md | ISSUE_SATURATION |
| compare, contrast, vs, versus, between | comparison.md | WINNER_STABILITY |
| (other) | custom.md | PATTERN_ADAPTIVE |

### Examples

**Analysis (architecture/refactor prep):**
```
/swarm analyze the payment processing in src/payments/
/swarm examine src/models/ for coupling issues
/swarm investigate how caching works across the app
```

**Review (validation against requirements):**
```
/swarm review src/api/v2/ against openapi.yaml
/swarm evaluate the migration script for edge cases
/swarm audit src/auth/ for security issues
```

**Comparison (decision support):**
```
/swarm compare PostgreSQL vs MongoDB for our use case
/swarm contrast the old auth flow vs proposed new flow
/swarm evaluate Redis vs Memcached for session storage
```

**Custom (everything else):**
```
/swarm trace request flow from API to database
/swarm map all entry points in the application
/swarm verify the accuracy of docs/architecture.md
```

**Detailed research prompts:**
```
/swarm investigate how an attacker could intercept signup requests at admin/login and manipulate POST /co/authenticate to POST /dbconnections/signup to create unauthorized OAuth accounts. Examine auth flow, request handling, and validation. Include file:line references for any vulnerable code paths.
```

Full prompts with context work - swarm parses keywords and delegates to workers.

## Tips

### 1. Be Specific About Scope

```
# Good - clear scope
/swarm analyze src/services/billing/ for refactor risks

# Vague - workers might scatter
/swarm analyze the codebase
```

### 2. Reference Files Explicitly

```
# Good - workers know where to look
/swarm review src/api/routes.py against docs/api-spec.md

# Less effective - workers must search
/swarm review the API against the spec
```

### 3. State Your Goal

```
# Good - workers focus on what matters
/swarm analyze src/auth/ to prepare for OAuth2 migration

# Generic - analysis might miss your intent
/swarm analyze src/auth/
```

### 4. Use for Parallel Perspectives

Swarm shines when you need multiple viewpoints:
- Technical + business + risk perspectives
- Different aspects examined simultaneously
- Cross-cutting concerns (security, performance, maintainability)

### 5. Expect Iteration

The first iteration establishes baseline. Real insights often come in iterations 2-3 as workers build on each other's findings. Don't be surprised by 3-5 iteration runs for complex tasks.

### 6. Check Convergence Type

Different tasks converge differently:
- **ISSUE_SATURATION**: Stops when workers stop finding new issues
- **SCORE_STABILITY**: Stops when dimension scores stabilize
- **WINNER_STABILITY**: Stops when option rankings stabilize

If convergence seems stuck, the output will tell you which threshold is blocking.

## What Happens Under the Hood

1. **Orchestrator** (Opus) parses your task, detects type, loads template
2. **Workers** (Haiku x 3-8) spawn in parallel, each analyzing one aspect
   - Workers can Read/Glob/Grep code
   - Workers consult Codex via PAL clink for enhanced reasoning
3. **Validator** (Opus) synthesizes all worker reports
   - Resolves conflicts between workers
   - Consults Codex via PAL clink for validation
   - Calculates convergence metrics
4. If not converged: workers re-spawn focusing on gaps
5. Final synthesis written to scratch/ file (routed by task type)

## Output Routing

| Task Type | Directory |
|-----------|-----------|
| ANALYSIS | scratch/research/{topic}_analysis.md |
| REVIEW | scratch/reviews/{subject}_review.md |
| COMPARISON | scratch/research/{options}_comparison.md |
| CUSTOM | scratch/research/{topic}_findings.md |

## Limits

- **Max 5 iterations** (cost control)
- **Min 2 iterations** before convergence check
- **3-8 workers** per iteration
- **Output to scratch/ files** (routed by task type)

## Troubleshooting

**Workers not finding files:**
- Use explicit paths: `src/auth/` not "the auth code"
- Check paths exist before invoking

**Convergence stuck:**
- Check which threshold is blocking in output
- Consider if task is too broad
- Some tasks genuinely don't converge - that's useful info

**Taking too long:**
- Narrow the scope
- Use fewer aspects (orchestrator adjusts based on task)

**PAL/Codex errors:**
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
```
/arch-discover       -> map the territory
/swarm analyze       -> deep dive on specific areas
write plan           -> based on findings
/swarm review        -> validate plan
/swarm-exec          -> implement (separate command)
```

Swarm analyzes. Swarm-exec implements.
