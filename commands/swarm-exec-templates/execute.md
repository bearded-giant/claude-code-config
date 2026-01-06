# Execution Template

Task type: EXECUTE
Used by: /swarm-exec

## Convergence

Type: EXECUTION_COMPLETE
Min iterations: 1
Max iterations: 5

Thresholds (ALL must be met):
- tests_failing == 0
- lint_errors == 0
- critical_review_issues == 0
- work_units_remaining == 0

Metrics tracked:
- tests_passing: tests that pass
- tests_failing: tests that fail (must be 0 to converge)
- lint_errors: linting/type errors (must be 0 to converge)
- review_issues: {critical, high, medium, low} counts
- work_units_complete: plan items fully implemented
- work_units_remaining: plan items still needing work

## Work Unit Decomposition

Plans are broken into work units based on:

1. **File boundaries** - one file = one unit (usually)
2. **Logical cohesion** - related changes grouped
3. **Dependencies** - units ordered by what depends on what

Example:
```
Plan: Add user preferences feature

Work Units:
  Group 1 (parallel):
    - unit-1: models/preferences.py (new model)
  Group 2 (after group 1):
    - unit-2: services/preferences.py (new service, needs model)
  Group 3 (after group 2):
    - unit-3: api/preferences.py (new endpoints, needs service)
    - unit-4: tests/test_preferences.py (tests, can parallel with api)
```

## Worker Behavior

Workers should:
- Read existing code first (understand patterns)
- Make minimal changes (no scope creep)
- Follow existing conventions
- Use Gemini for complex decisions
- Report clearly what changed

Workers must NOT:
- Change files outside their assignment
- Add features not in the plan
- Refactor unrelated code
- Commit or push anything

## Validator Behavior

Validator should:
- Review all changes for correctness
- Run test suite
- Check for integration issues
- Use Codex for complex reviews
- Identify specific fixes needed

Validator must NOT:
- Make changes directly
- Approve incomplete work
- Skip test runs
- Commit or push anything

## Fix Iteration

When NOT_CONVERGED:

1. Identify blocking issues from validator
2. Spawn targeted fix workers (one per issue)
3. Fix workers make minimal changes
4. Re-validate

Fix workers get specific, scoped assignments:
```
Fix: Test test_create_preference failing
File: services/preferences.py
Error: AttributeError: 'Preferences' has no attribute 'user_id'
Likely cause: Model field name mismatch
Action: Check model definition, fix reference
```

## Output Expectations

Successful execution provides:
- List of all files created/modified
- Summary of what each change does
- Test results (all passing)
- Clear rollback instructions
- NO commits made
