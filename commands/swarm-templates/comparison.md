# Comparison Template

Task type: COMPARISON
Keywords: compare, contrast, versus, vs, difference, between, tradeoff

## Convergence

Type: WINNER_STABILITY
Min iterations: 2
Max iterations: 5

Thresholds:
- winner_changes == 0
- winner_margin >= 2 (clear lead)

Metrics tracked:
- winner_changes: dimensions that changed winner from previous iteration
- winner_margin: difference between option wins (e.g., A wins 4 dimensions, B wins 2 = margin 2)
- avg_score_gap: average point difference between options
- clear_winner: option_a | option_b | tie | none

Special case: CONVERGED_TIE when all dimensions are tied after min iterations

## Aspects

Workers analyze these dimensions (adjust based on options being compared):

### features
Focus: functionality, capabilities, feature completeness
Questions:
- Which option has more features?
- Which features are unique to each?
- Which has better feature quality?
- Missing features in each?

### complexity
Focus: implementation effort, learning curve, maintenance burden
Questions:
- Which is simpler to implement?
- Which has lower learning curve?
- Which is easier to maintain?
- Which has less operational overhead?

### performance
Focus: speed, resource usage, scalability
Questions:
- Which is faster?
- Which uses fewer resources?
- Which scales better?
- Any performance gotchas?

### integration
Focus: compatibility, ecosystem, existing codebase fit
Questions:
- Which fits current stack better?
- Which has better ecosystem/community?
- Which integrates more easily?
- Breaking changes required?

### risk
Focus: maturity, stability, long-term viability
Questions:
- Which is more battle-tested?
- Which has better long-term support?
- Which has fewer unknowns?
- Migration path if wrong choice?

### cost
Focus: licensing, infrastructure, development time
Questions:
- Licensing costs?
- Infrastructure requirements?
- Development time difference?
- Total cost of ownership?

## Worker Output Schema

```json
{
  "aspect": "features|complexity|performance|integration|risk|cost",
  "winner": "option_a|option_b|tie",
  "confidence": 0.0-1.0,
  "scores": {
    "option_a": 1-10,
    "option_b": 1-10
  },
  "score_gap": 0.0-10.0,
  "rationale": "why this option wins/ties",
  "option_a_pros": ["pro1", "pro2"],
  "option_a_cons": ["con1", "con2"],
  "option_b_pros": ["pro1", "pro2"],
  "option_b_cons": ["con1", "con2"],
  "codex_consulted": true|false,
  "codex_insight": "if consulted, key insight"
}
```

## Validator Synthesis

Combine worker findings into:
- Overall recommendation: Option A / Option B / Tie (with caveats)
- Winner by dimension table
- Key differentiators
- When to choose A vs B
- Risk assessment of recommendation
