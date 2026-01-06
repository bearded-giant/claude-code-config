#!/usr/bin/env python3
"""MCP Connection Handler Module.

Provides lightweight connection handling for MCP servers across multiple transport types.
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client


class MCPConnection(ABC):
    """Abstract base class for MCP connections."""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._exit_stack = None

    @abstractmethod
    async def connect(self) -> ClientSession:
        """Establish connection and return session."""
        pass

    async def __aenter__(self) -> "MCPConnection":
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()
        self.session = await self.connect()
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._exit_stack:
            await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools with metadata."""
        if not self.session:
            raise RuntimeError("Not connected")
        result = await self.session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool and return result."""
        if not self.session:
            raise RuntimeError("Not connected")
        result = await self.session.call_tool(name, arguments)
        return result.content


class MCPConnectionStdio(MCPConnection):
    """Connection via stdio for local processes."""

    def __init__(self, command: str, args: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None):
        super().__init__()
        self.command = command
        self.args = args or []
        self.env = env

    async def connect(self) -> ClientSession:
        read, write = await self._exit_stack.enter_async_context(
            stdio_client(self.command, self.args, self.env)
        )
        return await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )


class MCPConnectionSSE(MCPConnection):
    """Connection via Server-Sent Events."""

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        super().__init__()
        self.url = url
        self.headers = headers or {}

    async def connect(self) -> ClientSession:
        read, write = await self._exit_stack.enter_async_context(
            sse_client(self.url, self.headers)
        )
        return await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )


class MCPConnectionHTTP(MCPConnection):
    """Connection via streamable HTTP."""

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        super().__init__()
        self.url = url
        self.headers = headers or {}

    async def connect(self) -> ClientSession:
        read, write = await self._exit_stack.enter_async_context(
            streamablehttp_client(self.url, self.headers)
        )
        return await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )


def create_connection(
    transport: str,
    command: Optional[str] = None,
    url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    env: Optional[Dict[str, str]] = None
) -> MCPConnection:
    """Factory function to create appropriate connection type."""
    if transport == "stdio":
        if not command:
            raise ValueError("stdio transport requires 'command' parameter")
        return MCPConnectionStdio(command, env=env)
    elif transport == "sse":
        if not url:
            raise ValueError("sse transport requires 'url' parameter")
        return MCPConnectionSSE(url, headers)
    elif transport == "http":
        if not url:
            raise ValueError("http transport requires 'url' parameter")
        return MCPConnectionHTTP(url, headers)
    else:
        raise ValueError(f"Unknown transport: {transport}")
