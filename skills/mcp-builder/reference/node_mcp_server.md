# Node/TypeScript MCP Server Implementation Guide

## Quick Reference

### Key Imports
```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import express from "express";
import { z } from "zod";
```

### Server Initialization
```typescript
const server = new McpServer({
  name: "service-mcp-server",
  version: "1.0.0"
});
```

### Tool Registration Pattern
```typescript
server.registerTool(
  "tool_name",
  {
    title: "Tool Display Name",
    description: "What the tool does",
    inputSchema: { param: z.string() },
    annotations: { readOnlyHint: true }
  },
  async ({ param }) => {
    return {
      content: [{ type: "text", text: JSON.stringify(result) }],
      structuredContent: result
    };
  }
);
```

---

## Server Naming Convention

Format: `{service}-mcp-server` (lowercase with hyphens)
Examples: `github-mcp-server`, `jira-mcp-server`, `stripe-mcp-server`

## Project Structure

```
{service}-mcp-server/
├── package.json
├── tsconfig.json
├── README.md
├── src/
│   ├── index.ts          # Main entry point
│   ├── types.ts          # TypeScript interfaces
│   ├── tools/            # Tool implementations
│   ├── services/         # API clients
│   ├── schemas/          # Zod schemas
│   └── constants.ts      # Shared constants
└── dist/                 # Built JavaScript
```

---

## Tool Implementation

### Complete Tool Example

```typescript
import { z } from "zod";

enum ResponseFormat {
  MARKDOWN = "markdown",
  JSON = "json"
}

const UserSearchInputSchema = z.object({
  query: z.string()
    .min(2, "Query must be at least 2 characters")
    .max(200, "Query must not exceed 200 characters")
    .describe("Search string to match against names/emails"),
  limit: z.number()
    .int()
    .min(1)
    .max(100)
    .default(20)
    .describe("Maximum results to return"),
  offset: z.number()
    .int()
    .min(0)
    .default(0)
    .describe("Number of results to skip"),
  response_format: z.nativeEnum(ResponseFormat)
    .default(ResponseFormat.MARKDOWN)
    .describe("Output format")
}).strict();

type UserSearchInput = z.infer<typeof UserSearchInputSchema>;

server.registerTool(
  "example_search_users",
  {
    title: "Search Example Users",
    description: `Search for users by name, email, or team.

Args:
  - query (string): Search string (2-200 chars)
  - limit (number): Max results 1-100 (default: 20)
  - offset (number): Pagination offset (default: 0)
  - response_format ('markdown' | 'json'): Output format

Returns:
  JSON: { total, count, offset, users: [{id, name, email}], has_more }

Examples:
  - "Find marketing team" -> query="team:marketing"
  - "Search for John" -> query="john"`,
    inputSchema: UserSearchInputSchema,
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: true
    }
  },
  async (params: UserSearchInput) => {
    try {
      const data = await makeApiRequest("users/search", "GET", undefined, {
        q: params.query,
        limit: params.limit,
        offset: params.offset
      });

      const output = {
        total: data.total,
        count: data.users.length,
        offset: params.offset,
        users: data.users,
        has_more: data.total > params.offset + data.users.length
      };

      const textContent = params.response_format === ResponseFormat.MARKDOWN
        ? formatMarkdown(output)
        : JSON.stringify(output, null, 2);

      return {
        content: [{ type: "text", text: textContent }],
        structuredContent: output
      };
    } catch (error) {
      return {
        content: [{ type: "text", text: handleApiError(error) }]
      };
    }
  }
);
```

---

## Zod Schema Patterns

```typescript
// Basic validation
const CreateUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
  age: z.number().int().min(0).max(150)
}).strict();

// Enums
enum ResponseFormat {
  MARKDOWN = "markdown",
  JSON = "json"
}

const SearchSchema = z.object({
  response_format: z.nativeEnum(ResponseFormat).default(ResponseFormat.MARKDOWN)
});

// Pagination
const PaginationSchema = z.object({
  limit: z.number().int().min(1).max(100).default(20),
  offset: z.number().int().min(0).default(0)
});
```

---

## Shared Utilities

### API Client
```typescript
async function makeApiRequest<T>(
  endpoint: string,
  method: "GET" | "POST" | "PUT" | "DELETE" = "GET",
  data?: any,
  params?: any
): Promise<T> {
  const response = await axios({
    method,
    url: `${API_BASE_URL}/${endpoint}`,
    data,
    params,
    timeout: 30000,
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json"
    }
  });
  return response.data;
}
```

### Error Handler
```typescript
function handleApiError(error: unknown): string {
  if (error instanceof AxiosError) {
    if (error.response) {
      switch (error.response.status) {
        case 404: return "Error: Resource not found.";
        case 403: return "Error: Permission denied.";
        case 429: return "Error: Rate limit exceeded.";
        default: return `Error: API failed with status ${error.response.status}`;
      }
    } else if (error.code === "ECONNABORTED") {
      return "Error: Request timed out.";
    }
  }
  return `Error: ${error instanceof Error ? error.message : String(error)}`;
}
```

---

## Transport Setup

### stdio (Local)
```typescript
async function runStdio() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MCP server running via stdio");
}
```

### Streamable HTTP (Remote)
```typescript
async function runHTTP() {
  const app = express();
  app.use(express.json());

  app.post('/mcp', async (req, res) => {
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true
    });
    res.on('close', () => transport.close());
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  });

  app.listen(3000, () => console.error("MCP server on http://localhost:3000/mcp"));
}
```

---

## Package Configuration

### package.json
```json
{
  "name": "{service}-mcp-server",
  "version": "1.0.0",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "start": "node dist/index.js",
    "dev": "tsx watch src/index.ts",
    "build": "tsc"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.6.1",
    "axios": "^1.7.9",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "tsx": "^4.19.2",
    "typescript": "^5.7.2"
  }
}
```

### tsconfig.json
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "Node16",
    "moduleResolution": "Node16",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

---

## Quality Checklist

### Implementation
- [ ] All tools use `registerTool` with complete configuration
- [ ] All tools include title, description, inputSchema, annotations
- [ ] Zod schemas have constraints and `.strict()` enforcement
- [ ] Descriptions include args, return schema, examples
- [ ] Error messages are actionable

### TypeScript
- [ ] Interfaces defined for all data structures
- [ ] Strict mode enabled
- [ ] No `any` types
- [ ] All async functions have explicit return types

### Build
- [ ] `npm run build` succeeds
- [ ] `node dist/index.js` runs
- [ ] Sample tool calls work
