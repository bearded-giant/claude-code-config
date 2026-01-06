# MCP Server Evaluation Guide

## Purpose

Evaluate MCP servers by testing whether LLMs can effectively answer realistic, complex questions using only provided tools.

## Evaluation Requirements

Create 10 questions that are:

| Requirement | Description |
|-------------|-------------|
| **Read-only** | No state modifications |
| **Independent** | Each question stands alone |
| **Complex** | Require multiple tool calls |
| **Stable** | Answers don't change over time |
| **Realistic** | Reflect genuine user needs |

## Question Quality

**Good questions:**
- Multi-hop requiring synthesis across data sources
- Require exploration and inference
- Test real workflow scenarios

**Avoid:**
- Surface-level keyword searches
- Straightforward single-tool lookups
- Questions with unstable answers

## Answer Format

Answers must be:
- Single, verifiable values (not lists)
- Human-readable when possible (names over IDs)
- Derived from stable/historical data

## Evaluation File Format

```xml
<evaluation>
   <qa_pair>
      <question>Complex question requiring multiple tool calls?</question>
      <answer>Single verifiable answer</answer>
   </qa_pair>
   <!-- 10 total qa_pairs -->
</evaluation>
```

## Example

```xml
<evaluation>
   <qa_pair>
      <question>What is the total revenue from orders placed by customers in the "Enterprise" tier during Q3 2023?</question>
      <answer>$1,247,350.00</answer>
   </qa_pair>
   <qa_pair>
      <question>Which project has the most open issues assigned to users in the "Backend" team?</question>
      <answer>api-gateway</answer>
   </qa_pair>
</evaluation>
```

## Running Evaluations

Use the evaluation harness in `scripts/`:

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Run evaluation
python scripts/evaluation.py \
  --transport stdio \
  --command "node dist/index.js" \
  --evaluation evaluation.xml \
  --output results.md
```

## Evaluation Process

1. **Documentation review**: Understand API capabilities
2. **Tool inspection**: Review available tools
3. **Content exploration**: Find stable, verifiable data
4. **Question generation**: Create complex, realistic scenarios
5. **Answer verification**: Confirm answers are correct and stable
