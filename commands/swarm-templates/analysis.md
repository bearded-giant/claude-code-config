# Analysis Template

Task type: ANALYSIS
Keywords: analyze, examine, investigate, study, explore, deep dive, architecture, refactor

## Convergence

Type: SCORE_STABILITY
Min iterations: 2
Max iterations: 5

Thresholds:
- stability_score >= 0.85
- verdict_changes == 0
- avg_score_delta < 0.5

Metrics tracked:
- avg_score_delta: average change in dimension scores from previous iteration
- verdict_changes: count of dimensions that changed verdict
- low_confidence_count: dimensions with confidence < 0.6
- stability_score: weighted composite (see formula)

Formula: stability_score = ((1 - avg_delta/10) * 0.4) + ((1 - changes/total) * 0.4) + (avg_confidence * 0.2)

## Aspects

Workers analyze these dimensions (adjust based on task):

### technical
Focus: code structure, design patterns, anti-patterns, complexity
Questions:
- What patterns are used consistently?
- Where does code deviate from patterns?
- What's the cyclomatic complexity?
- Are there code smells?

### dependencies
Focus: external libraries, internal coupling, import graphs
Questions:
- What external dependencies exist?
- How tightly coupled are components?
- Are there circular dependencies?
- What would break if X changed?

### dataflow
Focus: how data moves, transformations, state management
Questions:
- How does data enter the system?
- What transformations occur?
- Where is state stored/mutated?
- Are there race conditions or data inconsistencies?

### risks
Focus: refactor hazards, hidden state, test coverage gaps
Questions:
- What implicit dependencies exist?
- Where is test coverage weak?
- What edge cases aren't handled?
- What could break silently?

### performance
Focus: bottlenecks, resource usage, scalability
Questions:
- Where are the hot paths?
- What scales poorly?
- Are there N+1 queries or similar issues?
- Memory/CPU concerns?

### maintainability
Focus: documentation, naming, cognitive load
Questions:
- Is code self-documenting?
- How easy is onboarding?
- Where is tribal knowledge required?
- What's the bus factor?

## Worker Output Schema

```json
{
  "aspect": "technical|dependencies|dataflow|risks|performance|maintainability",
  "verdict": "good|acceptable|concerning|poor",
  "confidence": 0.0-1.0,
  "score": 1-10,
  "key_findings": ["finding1", "finding2"],
  "evidence": [
    {"file": "path/to/file.py", "line": 42, "observation": "description"}
  ],
  "issues": [
    {"severity": "critical|high|medium|low", "description": "issue", "recommendation": "fix"}
  ],
  "gemini_consulted": true|false,
  "gemini_insight": "if consulted, key insight"
}
```

## Validator Synthesis

Combine worker findings into:
- Overall health score (1-10)
- Per-dimension summaries
- Prioritized issue list
- Refactor recommendations
