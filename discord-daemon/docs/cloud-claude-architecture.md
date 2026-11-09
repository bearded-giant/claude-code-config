# Cloud Claude — Architecture

Multi-session Claude Code on a GCP devbox, controllable from a phone via Discord. Repos are git clones on both machines and push from either side; transcripts, doit lists, the vault, and per-repo `.giantmem` dirs move both ways through Mutagen `two-way-resolved`.

## Doc index (start here)

| If you want to… | Read |
|---|---|
| Stand it up the first time | [`devbox.md`](devbox.md) |
| Understand the system end-to-end | this doc |
| Debug the bootstrap | [`devbox.md`](devbox.md) "Troubleshooting" |
| Extend the daemon or session-mcp | [`../HACKING.md`](../HACKING.md) |
| Check what surprised people before | [`cloud-claude-lessons.md`](cloud-claude-lessons.md) |
| Day-to-day ops (DM commands, sync, backups) | [`devbox.md`](devbox.md) "Day to day" |
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
       │ devbox │    │ Twingate │    │  Discord   │
       │ (GCP)  │    │  (ZTNA   │    │  (mobile + │
       │ (claude│    │  tunnel) │    │   desktop) │
       │ +daemon│    │          │    │            │
       └────────┘    └──────────┘    └────────────┘
            ▲              ▲              ▲
            │              │              │
            └─────── Anthropic API ───────┘
                    (each claude session
                     talks to Claude models)
```

Three external systems: the GCP devbox (compute), Twingate (network access), Discord (UI). Everything else lives inside the devbox.

---

## C4 — Level 2: Containers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            Laptop (macOS)                                │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Twingate    │  │   Mutagen    │  │  ~/dev (git) │  │   tmux +     │ │
│  │  client      │  │  daemon      │  │  clones, no  │  │   ssh        │ │
│  │              │  │  (two-way-   │  │  sync        │  │              │ │
│  │              │  │  resolved)   │  │              │  │              │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │ tunnel          │ SSH (Twingate)  │                 │ SSH     │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────┘
          │                 │                 │                 │
          │                 │                 │                 │
┌─────────┼─────────────────┼─────────────────┼─────────────────┼─────────┐
│         ▼                 ▼                 ▼                 ▼          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                       GCP devbox (Debian)                       │    │
│  │                                                                 │    │
│  │  ┌───────────────┐         ┌───────────────────────┐            │    │
│  │  │ sshd over     │◄────────┤ tmux (persistent)     │            │    │
│  │  │ Twingate      │         │                       │            │    │
│  │  └───────────────┘         │  pane: claude session │ ─── stdio ─┼─►  │
│  │                            │  pane: claude session │     MCP    │    │
│  │  ┌───────────────┐         │  pane: claude session │            │    │
│  │  │ Mutagen agent │ ◄─────► │                       │            │    │
│  │  │ ↔ state dirs  │  two-   │  each `dclaude`       │            │    │
│  │  │   (no repos)  │  way    │   script loads the    │            │    │
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

## C4 — Level 3: Inside the devbox

```
┌────────────────────────────────────────────────────────────────────────┐
│                      GCP devbox                                         │
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
│ │     control.ts   DM command parsing (list/status/kill/restart)  │    │
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
| **GCP devbox** | external | Hosts the sessions and the daemon; company-provisioned, reached only over Twingate | ssh alias `devbox` in `~/.ssh/config` |
| **Twingate** | laptop | ZTNA tunnel to the devbox; ssh and Mutagen ride it, the phone uses Discord directly | Mutagen sessions pause while it is down |
| **OpenSSH** | devbox | Shell, file transfer, Mutagen agent | `ssh devbox`, `scp`, `rsync` |
| **Mutagen** | laptop daemon + devbox agent | Continuous bi-directional sync of state dirs (`two-way-resolved`, laptop is alpha and wins every conflict): transcripts, doit, vault, per-repo `.giantmem`. Repos never sync; they are git clones on both machines. | `scripts/mutagen-sync-state.sh`, `scripts/mutagen-sync-giantmem.sh` |
| **GNU stow** | devbox (and laptop) | Symlink-tree manager — turns `~/dev/claude-code-config` into `~/.claude` | `install.sh` runs it |
| **GNU bash + bun + node** | devbox | Runtimes for daemon (bun), hooks (node) | systemd + bunshell |
| **discord-daemon** | devbox systemd | Single Discord gateway, multi-session routing | This repo's `discord-daemon/` |
| **session-mcp** | devbox, per-claude | Stdio MCP server, HTTP client of daemon | This repo's `session-mcp/` |
| **Claude Code CLI** | devbox (per pane) | The AI agent | `claude --dangerously-load-development-channels server:discord` |
| **Discord bot (`BG-CLC`)** | external | UI surface for chat + control | Channel threads = chat, DM = control |
| **systemd** | devbox | Daemon supervision | `discord-daemon.service` |
| **journalctl** | devbox | Daemon logs | `sudo journalctl -u discord-daemon -f` |

---

## Nested tmux

**Current setup — likely to change.** devbox-side tmux is how sessions survive ssh disconnects today. The shape of that may change (single-pane-per-window, drop devbox tmux for screen, or skip it entirely for users who don't want nesting). Documented here so the friction is visible:

| Layer | Leader | Notes |
|---|---|---|
| Local tmux | `C-a` | per user's local config |
| devbox tmux | `C-b` (default) | set explicitly in `~/.tmux.conf` on the devbox; red status bar tagged `devbox` |

Distinct prefixes mean keys for the outer tmux don't accidentally fire on the inner one. Users not already on tmux will still find nested-tmux confusing — open ergonomics question.

---

## Security boundaries

| Boundary | Mechanism |
|---|---|
| Network | No public ingress on the devbox; everything arrives over Twingate. |
| Daemon HTTP | Binds `127.0.0.1:7777`; sessions on the box use loopback, the laptop an ssh port-forward. |
| Daemon auth | `x-daemon-token` header, constant-time compare. Token in `.env` chmod 600. |
| Discord access | `access.json` allowlist of Discord user IDs. Bot ignores messages from non-allowlisted senders. |
| Bot pairing | `/discord:access pair <code>` skill; codes expire 1h; 3 max concurrent. |
| chat_id authorization | Session can only act on its own `threadId`. Cross-session calls return 403. |
| File send sandbox | `assertSendable` blocks sending daemon state files via `reply`. |
| SSH | Key auth only, over Twingate; agent forwarding from the laptop, the devbox's own key for unattended pushes. |

---

## Failure modes + behaviors

| Event | What happens |
|---|---|
| Laptop closes | SSH/mosh sessions disconnect. devbox tmux + claude + daemon keep running. Phone Discord still works. |
| Reopen laptop | `cvps` from the repo dir (or `ssh devbox; tmux attach`) → exact prior state. |
| Daemon crashes | systemd restarts (Restart=always, 5s). Sessions reconnect SSE on backoff. |
| Discord gateway drops | discord.js auto-reconnects. SessionsMC keep heartbeating. |
| Claude session crashes | Heartbeat stops. After 90s daemon marks session dormant + archives its thread (thread mapping retained — next `dclaude` in same cwd reattaches). |
| Claude session ended normally + resumed (`claude --resume`) | Same cwd → same `session_id` → daemon reuses existing thread. Archive auto-clears on first outbound send. |
| devbox reboots | systemd starts daemon. Sessions need manual restart in tmux. Mutagen reconnects. |
| Mutagen network drop | Reconnects automatically. Edits queued. No data loss unless both sides edited the same file meanwhile (next row). |
| Both sides edit same file | two-way-resolved keeps the laptop's (alpha) copy whatever the mtimes; the devbox edit is overwritten. Avoid simultaneous editing in same file from both hosts, and edits on both while Twingate is down. |
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
  settings.local.json             devbox overlay candidate (gitignored)
  channels/discord/               daemon state (NOT in stow source)
    .env                          bot token, daemon token
    access.json                   user allowlist
```

### Devbox

```
<bridge>/                         bind mount of $HOME at the laptop's home path (BRIDGE in setup-vps.sh)
  dev/                            git clones laid out like the laptop (devbox-clone-repos.sh)
    claude-code-config/           clone; bootstrap-vps.sh fast-forwards it
      discord-daemon/             daemon source (the unit runs it from here)
      session-mcp/                MCP source
      scripts/dclaude             linked into ~/.local/bin
    giant-tooling/                rsync'd; giantmem binary cross-built on the laptop
  .claude/                        stowed from dev/claude-code-config
    projects/                     transcripts, mutagen session claude-projects
    channels/discord/             daemon state
      .env                        DISCORD_BOT_TOKEN, DISCORD_SESSIONS_CHANNEL_ID, DAEMON_TOKEN, DAEMON_BIND_HOST, DAEMON_HOME_ROOT
      access.json
  .claude-team/ .claude-ent/      credentials slots (.credentials.json each)
  .claude-devbox.sh               PATH, tokens, aliases; sourced by .profile and .bashrc
  .local/share/nvim/doit/         doit lists, mutagen session doit
  .local/bin/{claude,giantmem,dclaude,gh,glab}
  .config/systemd/user/           discord-daemon, giantmemd, giantmem-ingest.{service,timer}
```
