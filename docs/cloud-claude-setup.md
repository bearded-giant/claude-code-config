# Cloud Claude Setup — VPS + Tailscale + Multi-Session Discord

End-to-end guide for running claude-code on a VPS, mounting it as if local from your laptop/phone, and chatting with 5–6 concurrent sessions via Discord threads.

## Architecture

```
                            Discord
                               │
                               ▼ gateway
                    ┌──────────────────────┐
                    │ discord-daemon (VPS) │
                    │ systemd, always-on   │
                    │ HTTP on tailnet      │
                    └──────────────────────┘
                       ▲          ▲          ▲
                       │ HTTP/SSE │          │
                  ┌────┴────┐ ┌───┴─────┐ ┌──┴──────┐
                  │ claude  │ │ claude  │ │ claude  │
                  │ sess #1 │ │ sess #2 │ │ sess #3 │
                  │ tmux    │ │ tmux    │ │ tmux    │
                  └─────────┘ └─────────┘ └─────────┘
                       VPS (Hetzner CCX33)
```

## 1. Provision the VPS

Hetzner CCX33 (8 vCPU, 32GB, 240GB SSD, ~$40/mo). Ubuntu 24.04. SSH key only.

```bash
ssh root@<ip>
adduser bryan
usermod -aG sudo bryan
mkdir -p /home/bryan/.ssh
cp ~/.ssh/authorized_keys /home/bryan/.ssh/
chown -R bryan:bryan /home/bryan/.ssh
```

## 2. Tailscale

On VPS, laptop, phone:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh --hostname=claude-vps   # VPS only — `--ssh` makes Tailscale handle SSH auth
```

From laptop:

```bash
ssh bryan@claude-vps        # Tailscale resolves it. No public port 22 needed.
tailscale ip -4             # note the VPS tailnet IP — used to bind daemon
```

## 3. Discord bot prep

In the Discord developer portal:

1. Create application + bot. Copy the bot token.
2. In OAuth2 URL generator, scopes: `bot`. Permissions: Send Messages, Read Message History, Manage Threads, Create Public Threads, Add Reactions, Attach Files.
3. Invite to a server you control.
4. Pick a text channel for session threads. Copy its channel ID (Developer Mode → right-click).

## 4. Install the daemon

On the VPS:

```bash
git clone https://github.com/yourname/claude-code-config.git
cd claude-code-config/discord-daemon
sudo bash scripts/install-vps.sh
```

Edit `/home/bryan/.claude/channels/discord/.env`:

```
DISCORD_BOT_TOKEN=MTxxx...
DISCORD_SESSIONS_CHANNEL_ID=1234567890
DAEMON_TOKEN=<random — script pre-fills>
DAEMON_BIND_HOST=100.x.y.z          # tailnet IP — `tailscale ip -4`
DAEMON_BIND_PORT=7777
```

Start it:

```bash
sudo systemctl enable --now discord-daemon
journalctl -u discord-daemon -f
```

DM the bot from Discord → pairing prompt arrives. Use `/discord:access pair <code>` on the VPS (locally `cd discord-daemon && bun ...` — or via SSH).

## 5. Run claude on the VPS

Each session uses session-mcp to talk to the daemon:

```bash
ssh bryan@claude-vps
tmux new -A -s main
cd ~/dev/some-project
DISCORD_DAEMON_URL=http://100.x.y.z:7777 \
DISCORD_DAEMON_TOKEN=<same as daemon .env> \
claude --channels
```

Or bake it into `~/.bashrc`:

```bash
export DISCORD_DAEMON_URL=http://100.x.y.z:7777
export DISCORD_DAEMON_TOKEN=$(grep DAEMON_TOKEN ~/.claude/channels/discord/.env | cut -d= -f2)
```

`session-mcp` registers on launch. The daemon creates a Discord thread named after the cwd. Anyone allowlisted can post in the thread; the session sees it.

### Settings.json snippet

In `~/.claude/settings.json` on the VPS, point the `discord` MCP at session-mcp instead of the bundled plugin:

```json
{
  "mcpServers": {
    "discord": {
      "command": "bun",
      "args": ["run", "/home/bryan/claude-code-config/session-mcp/src/server.ts"],
      "env": {
        "DISCORD_DAEMON_URL": "http://100.x.y.z:7777"
      }
    }
  }
}
```

(Token comes from the daemon's env file if you `EnvironmentFile=` it, or export from `~/.bashrc`.)

## 6. File sync with Mutagen (optional)

VPS is source of truth. Laptop keeps a live mirror. Edit anywhere.

Install Mutagen on laptop (`brew install mutagen-io/mutagen/mutagen`) and VPS (`mutagen-agent` auto-installs over SSH on first sync).

```bash
mutagen sync create --name=dev \
  ~/dev bryan@claude-vps:/home/bryan/dev \
  --ignore-vcs \
  --ignore="node_modules,.venv,target,dist,build,.next"
mutagen sync monitor dev
```

Pause / resume:

```bash
mutagen sync pause dev
mutagen sync resume dev
```

Conflicts (rare if you don't write the same file from both sides simultaneously) park in `.mutagen-conflict-*` files; resolve and `mutagen sync flush dev`.

## 7. Editor over SSH

- **VS Code / Cursor:** Remote-SSH extension. Host = `claude-vps`. Opens `~/dev/...` as if local.
- **nvim:** `mosh claude-vps -- tmux attach -t main` and use nvim inside the VPS tmux.

## 8. Phone access

- **Termius / Blink** for SSH/mosh.
- **Discord mobile** for chatting with sessions — that's the whole point. Close laptop, monitor from phone.

## 9. Cost breakdown

| Item | $/mo |
|---|---|
| Hetzner CCX33 | ~40 |
| Tailscale free tier | 0 |
| Discord | 0 |
| Mutagen | 0 |
| **Total** | **~40** |

## 10. Operating notes

- DMs to the bot = control commands only (`list`, `status`, `kill`, `help`). Never routed to a session.
- To talk to a session, post in its thread.
- Sessions auto-archive their thread on shutdown.
- Heartbeat is 30s; sessions go stale after 90s and the daemon archives their thread + drops them.
- `tailscale up --ssh` removes the need to manage SSH keys per device.
- Tailscale ACL can lock the tailnet to just your devices — set in admin console.
