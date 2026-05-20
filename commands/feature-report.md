---
description: Generate a QA validation report for a feature using goal-backward verification. Auto-fires when user invokes /feature-report, asks to "QA the feature", "validate feature acceptance", or "verify the feature works".
---

Generate a QA validation report for a feature using goal-backward verification.

## Arguments

- feature: (optional) Feature name. If not provided, use current active feature from features.json or ask.

## Steps

1. Identify the target feature folder in .giantmem/features/
2. Read `spec.md` -- extract acceptance criteria as "truths that must be true"
3. Read `facts.md` -- extract test commands, beta flags, config keys
4. For each acceptance criterion, verify 3 levels:

### Verification Levels

| Level | Question | How to check |
|-------|----------|-------------|
| **Exists** | Are the expected files, endpoints, models present? | Glob/Grep for expected paths, class names, route definitions |
| **Substantive** | Real implementation, not stubs? | Check for TODO, FIXME, placeholder, pass-only functions, empty returns, hardcoded responses |
| **Wired** | Connected to the system? | Imported somewhere, called by a route/service, rendered in a template, registered in config |

5. Run test commands from `facts.md`
6. Write the report to `.giantmem/features/{feature}/qa_report.md`
7. If issues found, update meta.json status
8. Display summary to user

## Report Format

```markdown
# QA Report: {feature name}

Generated: {timestamp}
Status: {APPROVED | ISSUES_FOUND}

## Verification

| # | Criterion | Exists | Substantive | Wired | Notes |
|---|-----------|--------|-------------|-------|-------|
| 1 | {from spec.md} | PASS/FAIL | PASS/FAIL | PASS/FAIL | {details} |
| 2 | {criterion} | PASS | PASS | FAIL | not imported by any route |

## Test Results

- Passing: {N}
- Failing: {N}
- Commands run:
  ```bash
  {test commands from facts.md}
  ```

## Manual Verification Needed

Items that cannot be verified by code inspection alone:

- {visual rendering, real-time behavior, external service integration, etc.}

## Code Review Summary

- Files reviewed: {list}
- Issues found: {count}
- Security concerns: {none | list}

## Sign-off

- [ ] All acceptance criteria pass all 3 levels
- [ ] All tests pass
- [ ] No security vulnerabilities
- [ ] Code follows project patterns
- [ ] Manual verification items documented
```

## Notes

- A criterion that passes Exists but fails Substantive is a stub -- flag it clearly
- A criterion that passes Substantive but fails Wired is dead code -- flag it clearly
- Swarm commands should always call this as part of validation
- For regular work, user explicitly invokes when ready for QA
