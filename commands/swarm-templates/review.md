# Review Template

Task type: REVIEW
Keywords: review, evaluate, assess, check, audit, validate, verify

## Convergence

Type: ISSUE_SATURATION
Min iterations: 2
Max iterations: 5

Thresholds:
- saturation_ratio >= 0.85
- new_issues_found <= 1

Metrics tracked:
- new_issues_found: issues discovered this iteration not in previous
- confirmed_issues: issues from previous iteration still valid
- total_unique_issues: cumulative unique issues across all iterations
- saturation_ratio: confirmed / (new + confirmed)

Issue hashing: severity + first 50 chars of description (for deduplication)

## Aspects

Workers analyze these dimensions (adjust based on task):

### requirements
Focus: coverage of stated requirements, missing features
Questions:
- Does implementation meet each requirement?
- What requirements are missing or incomplete?
- Are there requirements that are partially met?
- Any scope creep beyond requirements?

### technical_accuracy
Focus: correctness of implementation, logic errors
Questions:
- Is the logic correct?
- Are edge cases handled?
- Are error conditions managed?
- Does it do what it claims?

### security
Focus: vulnerabilities, auth/authz, data protection
Questions:
- Are there OWASP top 10 vulnerabilities?
- Is authentication/authorization sound?
- Is sensitive data protected?
- Are inputs validated?

### consistency
Focus: adherence to patterns, style, conventions
Questions:
- Does it follow project conventions?
- Are naming patterns consistent?
- Does structure match similar code?
- Any deviation from established patterns?

### completeness
Focus: documentation, tests, edge cases
Questions:
- Is there adequate test coverage?
- Are edge cases tested?
- Is documentation sufficient?
- Are all code paths exercised?

### best_practices
Focus: industry standards, modern patterns
Questions:
- Does it follow language idioms?
- Are there anti-patterns?
- Is it production-ready?
- Would it pass code review?

## Worker Output Schema

```json
{
  "aspect": "requirements|technical_accuracy|security|consistency|completeness|best_practices",
  "verdict": "pass|partial|fail",
  "confidence": 0.0-1.0,
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "description": "issue description (first 50 chars used for dedup)",
      "location": "file:line or general area",
      "recommendation": "suggested fix",
      "issue_hash": "auto-generated for tracking"
    }
  ],
  "passed_checks": ["check1", "check2"],
  "codex_consulted": true|false,
  "codex_insight": "if consulted, key insight"
}
```

## Validator Synthesis

Combine worker findings into:
- Overall verdict: PASS / PARTIAL / FAIL
- Critical blockers (must fix)
- High priority issues (should fix)
- Medium/low issues (nice to fix)
- Passed areas (what's working well)
- Specific recommendations
