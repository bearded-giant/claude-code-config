Generate a QA validation report for a feature.

## Arguments

- feature: (optional) Feature name. If not provided, use current active feature from plans/current.md context or ask.

## Steps

1. Identify the target feature folder in .giantmem/features/
2. Read the feature's spec.md to get acceptance criteria
3. Read the feature's facts.md to get test commands
4. Generate qa_report.md with:

````markdown
# QA Report: {feature name}

Generated: {timestamp}
Status: {PENDING | APPROVED | ISSUES_FOUND}

## Acceptance Criteria Verification

| Criterion      | Status | Notes |
| -------------- | ------ | ----- |
| {from spec.md} |        |       |

## Test Results

```bash
# Commands from facts.md
{test command 1}
# Result: PASS/FAIL
```
````

## Code Review Summary

- Files reviewed: {list}
- Issues found: {count}
- Security concerns: {none | list}

## Sign-off

- [ ] All acceptance criteria met
- [ ] All tests pass
- [ ] No security vulnerabilities
- [ ] Code follows project patterns

---

```

5. Write to .giantmem/features/{feature}/qa_report.md
6. If issues found, update meta.json status
7. Display summary to user

## Notes

- Swarm commands should always call this as part of validation
- For regular work, user explicitly invokes when ready for QA
```
