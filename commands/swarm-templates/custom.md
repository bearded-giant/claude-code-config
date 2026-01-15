# Custom Template

Task type: CUSTOM
Keywords: (fallback when no other template matches)
Also used for: explain, verify, document, map, trace, audit (specific)

## Convergence

Type: PATTERN_ADAPTIVE
Min iterations: 2
Max iterations: 5

Pattern detection based on task keywords:
- ACCURACY: verify, validate, check accuracy, confirm
- COMPLETENESS: complete, comprehensive, full, all
- ROOTCAUSE: debug, why, cause, investigate, trace
- CONFIDENCE: explain, understand, clarify

### ACCURACY Pattern
Thresholds:
- overall_accuracy >= 0.90
- new_inaccuracies == 0

Metrics:
- claims_verified: count of verified claims
- claims_false: count of false claims
- overall_accuracy: verified / total

### COMPLETENESS Pattern
Thresholds:
- coverage >= 0.90
- gaps_found <= 1

Metrics:
- items_covered: count of covered items
- items_missing: count of missing items
- coverage: covered / expected

### ROOTCAUSE Pattern
Thresholds:
- hypothesis_confidence >= 0.85
- contradicting_evidence == 0

Metrics:
- hypotheses_tested: count of hypotheses
- hypotheses_eliminated: count ruled out
- hypothesis_confidence: confidence in remaining hypothesis

### CONFIDENCE Pattern
Thresholds:
- explanation_confidence >= 0.85
- ambiguities_remaining == 0

Metrics:
- concepts_explained: count of explained concepts
- ambiguities_found: count of unclear areas
- explanation_confidence: overall understanding confidence

## Aspects

For CUSTOM tasks, the orchestrator generates 3-8 aspects based on:
1. Task keywords and intent
2. Files/context provided
3. Domain of the task

Example aspect generation:
- "Explain how auth flow works" -> [entry_points, token_handling, session_management, error_cases]
- "Verify API documentation accuracy" -> [endpoints, parameters, responses, examples]
- "Trace data from input to database" -> [input_validation, transformations, persistence, error_handling]

## Worker Output Schema

```json
{
  "aspect": "dynamically assigned",
  "pattern": "ACCURACY|COMPLETENESS|ROOTCAUSE|CONFIDENCE",
  "verdict": "task-specific verdict",
  "confidence": 0.0-1.0,
  "findings": ["finding1", "finding2"],
  "evidence": [
    {"source": "file or observation", "detail": "supporting evidence"}
  ],
  "issues": [
    {"severity": "critical|high|medium|low", "description": "issue", "recommendation": "fix"}
  ],
  "pattern_metrics": {
    "ACCURACY": {"verified": 0, "false": 0},
    "COMPLETENESS": {"covered": 0, "missing": 0},
    "ROOTCAUSE": {"hypothesis": "string", "confidence": 0.0, "eliminated": []},
    "CONFIDENCE": {"explained": 0, "ambiguous": 0}
  },
  "codex_consulted": true|false,
  "codex_insight": "if consulted, key insight"
}
```

## Validator Synthesis

Combine worker findings into:
- Pattern-specific summary
- Consolidated findings
- Confidence assessment
- Remaining gaps or unknowns
- Recommendations for follow-up
