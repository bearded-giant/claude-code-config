# /swarm-exec Command Usage Guide

## What It Is

A hierarchical execution system that parallelizes code implementation across Haiku workers, with Opus validation and test verification. Makes actual code changes based on a plan.

**Key difference from /swarm**: This command WRITES code.

```
You invoke /swarm-exec with a plan
    |
    v
Opus Orchestrator
    |-- Creates git branch (safety)
    |-- Spawns Haiku workers IN PARALLEL
    |     Workers: Edit/Write code + consult Gemini
    |
    v
Opus Validator
    |-- Reviews changes
    |-- Runs tests
    |-- Identifies issues
    |
    v
Fix iteration if needed (max 5)
    |
    v
Output summary (YOU commit when ready)
```

## What It's For

- **Implementing features** from a clear plan
- **Refactoring** with defined steps
- **Bug fixes** across multiple files
- **Migrations** with known changes
- **Parallel implementation** of independent components

Good use cases:
```
/swarm-exec scratch/plans/add-preferences-api.md
/swarm-exec "add logout button to navbar, clear session, redirect to login"
/swarm-exec scratch/plans/refactor-auth-to-oauth2.md
```

## What It's NOT For

- **Exploratory work** - use /swarm to analyze first
- **Unclear requirements** - plan it first
- **Single-file changes** - just edit directly
- **Anything you haven't planned** - plan first, execute second

## Critical Safeguards

**Swarm-exec NEVER:**
- Commits code (you review and commit)
- Pushes to remote (you push when ready)
- Merges branches (you merge after validation)
- Modifies files outside the plan
- Deletes files unless explicitly planned

**Before changes:**
- Checks for uncommitted work (stops if dirty)
- Creates `swarm-exec/{timestamp}` branch
- All changes isolated to that branch

**You always have:**
```bash
# discard everything
git checkout main
git branch -D swarm-exec/{timestamp}

# review before deciding
git diff main..swarm-exec/{timestamp}
```

## Invocation

```
/swarm-exec <plan file or inline description>
```

### With Plan File (Recommended)

```
/swarm-exec scratch/plans/my-feature.md
```

Plan file should contain:
- What to implement
- Which files to create/modify
- Success criteria (tests, behavior)
- Any ordering dependencies

### Inline (Simple Cases)

```
/swarm-exec "add health check endpoint at /api/health returning {status: ok}"
```

## Plan Format

Good plans are specific:

```markdown
# Add User Preferences API

## Goal
Users can store and retrieve preference key-value pairs.

## Files to Create
- models/preferences.py - Preferences model with user_id, key, value
- services/preferences.py - PreferencesService with get, set, delete
- api/preferences.py - REST endpoints GET/POST/DELETE /api/preferences

## Files to Modify
- api/__init__.py - register preferences blueprint

## Tests
- tests/test_preferences.py - unit tests for service
- tests/test_preferences_api.py - integration tests for endpoints

## Dependencies
Model must exist before service. Service before API.

## Success Criteria
- All new tests pass
- Existing tests still pass
- Endpoints return correct responses
```

## Workflow

**Recommended full workflow:**

```
1. /swarm analyze src/related-area/    # understand current state
2. Draft plan based on analysis        # you write the plan
3. /swarm review plan.md               # validate plan
4. /swarm-exec plan.md                 # execute plan
5. Review changes: git diff            # you inspect
6. Run tests manually if desired       # you verify
7. Commit: git add -A && git commit    # you commit
```

## Tips

### 1. Plan First, Execute Second

```
# Bad - vague, will struggle
/swarm-exec "improve the auth system"

# Good - clear plan exists
/swarm-exec scratch/plans/auth-improvement.md
```

### 2. Be Specific About Files

```
# Good plan content
Files to create:
- src/services/billing.py
- src/api/billing.py

# Vague plan content (avoid)
"create billing stuff somewhere"
```

### 3. Include Test Expectations

```
# Good
Tests:
- test_billing_create_invoice passes
- test_billing_process_payment passes

# Missing (swarm won't know how to validate)
"make sure it works"
```

### 4. Check Branch After Execution

Before committing, always:
```bash
git diff main..swarm-exec/{timestamp}
git log --oneline main..swarm-exec/{timestamp}
```

### 5. Iterate If Needed

If first execution is close but not perfect:
- Stay on swarm branch
- Run /swarm-exec again with fixes
- Or manually fix small issues

## Convergence

Execution converges when ALL:
- Tests passing (0 failures)
- No lint/type errors
- No critical review issues
- All work units complete

If stuck after 5 iterations:
- Output shows blocking issues
- You can fix manually
- Or discard and re-plan

## Error Handling

**Tests fail:**
- Swarm spawns fix workers
- Targets specific failures
- Iterates until passing or max iterations

**Uncommitted changes detected:**
- Swarm STOPS before any changes
- You must commit or stash first

**Worker can't complete assignment:**
- Retries once
- Escalates to Sonnet if still failing
- Reports partial completion

**Max iterations without convergence:**
```
Execution incomplete after 5 iterations.

Blocking:
- test_payment_process: AssertionError
- lint: unused import in billing.py

Changes made (on branch swarm-exec/20250105-1423):
- Created src/services/billing.py
- Created src/api/billing.py
- Modified src/api/__init__.py

Your options:
- Fix remaining issues manually
- Discard: git checkout main && git branch -D swarm-exec/20250105-1423
```

## Related Commands

| Command | Purpose |
|---------|---------|
| /swarm | Analyze (read-only) |
| /swarm-exec | Execute (read-write) |
| /arch-discover | Map architecture |
| /arch-brainstorm | Plan approach |
| /scope | Create phased plan |

**Typical flow:**
```
/arch-discover       -> understand system
/arch-brainstorm     -> decide approach
write plan           -> document steps
/swarm review        -> validate plan
/swarm-exec          -> implement plan
you commit           -> finalize
```
