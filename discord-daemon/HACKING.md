# Hacking on discord-daemon + session-mcp

How to extend this system. Recipes map "I want to do X" → the specific files to touch + the verification step. Designed so an LLM can pick a recipe, follow it, and stay aligned with the existing patterns.

If you change the public surface (HTTP API, tool names, env vars), update `discord-daemon/README.md` and `docs/cloud-claude-architecture.md` in the same commit.

---

## Module map

| File | Owns | Stable surface |
|---|---|---|
| `src/server.ts` | Boot, shutdown, hydration | env vars, signals |
| `src/config.ts` | Env + paths | exported constants |
| `src/types.ts` | Shared types incl. `InboxEvent`, `Session`, `Access` | yes — adding union variants is OK; removing is a break |
| `src/access.ts` | `access.json` r/w + pruning | `readAccess`, `saveAccess`, `pruneExpired`, `drainApprovals` |
| `src/registry.ts` | In-memory session map + persistence + recent ring buffer | `register/unregister/heartbeat/get/getByThread/list/deliver/subscribe/recent/sweepStale/loadFromDisk/persistNow` |
| `src/discord.ts` | discord.js client, thread lifecycle, permission buttons | `DiscordBot` class methods |
| `src/control.ts` | DM command parsing | `handleControlDM(input, userId, bot)` |
| `src/http.ts` | Bun.serve REST + SSE + /metrics | routes |
| `src/metrics.ts` | Counters + gauges + Prom render | `metrics.incr/setGauge/render` |
| `src/alerts.ts` | Outbound webhook | `alert(level, text)` |

session-mcp:

| File | Owns |
|---|---|
| `src/server.ts` | MCP server, tool handlers, SSE subscribe, lifecycle |
| `src/daemon-client.ts` | HTTP client to daemon |

---

## Recipes

### Add a DM control command

1. **`discord-daemon/src/control.ts`** — add a `case` for the verb in `handleControlDM`. Use existing helpers (`resolveSession`, `humanAge`). Return a string for the bot to reply with, or `null` to ignore.
2. **`discord-daemon/src/control.ts`** — append the verb + one-line description to `helpText()`.
3. **`discord-daemon/scripts/smoke-test.sh`** — add a curl check that proves the command works (use the mock-injection path to set up a session, then exercise via mock DM logic if applicable; or add unit-level coverage).
4. **`docs/cloud-claude-quickstart.md`** — add the command to the DM commands table.

Verification: `./discord-daemon/scripts/smoke-test.sh`.

### Add an `InboxEvent` kind

1. **`src/types.ts`** — extend the `InboxEvent` discriminated union with the new `kind` + payload.
2. **`src/registry.ts`** — no change needed if it just rides through `deliver` / `subscribe` / `recent`. If the event needs special handling (eviction, dedup), edit `Registry`.
3. **`src/discord.ts`** — if the daemon emits it, find the right hook (`messageCreate`, `interactionCreate`, gateway events) and call `registry.deliver`.
4. **`session-mcp/src/server.ts`** — extend `routeInbound` to forward the event back to claude. Most go through `mcp.notification`.
5. **Update `docs/cloud-claude-architecture.md`** — the inbound flow diagram + the JSON-schema appendix in this file.

Verification: smoke test injects the event and the consumer side observes it. Or run live: trigger from real Discord → check `journalctl -u discord-daemon -f`.

### Add an HTTP endpoint

1. **`src/http.ts`** — add a zod body schema near the others. Add the route in `handle()` and a typed handler. Auth gate runs before all session routes; preserve it.
2. **`session-mcp/src/daemon-client.ts`** — add a method that wraps the endpoint.
3. **`session-mcp/src/server.ts`** — wire the method into a tool (if claude needs it) or into a notification handler.
4. **`discord-daemon/README.md`** — add the endpoint to the API table.

Verification: extend `smoke-test.sh` with a `curl_json` invocation + assertion.

### Add a daemon-side tool (sendToThread variant, etc.)

1. **`src/discord.ts`** — add a method on `DiscordBot` with the new behavior. Branch on `MOCK_DISCORD` for smoke-test compatibility.
2. **HTTP route + session-mcp client + tool wrapper** — same as "Add an HTTP endpoint".
3. **MCP tool declaration in `session-mcp/src/server.ts`** — add to `ListToolsRequestSchema` handler with `inputSchema` JSON schema.

### Add a metric

1. **`src/metrics.ts`** — register the counter or gauge in the constructor.
2. **Wherever the event happens** — call `metrics.incr` / `metrics.setGauge`.
3. **`docs/cloud-claude-quickstart.md`** — mention the new metric name in the metrics section.

Verification: `curl http://claude-vps:7777/metrics | grep daemon_<your_name>`.

### Add a new env var

1. **`src/config.ts`** — read it, give a sensible default, export.
2. **`scripts/install-vps.sh`** — if it should be in `.env`, append to the generated stub.
3. **Docs:** mention in `cloud-claude-quickstart.md` env-vars/tokens table.
4. **systemd unit** in `discord-daemon/systemd/discord-daemon.service` — only edit if the value needs to be read at process spawn (it shouldn't; `loadEnvFile()` handles `.env`).

### Add a SessionStart hook

1. **`hooks/<name>.py`** (or `.sh`) — small, idempotent.
2. **`settings.json`** — append a `{ "type": "command", "command": "..." }` entry to the `SessionStart` array.
3. **`hooks/<name>.py`** — write to stderr only on action or error. Silent on no-op.

Verification: start a fresh claude session, observe hook output via `--debug` or by writing a tracer line.

### Rename a public surface (tool, env var, endpoint)

1. Grep the old name across `discord-daemon/`, `session-mcp/`, `scripts/`, `docs/`, `hooks/`, `settings.json`.
2. Replace inline. Don't ship backwards-compat aliases — small surface, no external consumers.
3. Update both READMEs and `cloud-claude-architecture.md`.
4. Re-run smoke test.

---

## State file schemas

These files live under `~/.claude/channels/discord/` on the host running the daemon.

### `.env` (chmod 600)

```ini
DISCORD_BOT_TOKEN=MTxxx...                  # required
DISCORD_SESSIONS_CHANNEL_ID=123456...       # required — text channel for threads
DAEMON_TOKEN=hex32                          # required — shared secret with session-mcp
DAEMON_BIND_HOST=0.0.0.0                    # 0.0.0.0 for same-host + tailnet
DAEMON_BIND_PORT=7777                       # default 7777
DAEMON_ALERT_WEBHOOK=https://ntfy.sh/...    # optional — gateway up/down + shutdown
HEARTBEAT_STALE_MS=90000                    # optional
DAEMON_DISCORD_MOCK=1                       # smoke-test only — never set in prod
DAEMON_ARCHIVE_ON_EXIT=1                    # optional — archive threads on SIGTERM
```

### `access.json` (chmod 600)

```json
{
  "dmPolicy": "pairing | allowlist | disabled",
  "allowFrom": ["<discord-user-id>", ...],
  "groups": {
    "<discord-channel-id>": {
      "requireMention": true,
      "allowFrom": ["<discord-user-id>", ...]
    }
  },
  "pending": {
    "<6-hex-code>": {
      "senderId": "<discord-user-id>",
      "chatId": "<dm-channel-id>",
      "createdAt": 1779000000000,
      "expiresAt": 1779003600000,
      "replies": 1
    }
  },
  "mentionPatterns": ["@mybot"],
  "ackReaction": "👀",
  "replyToMode": "off | first | all",
  "textChunkLimit": 2000,
  "chunkMode": "length | newline"
}
```

`groups` and `mentionPatterns` are reserved for non-thread guild channels; the daemon currently routes only thread messages, so these fields are unused in the multi-session flow.

### `sessions.json` (chmod 600, written by daemon)

```json
{
  "sessions": [
    {
      "sessionId": "uuid-or-claude-provided",
      "label": "feature-foo",
      "cwd": "/home/bryan/dev/feature-foo",
      "pid": 12345,
      "threadId": "1500000000000000000",
      "registeredAt": 1779000000000,
      "lastHeartbeat": 1779000030000
    }
  ]
}
```

Written via atomic `tmp + rename`. Debounced 1s on register/heartbeat/unregister. Synchronous flush on SIGTERM.

### `approved/<senderId>` (transient)

Plain text file. Contents: the DM channel ID. Written by the `/discord:access pair` skill on a host, polled+drained by the daemon every 5s, sends "Paired!" to the user.

---

## Testing

- **Unit/integration**: `discord-daemon/scripts/smoke-test.sh` — boots daemon in `MOCK_DISCORD=1`, exercises every HTTP route, asserts side effects via log scraping + JSON parsing. Add cases here when you ship a new endpoint.
- **Typecheck**: `cd discord-daemon && ./node_modules/.bin/tsc --noEmit` and same in `session-mcp/`. CI not yet wired; run before push.
- **Live**: deploy via `rsync` to `~/dev/claude-code-config/discord-daemon/` on VPS, `sudo systemctl restart discord-daemon`, watch `journalctl -u discord-daemon -f`.

## Don'ts

- Don't add MCPs to `~/.claude/settings.json` `mcpServers` block — they aren't auto-loaded. Use `claude mcp add` so they land in `~/.claude.json`.
- Don't sync `node_modules/` via Mutagen — already excluded in `scripts/mutagen-sync-dev.sh`.
- Don't store secrets outside `.env`. Tokens in `settings.json` would be checked into git via stow.
- Don't bind the daemon to a public interface. `0.0.0.0` is OK because Hetzner firewall blocks 7777, but if you change cloud provider, verify the firewall first.
- Don't archive threads on every shutdown — that's only for intentional teardown (`DAEMON_ARCHIVE_ON_EXIT=1`). Default behavior preserves threads so restarts are seamless.

## Lessons & ongoing notes

See [`docs/cloud-claude-lessons.md`](../docs/cloud-claude-lessons.md). Append there when you discover something non-obvious — that doc is the running log future agents read first.
