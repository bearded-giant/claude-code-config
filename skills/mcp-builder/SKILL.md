---
name: mcp-builder
description: Use this skill when building MCP (Model Context Protocol) servers. This includes creating new MCP servers in TypeScript or Python, implementing tools with proper schemas, setting up transports, and following MCP best practices for tool design, error handling, and documentation.
---

# MCP Server Development Guide

This skill provides comprehensive guidance for building high-quality MCP servers that enable LLMs to interact with external services through well-designed tools.

## Four-Phase Development Process

### Phase 1: Deep Research and Planning

Before implementation, thoroughly research:

1. **MCP Specification**: Review the core protocol concepts
2. **Target API Documentation**: Understand endpoints, auth, rate limits
3. **Existing Patterns**: Check for similar MCP servers as reference

Key design decisions:
- **API Coverage**: Balance comprehensive endpoint coverage with specialized workflow tools
- **Tool Naming**: Use clear, descriptive names with service prefix (e.g., `github_create_issue`)
- **Context Management**: Design tools returning focused, relevant data with pagination
- **Error Messages**: Provide actionable guidance with specific next steps

### Phase 2: Implementation

Reference the appropriate implementation guide:
- **TypeScript/Node**: @reference/node_mcp_server.md
- **Python**: @reference/python_mcp_server.md
- **Best Practices**: @reference/mcp_best_practices.md

Implementation checklist:
- [ ] Set up project structure (language-specific)
- [ ] Create shared utilities (API client, auth, error handling, pagination)
- [ ] Implement tools with input/output schemas (Zod for TS, Pydantic for Python)
- [ ] Add clear descriptions and examples for each tool
- [ ] Implement proper async operations and error handling
- [ ] Add tool annotations (readOnlyHint, destructiveHint, etc.)

### Phase 3: Review and Test

Quality verification:
- [ ] Code follows DRY principles
- [ ] Full type coverage (no `any` in TS, proper hints in Python)
- [ ] Consistent error handling across all tools
- [ ] Build succeeds without errors
- [ ] Tools work with MCP Inspector

Build commands:
- **TypeScript**: `npm run build && node dist/index.js`
- **Python**: `python your_server.py`

### Phase 4: Create Evaluations

Develop 10 independent, read-only evaluation questions:
- Complex enough to require multiple tool calls
- Realistic user scenarios
- Stable, verifiable answers

See @reference/evaluation.md for evaluation methodology.

## Technology Recommendations

| Aspect | Recommendation |
|--------|----------------|
| Language | TypeScript (better SDK, AI code generation) |
| Transport | Streamable HTTP (remote) or stdio (local) |
| Validation | Zod (TS) or Pydantic (Python) |

## Quick Reference

### Server Naming
- **Python**: `{service}_mcp` (e.g., `slack_mcp`)
- **TypeScript**: `{service}-mcp-server` (e.g., `slack-mcp-server`)

### Tool Naming
- Use snake_case with service prefix
- Format: `{service}_{action}_{resource}`
- Example: `slack_send_message`, `github_create_issue`

### Tool Annotations
| Annotation | Description |
|------------|-------------|
| `readOnlyHint` | Tool does not modify environment |
| `destructiveHint` | Tool may perform destructive updates |
| `idempotentHint` | Repeated calls have no additional effect |
| `openWorldHint` | Tool interacts with external entities |

## Output Location

Write MCP server implementations to appropriate project directories. Write plans and analysis to `.giantmem/plans/` per workspace rules.
