# session-mcp

Claude-side MCP server that proxies Discord tool calls to a remote `discord-daemon`. Drop-in replacement for the bundled `discord` plugin's stdio MCP, but every call goes over HTTP/SSE to a daemon that owns the gateway.

## Tools (same names as bundled plugin)

- `reply` — post to this session's thread
- `react` — emoji on a message
- `edit_message` — bot-authored edit
- `download_attachment` — pull message attachments to inbox
- `fetch_messages` — recent thread history

## Env

| Var | Required | Notes |
|---|---|---|
| `DISCORD_DAEMON_URL` | ✓ | e.g. `http://claude-vps:7777` or `http://127.0.0.1:7777` |
| `DISCORD_DAEMON_TOKEN` | ✓ | matches daemon's `DAEMON_TOKEN` |
| `CLAUDE_SESSION_ID` | optional | persist across restarts to re-use thread |
| `CLAUDE_SESSION_LABEL` | optional | default = `basename(cwd)` |

## settings.json

```json
{
  "mcpServers": {
    "discord": {
      "command": "bun",
      "args": ["run", "/path/to/session-mcp/src/server.ts"],
      "env": {
        "DISCORD_DAEMON_URL": "http://claude-vps:7777",
        "DISCORD_DAEMON_TOKEN": "..."
      }
    }
  }
}
```

## Lifecycle

1. On boot → `POST /sessions` to daemon. Daemon creates Discord thread.
2. Opens SSE on `/sessions/:id/inbox`. Reconnects on drop with exponential backoff.
3. Heartbeat every 30s.
4. On stdin close / SIGTERM → `DELETE /sessions/:id`. Daemon archives thread.

Inbound messages arrive via SSE and are re-emitted as `notifications/claude/channel` events, preserving the existing channel UX in Claude Code.
