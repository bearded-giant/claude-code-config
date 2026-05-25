# Cloud Claude — Architecture

Multi-session Claude Code on a remote VPS, controllable from a phone via Discord, with the laptop as the git/identity source of truth. File state is **bi-directional** — edits on either host land on the other via Mutagen `two-way-resolved`. Git remotes (push/pull, signing keys, ZTNA-gated corporate repos) live on the laptop; the VPS edits files but never pushes.

## Doc index (start here)

| If you want to… | Read |
|---|---|
| Stand it up the first time | [`cloud-claude-quickstart.md`](cloud-claude-quickstart.md) |
| Understand the system end-to-end | this doc |
| Re-provision from scratch / debug bootstrap | [`cloud-claude-provisioning-runbook.md`](cloud-claude-provisioning-runbook.md) |
| Extend the daemon or session-mcp | [`../HACKING.md`](../HACKING.md) |
| Check what surprised people before | [`cloud-claude-lessons.md`](cloud-claude-lessons.md) |
| Day-to-day ops (DM commands, metrics, backups) | [`cloud-claude-quickstart.md`](cloud-claude-quickstart.md) "Day-to-day use" |
| API reference | [`../README.md`](../README.md) |
| Module map | [`../HACKING.md`](../HACKING.md) |

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
│  │              │  │  (two-way-   │  │  ~12GB sync  │  │              │ │
│  │              │  │  resolved)   │  │              │  │              │ │
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
│  │  │ Mutagen agent │ ◄─────► │                       │            │    │
│  │  │ ↔ /home/bryan │  two-   │  each `dclaude`       │            │    │
│  │  │   /dev        │  way    │   alias loads the     │            │    │
│  │  └───────────────┘         │   server:discord MCP  │            │    │
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
│ │     registry.ts  in-memory Map<sessionId, {threadId, state, ..}>│    │
│ │                  state ∈ {active, dormant}; dormant retains     │    │
│ │                  thread mapping for resume                      │    │
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
dclaude  (= claude --dangerously-load-development-channels server:discord --dangerously-skip-permissions)
  └─► spawn session-mcp
        └─► session_id = `cwd-<sha1(cwd)[:8]>-<rand[:8]>`  (fresh per lift; CLAUDE_SESSION_ID overrides; CLAUDE_SESSION_STABLE=1 for legacy cwd-derived id)
        └─► POST /sessions {session_id, label, cwd, pid}
              ├─► registry.get(session_id) hit?
              │     ├─ yes  → reuse existing threadId, flip state → 'active'
              │     └─ no   → daemon.discord.createSessionThread(label, cwd)
              │                  └─► thread "<label>-<id>" appears in Discord
              └─► returns {threadId} to session-mcp
        └─► open SSE /sessions/:id/inbox  (long-lived)
        └─► heartbeat every 30s

claude exits / SIGTERM   (soft close — preserves thread mapping)
  └─► session-mcp DELETE /sessions/:id
        └─► registry.markDormant(session_id)
              ├─ state → 'dormant', subscribers cleared, entry retained
              └─ thread archived in Discord (auto-unarchives on next send)

Re-lift same cwd  →  NEW session_id (random suffix)  →  NEW thread
Resume specific past thread  →  CLAUDE_SESSION_ID=<old-id> dclaude  →  reattach
Legacy stable-per-cwd  →  CLAUDE_SESSION_STABLE=1 dclaude  →  cwd-<sha1[:16]>

Hard removal (intentional teardown):
  DM `kill <label>` → registry.delete(session_id) + archive thread.
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
              └─► "list" → registry.list() → markdown table (active + dormant tagged)
              └─► "kill <label>" → registry.delete (hard) + thread archive
              └─► "status <label>" → registry.get + format (includes state)
        └─► msg.reply(text)
```

---

## Tooling overview

| Tool | Where | Purpose | Key interactions |
|---|---|---|---|
| **Hetzner Cloud (CCX33)** | external | Hosts the VPS (8 vCPU / 32GB / 240GB / ~$40/mo) | provisioned by `scripts/provision-hetzner.sh` via `hcloud` CLI |
| **hcloud CLI** | laptop | Talks to Hetzner Cloud API | `hcloud context create claude` once; provisioning script uses it |
| **Tailscale** | laptop + VPS (NOT phone) | Mesh VPN. Stable hostnames + identity-based ACL. Phone uses Discord directly, no tailnet membership needed. | `tailscale up --ssh` on VPS; `ssh bryan@claude-vps` resolves from laptop |
| **OpenSSH (regular, port 22)** | VPS public IP | File transfer + Mutagen agent (Tailscale SSH strips exec bits) | `scp`, `rsync`, Mutagen — always public IP |
| **Tailscale SSH** | tailnet | Interactive shell, no key management | `ssh bryan@claude-vps` |
| **Mutagen** | laptop daemon + VPS agent | Continuous bi-directional file sync laptop ↔ VPS (`two-way-resolved`). Conflicts resolved newest-mtime-wins. `.git/` excluded — git state is per-host, commits + pushes happen on laptop only. | `scripts/mutagen-sync-dev.sh` creates session |
| **GNU stow** | VPS (and laptop) | Symlink-tree manager — turns `~/dev/claude-code-config` into `~/.claude` | `install.sh` runs it |
| **GNU bash + bun + node** | VPS | Runtimes for daemon (bun), hooks (node) | systemd + bunshell |
| **discord-daemon** | VPS systemd | Single Discord gateway, multi-session routing | This repo's `discord-daemon/` |
| **session-mcp** | VPS, per-claude | Stdio MCP server, HTTP client of daemon | This repo's `session-mcp/` |
| **Claude Code CLI** | VPS (per pane) | The AI agent | `claude --dangerously-load-development-channels server:discord` |
| **Discord bot (`BG-CLC`)** | external | UI surface for chat + control | Channel threads = chat, DM = control |
| **systemd** | VPS | Daemon supervision | `discord-daemon.service` |
| **journalctl** | VPS | Daemon logs | `sudo journalctl -u discord-daemon -f` |

---

## Nested tmux

**Current setup — likely to change.** VPS-side tmux is how sessions survive ssh disconnects today. The shape of that may change (single-pane-per-window, drop VPS tmux for screen, or skip it entirely for users who don't want nesting). Documented here so the friction is visible:

| Layer | Leader | Notes |
|---|---|---|
| Local tmux | `C-a` | per user's local config |
| VPS tmux | `C-b` (default) | set explicitly in `~/.tmux.conf` on the VPS; red status bar tagged `VPS` |

Distinct prefixes mean keys for the outer tmux don't accidentally fire on the inner one. Users not already on tmux will still find nested-tmux confusing — open ergonomics question.

---

## Security boundaries

| Boundary | Mechanism |
|---|---|
| Hetzner firewall | Only SSH (22) + ICMP open from public internet. 7777 blocked publicly. |
| Daemon HTTP | Binds `0.0.0.0:7777` → reachable only via loopback (same-host sessions) + tailnet interface (laptop). Public ingress blocked by Hetzner firewall. |
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
| Claude session crashes | Heartbeat stops. After 90s daemon marks session dormant + archives its thread (thread mapping retained — next `dclaude` in same cwd reattaches). |
| Claude session ended normally + resumed (`claude --resume`) | Same cwd → same `session_id` → daemon reuses existing thread. Archive auto-clears on first outbound send. |
| VPS reboots | systemd starts daemon. Sessions need manual restart in tmux. Mutagen reconnects. |
| Mutagen network drop | Reconnects automatically. Edits queued. No data loss. |
| Both sides edit same file | two-way-resolved picks newest mtime. Older edit overwritten. Avoid simultaneous editing in same file from both hosts. |
| Token rotation needed | Edit `~/.claude/channels/discord/.env`, `sudo systemctl restart discord-daemon`. |

---

## State file schemas

Authoritative location: [`../HACKING.md`](../HACKING.md) "State file schemas". Quick summary:

- **`.env`** — bot token, daemon token, bind host/port, optional alert webhook
- **`access.json`** — `dmPolicy` + `allowFrom` user IDs + (unused-today) groups/pending
- **`sessions.json`** — registry persistence; written by daemon, hydrated on boot
- **`approved/<senderId>`** — transient pairing approval marker

All live under `~/.claude/channels/discord/` on the host running the daemon.

## File system layout

### Laptop

```
~/dev/                            (Mutagen alpha — bi-directional)
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
  dev/                            (Mutagen beta — bi-directional)
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
