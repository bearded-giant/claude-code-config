---
name: mcp-builder
description: Build MCP (Model Context Protocol) servers in TypeScript or Python — tool design, schemas, transports, error handling, evaluations. Auto-fires when files import `@modelcontextprotocol/sdk` or `mcp.server`, when user edits files in `mcp/` directories, or asks to "build an MCP", "add a tool to MCP", "expose X as MCP". Skip for general API/SDK work unrelated to MCP.
---

# MCP Server Development Guide

Build MCP servers in TypeScript or Python that expose external services as LLM tools.

## Four-Phase Development Process

### Phase 1: Research and Planning

Before implementation, capture:

1. **MCP Specification**: core protocol concepts (transports, schemas, annotations)
2. **Target API**: endpoints, auth method, rate limits, pagination model
3. **Existing Patterns**: similar MCP servers to copy from

Key design decisions:
- **API Coverage**: list the endpoints to expose. Prefer narrow workflow tools over 1:1 endpoint mirroring.
- **Tool Naming**: clear names with service prefix (e.g., `github_create_issue`)
- **Context Management**: tools return focused data with pagination
- **Error Messages**: include actionable next steps

### Phase 2: Implementation

Reference the implementation guide for your language:
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

- MCP server code → the project's `mcp/` directory (or `src/mcp/` if convention there).
- Plans and analysis → `.giantmem/plans/` per `workspace-rules` skill.
