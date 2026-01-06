# Python MCP Server Implementation Guide

## Quick Reference

### Key Imports
```python
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum
import httpx
```

### Server Initialization
```python
mcp = FastMCP("service_mcp")
```

### Tool Registration Pattern
```python
@mcp.tool(name="tool_name", annotations={...})
async def tool_function(params: InputModel) -> str:
    '''Docstring becomes tool description.'''
    pass
```

---

## Server Naming Convention

Format: `{service}_mcp` (lowercase with underscores)
Examples: `github_mcp`, `jira_mcp`, `stripe_mcp`

---

## Tool Implementation

### Complete Tool Example

```python
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from enum import Enum

mcp = FastMCP("example_mcp")

class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"

class UserSearchInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    query: str = Field(..., description="Search string", min_length=2, max_length=200)
    limit: Optional[int] = Field(default=20, description="Max results", ge=1, le=100)
    offset: Optional[int] = Field(default=0, description="Pagination offset", ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()

@mcp.tool(
    name="example_search_users",
    annotations={
        "title": "Search Example Users",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def example_search_users(params: UserSearchInput) -> str:
    '''Search for users by name, email, or team.

    Args:
        params (UserSearchInput): Search parameters

    Returns:
        str: JSON with {total, count, offset, users, has_more}
    '''
    try:
        data = await _make_api_request(
            "users/search",
            params={"q": params.query, "limit": params.limit, "offset": params.offset}
        )

        users = data.get("users", [])
        if not users:
            return f"No users found matching '{params.query}'"

        if params.response_format == ResponseFormat.MARKDOWN:
            return format_markdown(users, data["total"])
        else:
            return json.dumps({
                "total": data["total"],
                "count": len(users),
                "offset": params.offset,
                "users": users,
                "has_more": data["total"] > params.offset + len(users)
            }, indent=2)

    except Exception as e:
        return _handle_api_error(e)

if __name__ == "__main__":
    mcp.run()
```

---

## Pydantic v2 Patterns

```python
from pydantic import BaseModel, Field, field_validator, ConfigDict

class CreateUserInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: int = Field(..., ge=0, le=150)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.lower()
```

**Pydantic v2 notes:**
- Use `model_config` not nested `Config` class
- Use `field_validator` not `validator`
- Use `model_dump()` not `dict()`
- Validators require `@classmethod`

---

## Shared Utilities

### API Client
```python
async def _make_api_request(endpoint: str, method: str = "GET", **kwargs) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{API_BASE_URL}/{endpoint}",
            timeout=30.0,
            **kwargs
        )
        response.raise_for_status()
        return response.json()
```

### Error Handler
```python
def _handle_api_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Error: Resource not found."
        elif status == 403:
            return "Error: Permission denied."
        elif status == 429:
            return "Error: Rate limit exceeded."
        return f"Error: API failed with status {status}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out."
    return f"Error: {type(e).__name__}"
```

---

## Advanced Features

### Context Parameter
```python
from mcp.server.fastmcp import FastMCP, Context

@mcp.tool()
async def advanced_tool(query: str, ctx: Context) -> str:
    '''Tool with context access.'''
    await ctx.report_progress(0.5, "Processing...")
    await ctx.log_info("Query received", {"query": query})
    return result
```

### Resources
```python
@mcp.resource("file://documents/{name}")
async def get_document(name: str) -> str:
    '''Expose documents as MCP resources.'''
    with open(f"./docs/{name}", "r") as f:
        return f.read()
```

### Transport
```python
# stdio (default)
if __name__ == "__main__":
    mcp.run()

# Streamable HTTP
if __name__ == "__main__":
    mcp.run(transport="streamable_http", port=8000)
```

---

## Quality Checklist

### Implementation
- [ ] All tools have `name` and `annotations` in decorator
- [ ] Pydantic models with Field() definitions for all inputs
- [ ] Comprehensive docstrings with args and return types
- [ ] Error handling for all external calls
- [ ] Common functionality extracted into reusable functions

### Python Quality
- [ ] Type hints throughout
- [ ] All async functions use `async def`
- [ ] httpx with async context managers
- [ ] No manual validation (let Pydantic handle it)

### Testing
- [ ] `python server.py` runs
- [ ] Imports resolve correctly
- [ ] Sample tool calls work
