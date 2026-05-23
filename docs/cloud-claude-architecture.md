# Cloud Claude — Architecture

Multi-session Claude Code on a remote VPS, controllable from a phone via Discord, with the laptop as the canonical source of truth.

## Doc index (start here)

| If you want to… | Read |
|---|---|
| Stand it up the first time | [`cloud-claude-quickstart.md`](cloud-claude-quickstart.md) |
| Understand the system end-to-end | this doc |
| Re-provision from scratch / debug bootstrap | [`cloud-claude-provisioning-runbook.md`](cloud-claude-provisioning-runbook.md) |
| Extend the daemon or session-mcp | [`../discord-daemon/HACKING.md`](../discord-daemon/HACKING.md) |
| Check what surprised people before | [`cloud-claude-lessons.md`](cloud-claude-lessons.md) |
| Day-to-day ops (DM commands, metrics, backups) | [`cloud-claude-quickstart.md`](cloud-claude-quickstart.md) "Day-to-day use" |
| API reference | [`../discord-daemon/README.md`](../discord-daemon/README.md) |
| Module map | [`../discord-daemon/HACKING.md`](../discord-daemon/HACKING.md) |

---

## C4 — Level 1: System context

```
                   ┌────────────────┐
                   │     You        │
                   │  (laptop +     │
                   │   phone)       │
                   └───────┬────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
       ┌────────┐    ┌──────────┐    ┌────────────┐
       │ Hetzner│    │ Tailscale│    │  Discord   │
       │  VPS   │    │  (mesh   │    │  (mobile + │
       │ (claude│    │   VPN)   │    │   desktop) │
       │ +daemon│    │          │    │            │
       └────────┘    └──────────┘    └────────────┘
            ▲              ▲              ▲
            │              │              │
            └─────── Anthropic API ───────┘
                    (each claude session
                     talks to Claude models)
```

Three external systems: Hetzner (compute), Tailscale (network identity), Discord (UI). Everything else lives inside the VPS.

---

## C4 — Level 2: Containers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            Laptop (macOS)                                │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Tailscale   │  │   Mutagen    │  │  ~/dev (src) │  │   tmux +     │ │
│  │  app (mesh)  │  │  daemon      │  │   80GB raw,  │  │   mosh/ssh   │ │
│  │              │  │  (one-way    │  │  ~12GB sync  │  │              │ │
│  │              │  │  -safe)      │  │              │  │              │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │ tailnet         │ SSH (public IP) │                 │ SSH/mosh│
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────┘
          │                 │                 │                 │
          │                 │                 │                 │
┌─────────┼─────────────────┼─────────────────┼─────────────────┼─────────┐
│         ▼                 ▼                 ▼                 ▼          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                       Hetzner CCX33 (Ubuntu 24.04)              │    │
│  │                                                                 │    │
│  │  ┌───────────────┐         ┌───────────────────────┐            │    │
│  │  │ Tailscale +   │◄────────┤ tmux (persistent)     │            │    │
│  │  │ public sshd   │         │                       │            │    │
│  │  └───────────────┘         │  pane: claude session │ ─── stdio ─┼─►  │
│  │                            │  pane: claude session │     MCP    │    │
│  │  ┌───────────────┐         │  pane: claude session │            │    │
│  │  │ Mutagen agent │ writes  │                       │            │    │
│  │  │ → /home/bryan │ ──────► │  each claude:         │            │    │
│  │  │   /dev        │         │   --channels          │            │    │
│  │  └───────────────┘         │     server:discord    │            │    │
│  │                            └──────────┬────────────┘            │    │
│  │                                       │ HTTP + SSE              │    │
│  │                                       │ (loopback)              │    │
│  │                                       ▼                         │    │
│  │                            ┌───────────────────────┐            │    │
│  │                            │ discord-daemon        │            │    │
│  │                            │ (systemd, Bun)        │            │    │
│  │                            │                       │            │    │
│  │                            │  - HTTP API           │            │    │
│  │                            │  - SSE inbox          │            │    │
│  │                            │  - thread per session │            │    │
│  │                            │  - allowlist gate     │            │    │
│  │                            └──────────┬────────────┘            │    │
│  │                                       │                         │    │
│  │                                       │ Discord gateway         │    │
│  │                                       │ (WSS)                   │    │
│  └───────────────────────────────────────┼─────────────────────────┘    │
└──────────────────────────────────────────┼─────────────────────────────┘
                                           │
                                           ▼
                            ┌──────────────────────────┐
                            │   Discord                │
                            │   ┌──────────────────┐   │
                            │   │ sessions channel │   │
                            │   │  ├─ thread A     │   │
                            │   │  ├─ thread B     │   │
                            │   │  └─ thread C     │   │
                            │   └──────────────────┘   │
                            │   ┌──────────────────┐   │
                            │   │  DM (control)    │   │
                            │   └──────────────────┘   │
                            └───────────┬──────────────┘
                                        │
                                        ▼
                              ┌────────────────┐
                              │  You — phone   │
                              │   (anywhere)   │
                              └────────────────┘
```

---

## C4 — Level 3: Inside the VPS

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Hetzner VPS (claude-vps)                           │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐    │
│ │           Per-session subprocess tree (one per pane)            │    │
│ │                                                                 │    │
│ │  tmux pane                                                      │    │
│ │   └─ claude (CLI, ~/.local/bin/claude)                          │    │
│ │       └─ session-mcp (bun child, stdio MCP)                     │    │
│ │           ├─ POST /sessions     (register, get threadId)        │    │
│ │           ├─ POST /sessions/:id/heartbeat   (every 30s)         │    │
│ │           ├─ POST /sessions/:id/{send,edit,react,fetch,...}     │    │
│ │           └─ GET  /sessions/:id/inbox       (SSE stream)        │    │
│ │                                                                 │    │
│ └─────────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│ ┌─────────────────────────────────────────────────────────────────┐    │
│ │   discord-daemon (systemd, Bun, single instance)                │    │
│ │                                                                 │    │
│ │   src/                                                          │    │
│ │     server.ts    entrypoint, lifecycle                          │    │
│ │     http.ts      Bun.serve REST + SSE                           │    │
│ │     registry.ts  in-memory Map<sessionId, {threadId, ...}>      │    │
│ │     discord.ts   discord.js client, gateway                     │    │
│ │     control.ts   DM command parsing (list/status/kill)          │    │
│ │     access.ts    access.json read/write (allowlist)             │    │
│ │                                                                 │    │
│ │   state:                                                        │    │
│ │     ~/.claude/channels/discord/                                 │    │
│ │       .env             bot token, daemon token, bind host       │    │
│ │       access.json      dmPolicy + allowFrom user IDs            │    │
│ │       approved/        pairing approval markers                 │    │
│ │       inbox/           downloaded attachments                   │    │
│ │                                                                 │    │
│ │   ports: 0.0.0.0:7777 (loopback + tailnet, NOT public)          │    │
│ │   auth:  x-daemon-token header, constant-time compare           │    │
│ └─────────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│                       Discord gateway (WSS)                             │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Flows

### Session lifecycle

```
claude --channels server:discord
  └─► spawn session-mcp
        └─► POST /sessions {session_id, label, cwd, pid}
              └─► daemon.discord.createSessionThread(label, cwd)
                    └─► thread "<label>-<id>" appears in Discord
              └─► daemon.registry.register(...)
              └─► returns {threadId} to session-mcp
        └─► open SSE /sessions/:id/inbox  (long-lived)
        └─► heartbeat every 30s

claude exits / SIGTERM
  └─► session-mcp DELETE /sessions/:id
        └─► daemon.discord.archiveSessionThread(threadId)
              └─► thread archived in Discord
        └─► registry drops entry, closes SSE
```

### Inbound message (Discord → claude)

```
Discord user posts in thread X
  └─► discord.js messageCreate event
        └─► daemon.gate(msg) — allowlist check
              └─► reject if user not in allowFrom OR archived thread
        └─► registry.getByThread(X.id) → session S
        └─► registry.deliver(S, {kind: 'message', ...})
              └─► SSE write to all subscribers of S
                    └─► session-mcp receives via fetch reader
                          └─► mcp.notification('claude/channel', ...)
                                └─► claude sees as inbound user msg
```

### Outbound message (claude → Discord)

```
claude calls `reply` tool
  └─► session-mcp POST /sessions/:id/send {chat_id, text, files?, reply_to?}
        └─► daemon.authorize(session_id, chat_id) — must match own threadId
        └─► daemon.discord.sendToThread(threadId, text)
              └─► discord.js channel.send(...)
                    └─► message posted in thread
        └─► returns {ids} to session-mcp → claude tool result
```

### DM control (no claude session involved)

```
Discord user DMs the bot
  └─► daemon.handleDM(msg)
        └─► access.allowFrom check
        └─► control.handleControlDM(text)
              └─► "list" → registry.list() → markdown table
              └─► "kill <label>" → registry.unregister + thread archive
              └─► "status <label>" → registry.get + format
        └─► msg.reply(text)
```

---

## Tooling overview

| Tool | Where | Purpose | Key interactions |
|---|---|---|---|
| **Hetzner Cloud (CCX33)** | external | Hosts the VPS (8 vCPU / 32GB / 240GB / ~$40/mo) | provisioned by `scripts/provision-hetzner.sh` via `hcloud` CLI |
| **hcloud CLI** | laptop | Talks to Hetzner Cloud API | `hcloud context create claude` once; provisioning script uses it |
| **Tailscale** | laptop + phone + VPS | Mesh VPN. Stable hostnames + identity-based ACL | `tailscale up --ssh` on VPS; `ssh bryan@claude-vps` resolves anywhere |
| **OpenSSH (regular, port 22)** | VPS public IP | File transfer + Mutagen agent (Tailscale SSH strips exec bits) | `scp`, `rsync`, Mutagen — always public IP |
| **Tailscale SSH** | tailnet | Interactive shell, no key management | `ssh bryan@claude-vps` |
| **Mutagen** | laptop daemon + VPS agent | Continuous file sync laptop→VPS (`one-way-safe`) | `scripts/mutagen-sync-dev.sh` creates session |
| **GNU stow** | VPS (and laptop) | Symlink-tree manager — turns `~/dev/claude-code-config` into `~/.claude` | `install.sh` runs it |
| **GNU bash + bun + node** | VPS | Runtimes for daemon (bun), hooks (node) | systemd + bunshell |
| **discord-daemon** | VPS systemd | Single Discord gateway, multi-session routing | This repo's `discord-daemon/` |
| **session-mcp** | VPS, per-claude | Stdio MCP server, HTTP client of daemon | This repo's `session-mcp/` |
| **Claude Code CLI** | VPS (per pane) | The AI agent | `claude --dangerously-load-development-channels server:discord` |
| **Discord bot (`BG-CLC`)** | external | UI surface for chat + control | Channel threads = chat, DM = control |
| **systemd** | VPS | Daemon supervision | `discord-daemon.service` |
| **journalctl** | VPS | Daemon logs | `sudo journalctl -u discord-daemon -f` |

---

## Security boundaries

| Boundary | Mechanism |
|---|---|
| Hetzner firewall | Only SSH (22) + ICMP open from public internet. 7777 blocked publicly. |
| Daemon HTTP | Binds `0.0.0.0:7777` → reachable only via loopback (same-host sessions) + tailnet interface (laptop/phone). Public ingress blocked by Hetzner firewall. |
| Daemon auth | `x-daemon-token` header, constant-time compare. Token in `.env` chmod 600. |
| Discord access | `access.json` allowlist of Discord user IDs. Bot ignores messages from non-allowlisted senders. |
| Bot pairing | `/discord:access pair <code>` skill; codes expire 1h; 3 max concurrent. |
| chat_id authorization | Session can only act on its own `threadId`. Cross-session calls return 403. |
| File send sandbox | `assertSendable` blocks sending daemon state files via `reply`. |
| Tailscale ACL | Lock to your own tailnet only (admin console). |
| Public SSH | Tailscale SSH (`--ssh`) handles interactive auth via tailnet identity. Public sshd keeps key auth (no passwords). |

---

## Failure modes + behaviors

| Event | What happens |
|---|---|
| Laptop closes | SSH/mosh sessions disconnect. VPS tmux + claude + daemon keep running. Phone Discord still works. |
| Reopen laptop | `ssh bryan@claude-vps; tmux attach -t main` → exact prior state. |
| Daemon crashes | systemd restarts (Restart=always, 5s). Sessions reconnect SSE on backoff. |
| Discord gateway drops | discord.js auto-reconnects. SessionsMC keep heartbeating. |
| Claude session crashes | Heartbeat stops. After 90s daemon evicts the session + archives its thread. |
| VPS reboots | systemd starts daemon. Sessions need manual restart in tmux. Mutagen reconnects. |
| Mutagen network drop | Reconnects automatically. Edits queued. No data loss. |
| Both sides edit same file | one-way-safe halts propagation → conflict shown. Manual resolve. |
| Token rotation needed | Edit `~/.claude/channels/discord/.env`, `sudo systemctl restart discord-daemon`. |

---

## State file schemas

Authoritative location: [`../discord-daemon/HACKING.md`](../discord-daemon/HACKING.md) "State file schemas". Quick summary:

- **`.env`** — bot token, daemon token, bind host/port, optional alert webhook
- **`access.json`** — `dmPolicy` + `allowFrom` user IDs + (unused-today) groups/pending
- **`sessions.json`** — registry persistence; written by daemon, hydrated on boot
- **`approved/<senderId>`** — transient pairing approval marker

All live under `~/.claude/channels/discord/` on the host running the daemon.

## File system layout

### Laptop

```
~/dev/                            (Mutagen alpha)
  claude-code-config/             stowed → ~/.claude
    discord-daemon/               daemon source
    session-mcp/                  session MCP source
    scripts/                      provisioning + wrappers
    docs/                         these docs
  giant-tooling/                  workspace + giantmem (sibling repo)
  <your repos>/

~/.claude/                        stowed from claude-code-config
  settings.json                   committed, shared
  settings.local.json             VPS overlay candidate (gitignored)
  channels/discord/               daemon state (NOT in stow source)
    .env                          bot token, daemon token
    access.json                   user allowlist
```

### VPS

```
/home/bryan/
  dev/                            (Mutagen beta)
    claude-code-config/           rsync'd then mutagen-synced
      discord-daemon/             daemon source
      session-mcp/                MCP source
    giant-tooling/                cloned by install.sh
    <your repos>/                 synced from laptop
  .claude/                        stowed from ~/dev/claude-code-config
    settings.local.json           VPS-specific overlay (gitignored)
    channels/discord/             daemon state
      .env                        DISCORD_BOT_TOKEN, DAEMON_TOKEN, DAEMON_BIND_HOST
      access.json
  .claude.json                    claude mcp registry (created by `claude mcp add`)
  .local/bin/claude               claude CLI (installed by install.sh)
  .bun/bin/bun                    bun runtime
/Users/bryan → /home/bryan        root-level symlink so laptop-absolute symlinks resolve
/etc/systemd/system/discord-daemon.service
```
