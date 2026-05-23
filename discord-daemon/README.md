# discord-daemon

Multi-session Discord channel for Claude Code. Runs on a VPS, owns the Discord gateway, exposes HTTP+SSE on a tailnet for any number of claude sessions.

## Why

The bundled `discord` plugin is stdio-coupled to one claude process. Multiple concurrent sessions clobber each other; restarts kill the bot presence. This daemon decouples Discord from claude lifecycles:

- one bot, many sessions
- each session gets its own thread
- DMs reserved for control commands
- bot survives claude restarts

## Layout

```
src/
  server.ts        # entrypoint
  config.ts        # env + paths
  types.ts         # shared types
  access.ts        # access.json reader/writer (mirrors /discord:access skill)
  registry.ts      # in-memory session map + SSE subscriber set
  discord.ts       # gateway client, thread lifecycle, send/edit/react
  control.ts       # DM command handler (list/status/kill/help)
  http.ts          # Bun.serve REST + SSE inbox
systemd/discord-daemon.service
scripts/install-vps.sh
```

## Run locally

```
bun install
DISCORD_BOT_TOKEN=... \
DISCORD_SESSIONS_CHANNEL_ID=... \
DAEMON_TOKEN=secret123 \
bun run src/server.ts
```

## API surface (token-gated, header `x-daemon-token`)

| Method | Path                          | Body / Notes                                   |
|--------|-------------------------------|------------------------------------------------|
| GET    | /health                       | `{ ok, sessions }`                             |
| GET    | /sessions                     | list active sessions                           |
| POST   | /sessions                     | `{ session_id, label, cwd, pid }` → thread     |
| DELETE | /sessions/:id                 | unregister + archive thread                    |
| POST   | /sessions/:id/heartbeat       | refresh lastHeartbeat                          |
| POST   | /sessions/:id/send            | `{ chat_id, text, reply_to?, files? }`         |
| POST   | /sessions/:id/edit            | `{ chat_id, message_id, text }`                |
| POST   | /sessions/:id/react           | `{ chat_id, message_id, emoji }`               |
| POST   | /sessions/:id/fetch           | `{ chat_id, limit? }` → `{ text }`             |
| POST   | /sessions/:id/download        | `{ chat_id, message_id }` → file paths         |
| GET    | /sessions/:id/inbox           | SSE — kind: hello \| message \| permission_reply |

Each session may only act on its own `threadId`. Cross-session calls return 403.

## Discord behavior

- **Thread channel** = `DISCORD_SESSIONS_CHANNEL_ID`. Bot creates one thread per registered session, named `{label}-{shortid}`.
- **DMs** route to `control.ts`. Commands: `list`, `status <label>`, `kill <label>`, `help`. Never forwarded to a session.
- **Thread messages** route to the matching session's SSE inbox.
- **Pairing flow** unchanged from the bundled plugin — `/discord:access` skill on the VPS approves codes.
- **Heartbeat** 30s from sessions; daemon evicts after 90s and archives the thread.

## Security

- HTTP listens on `DAEMON_BIND_HOST` only (set to tailnet IP). Token required on every request, constant-time compare.
- `access.json` controls who can post in threads (allowlist of Discord user IDs).
- Files sent via `reply` are sandboxed away from daemon state (`~/.claude/channels/discord` except `inbox/`).

## Smoke test (no Discord required)

```
bun install
./scripts/smoke-test.sh
```

Spawns daemon with `DAEMON_DISCORD_MOCK=1`, exercises the full HTTP+SSE surface, asserts auth, registry, inbox stream, send/edit/react, and chat_id isolation. 16 checks.

## CLI helper

```
DAEMON_TOKEN=... DAEMON_URL=http://claude-vps:7777 ./scripts/daemon-cli.sh list
./scripts/daemon-cli.sh tail <session_id>     # follow SSE
./scripts/daemon-cli.sh kill <label>
```

Persist creds in `~/.discord-daemon-cli`.

## Mock-mode endpoints (smoke testing only)

When `DAEMON_DISCORD_MOCK=1`:

- `POST /_mock/inject` — `{ thread_id, content, user?, user_id? }` — simulates an inbound thread message.

Disabled otherwise.

## Limits not yet implemented

- Permission relay (the `notifications/claude/channel/permission_request` flow with Allow/Deny buttons) — bundled plugin has it, this daemon doesn't yet. Add later if you want permission prompts via Discord across sessions.
- Group channel support (non-thread guild channels) — daemon currently only writes to its own session threads. Read fetch_messages also restricted to own thread.

See `docs/cloud-claude-setup.md` for the full VPS + Tailscale + Mutagen walkthrough.
