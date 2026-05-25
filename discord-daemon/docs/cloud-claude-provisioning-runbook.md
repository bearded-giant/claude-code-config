# Cloud Claude — Provisioning Runbook

Step-by-step to stand up the cloud claude + multi-session Discord setup. Resume from any step — each is checkpointed.

Companion doc: [`cloud-claude-architecture.md`](cloud-claude-architecture.md) for architecture overview.

---

## Phase 0 — Account prerequisites (do once)

### 0.1 Hetzner Cloud account

1. Sign up: https://www.hetzner.com/cloud
2. Verify email
3. Add payment method (card or PayPal)
4. **Identity verification (passport / driver's license upload)** — Hetzner sometimes holds new accounts pending ID verification, especially first server. Expect 1–24h turnaround. Upload via account settings when prompted.
5. Create a **project** (e.g., `claude-vps`)
6. Inside project: **Security → API tokens → Generate** (Read+Write). Copy token, save to password manager.

### 0.2 hcloud CLI on laptop

```bash
brew install hcloud
hcloud context create claude   # paste API token when prompted
hcloud context list            # verify "claude" is active
```

### 0.3 Local SSH key

Confirm a key exists, or generate one:

```bash
ls ~/.ssh/*.pub
# none? →
ssh-keygen -t ed25519 -C "bryan@laptop"   # accept default path
```

Default path used by provision script: `~/.ssh/id_ed25519.pub`. Override with `SSH_PUBKEY_PATH=...` env if different.

### 0.4 Tailscale account + auth key

1. Sign up: https://tailscale.com (Google/GitHub/email)
2. Install on laptop:
   ```bash
   brew install --cask tailscale         # laptop (GUI app, recommended)
   # OR CLI-only:
   #   brew install tailscale
   #   sudo /opt/homebrew/opt/tailscale/bin/tailscaled install-system-daemon
   #   sudo mkdir -p /etc/resolver && echo -e "nameserver 100.100.100.100\nsearch <your-tailnet>.ts.net" | sudo tee /etc/resolver/ts.net
   ```
   Phone: **not needed**. Discord handles phone↔VPS traffic via Discord's own infrastructure; Tailscale on phone is only useful if you ssh from phone, which this setup does not.
3. Log in on the laptop, accept the connection.
4. Generate pre-auth key for VPS:
   - https://login.tailscale.com/admin/settings/keys
   - Generate auth key: **Reusable: off**, **Ephemeral: off**, **Expiry: 90d**
   - Copy `tskey-auth-...`, save to password manager
5. Optional: lock the tailnet ACL to your own devices only (admin console → Access controls).

### 0.5 Discord bot

1. https://discord.com/developers/applications → New Application → `claude-bot`
2. Bot tab → Reset Token → copy bot token (save to password manager)
3. Privileged Gateway Intents → enable **Message Content Intent**
4. OAuth2 → URL Generator:
   - Scopes: `bot`
   - Permissions: Send Messages, Read Message History, Manage Threads, Create Public Threads, Add Reactions, Attach Files, Embed Links
5. Open generated URL → invite bot to a server you control
6. In Discord: enable Developer Mode (Settings → Advanced)
7. Right-click the channel for session threads → Copy Channel ID. Save it.

**Checkpoint:** by end of Phase 0 you should have, all saved to password manager:
- Hetzner API token (set in `hcloud context`)
- Tailscale auth key (`tskey-auth-...`)
- Discord bot token (`MT...`)
- Discord channel ID for session threads (numeric snowflake)
- SSH keypair on laptop

### 0.6 Local smoke test (no VPS, no Discord)

Validates the daemon + session-mcp HTTP/SSE path before any VPS exists. Uses `DAEMON_DISCORD_MOCK=1` — stubs threads, skips gateway login.

```bash
cd discord-daemon
bun install
./scripts/smoke-test.sh
```

Expect 16 PASS lines + `✅ all smoke checks passed`. Verifies:
- HTTP boot, auth gate (constant-time compare)
- Session register / list / heartbeat / unregister
- SSE inbox stream + hello event
- Mock-mode inbound message injection
- Send / edit / react
- `chat_id` authorization (cross-session calls → 403)
- Thread create + archive logged

If this fails, the deployed setup will fail the same way. Fix here before provisioning.

### 0.7 Local daemon dev-run against real Discord (optional)

Once you have a bot token + channel ID, smoke the real gateway path locally:

```bash
mkdir -p ~/.claude/channels/discord
cat > ~/.claude/channels/discord/.env <<'EOF'
DISCORD_BOT_TOKEN=MTxxx...
DISCORD_SESSIONS_CHANNEL_ID=12345...
DAEMON_TOKEN=$(openssl rand -hex 32)
DAEMON_BIND_HOST=127.0.0.1
DAEMON_BIND_PORT=7777
EOF
chmod 600 ~/.claude/channels/discord/.env

cd discord-daemon && bun run src/server.ts
```

Expect: `daemon: gateway connected as <bot>#XXXX` + `daemon: HTTP listening`.

In another terminal, point a claude session at it:

```bash
export DISCORD_DAEMON_URL=http://127.0.0.1:7777
export DISCORD_DAEMON_TOKEN=$(grep DAEMON_TOKEN ~/.claude/channels/discord/.env | cut -d= -f2)
cd ~/some-project
dclaude   # = claude --dangerously-load-development-channels server:discord --dangerously-skip-permissions
```

A thread should appear in Discord. Pair, post in thread, see claude respond.

Once VPS exists, the same `.env` moves to the VPS. Same code path.

---

## Phase 1 — Provision VPS

### 1.1 Run provisioning script

From the repo root on laptop:

```bash
TAILSCALE_AUTHKEY=tskey-auth-xxxxx \
  ./discord-daemon/scripts/provision-hetzner.sh
```

What it does:
- Uploads SSH key as `${USER}-laptop`
- Creates firewall (SSH+ICMP only — Tailscale carries everything else)
- Creates server `claude-vps` (CCX33, 8 vCPU dedicated / 32GB / 240GB, ~$40/mo)
- cloud-init installs: curl, git, mosh, jq, Tailscale, Bun
- Creates `bryan` user with SSH key
- Disables root SSH
- Joins tailnet if auth key supplied

Override defaults via env:
- `SERVER_LOCATION=ash` (Ashburn VA, default) | `hil` (Hillsboro OR) | `fsn1` (Falkenstein DE)
- `SERVER_TYPE=ccx33` (default) | `ccx23` (4 vCPU/16GB, cheaper)
- `SERVER_NAME=claude-vps` (default)
- `SSH_KEY_NAME=${USER}-laptop` (default)

### 1.2 Verify reachable

```bash
# wait ~60s for cloud-init
ssh bryan@claude-vps          # via Tailscale, if authkey was supplied
# or
ssh bryan@<public-ip>         # from `hcloud server ip claude-vps`
```

If Tailscale not auto-joined:

```bash
ssh bryan@<public-ip>
sudo tailscale up --ssh --hostname=claude-vps
# follow URL in laptop browser to approve
tailscale ip -4               # note this IP
```

**Checkpoint:** `ssh bryan@claude-vps` works from laptop.

---

## Phase 2 — Install daemon

### 2.1 Copy code

From laptop:

```bash
scp -r ~/dev/claude-code-config/discord-daemon bryan@claude-vps:~/
scp -r ~/dev/claude-code-config/session-mcp bryan@claude-vps:~/  # for the VPS's claude sessions
```

### 2.2 Run installer

```bash
ssh bryan@claude-vps
sudo bash ~/discord-daemon/scripts/install-vps.sh
```

The script:
- Installs system deps
- Copies daemon to `/home/bryan/discord-daemon`
- Creates `/home/bryan/.claude/channels/discord/` state dir + `.env`
- Generates random `DAEMON_TOKEN`
- Installs systemd unit (not started yet)

### 2.3 Configure .env

```bash
TAILNET_IP=$(tailscale ip -4)
sudo -u bryan vim /home/bryan/.claude/channels/discord/.env
```

Fill in:

```
DISCORD_BOT_TOKEN=<from Phase 0.5>
DISCORD_SESSIONS_CHANNEL_ID=<from Phase 0.5>
DAEMON_TOKEN=<pre-generated; keep>
DAEMON_BIND_HOST=<TAILNET_IP value>
DAEMON_BIND_PORT=7777
```

Save. Verify perms `chmod 600`.

### 2.4 Start daemon

```bash
sudo systemctl enable --now discord-daemon
sudo systemctl status discord-daemon
journalctl -u discord-daemon -f
```

Expect: `daemon: gateway connected as <bot>#XXXX` and `daemon: HTTP listening on <tailnet-ip>:7777`.

### 2.5 Verify HTTP from laptop

```bash
TOKEN=$(ssh bryan@claude-vps "grep DAEMON_TOKEN /home/bryan/.claude/channels/discord/.env | cut -d= -f2")
curl -H "x-daemon-token: $TOKEN" http://claude-vps:7777/health
# {"ok":true,"sessions":0}
```

**Checkpoint:** daemon running, health endpoint responds from laptop over tailnet.

---

## Phase 3 — Pair Discord user

### 3.1 DM the bot

From Discord (the account that should control sessions) → DM the bot → say `hi`.

Bot replies with pairing code: `Pairing required — run in Claude Code: /discord:access pair abc123`.

### 3.2 Approve on VPS

```bash
ssh bryan@claude-vps
cd ~/.claude
# Run the /discord:access skill manually — it just edits access.json.
# Easiest: hand-edit:
jq --arg id "<your-discord-user-id>" '.allowFrom += [$id] | .pending = {}' \
  channels/discord/access.json > /tmp/a && mv /tmp/a channels/discord/access.json
```

Or if you have claude installed on VPS already (will be after Phase 4):

```bash
claude --print "/discord:access pair abc123"
```

Bot DMs `Paired! DM "help" for commands.`

Confirm: DM `list` to bot → should reply `no active sessions`.

**Checkpoint:** bot accepts your DMs as control commands.

---

## Phase 4 — First claude session

### 4.1 Install claude on VPS

```bash
ssh bryan@claude-vps
curl -fsSL https://claude.ai/install.sh | bash    # or npm path, whichever Anthropic recommends
```

### 4.2 LSP runtimes

`claude-code-config` enables 4 LSP plugins via `settings.json` (pyright-lsp, typescript-lsp, rust-analyzer-lsp, lua-lsp). The language servers themselves are not bundled — install them or the LSP tool silently no-ops.

`setup-vps.sh` step `3b` handles this on fresh provisions. For existing VPS or manual fix:

```bash
sudo npm install -g pyright typescript-language-server typescript
sudo apt-get install -y rust-analyzer
sudo snap install lua-language-server --classic
```

Verify:

```bash
for cmd in pyright typescript-language-server rust-analyzer lua-language-server; do
  command -v "$cmd" || echo "MISSING $cmd"
done
```

### 4.3 settings.json snippet

```bash
mkdir -p ~/.claude
cat >> ~/.claude/settings.json <<'EOF'
{
  "mcpServers": {
    "discord": {
      "command": "/home/bryan/.bun/bin/bun",
      "args": ["run", "/home/bryan/session-mcp/src/server.ts"],
      "env": {
        "DISCORD_DAEMON_URL": "http://127.0.0.1:7777"
      }
    }
  }
}
EOF
```

(Daemon and sessions run on same host → loopback works; tailnet-bind from Phase 2.3 still required for other VPSes or laptop testing.)

### 4.4 Export token in shell

```bash
echo "export DISCORD_DAEMON_TOKEN=$(grep DAEMON_TOKEN ~/.claude/channels/discord/.env | cut -d= -f2)" >> ~/.bashrc
source ~/.bashrc
```

### 4.5 Launch session

```bash
tmux new -s main
cd ~/some-project
dclaude       # alias from setup-vps.sh; expands to claude --dangerously-load-development-channels server:discord --dangerously-skip-permissions
```

Expect: Discord shows new thread named after cwd, with `session <label> online`.

Post in the thread → claude session sees the message → replies in same thread.

**Checkpoint:** one session live, end-to-end.

---

## Phase 5 — Mutagen file sync (optional)

### 5.1 Laptop

```bash
brew install mutagen-io/mutagen/mutagen
# Wrapper script bakes in the right flags + excludes (see Lessons Learned).
# Pass the VPS public IP (NOT tailnet hostname).
./scripts/mutagen-sync-dev.sh "$(hcloud server ip claude-vps)"
mutagen sync monitor dev
```

Mutagen auto-installs its agent on the VPS over SSH on first sync.

### 5.2 Verify

```bash
echo "test" > ~/dev/sync-test.txt
ssh bryan@claude-vps "cat ~/dev/sync-test.txt"   # → test
ssh bryan@claude-vps "echo reverse >> ~/dev/sync-test.txt"
cat ~/dev/sync-test.txt   # → test\nreverse
rm ~/dev/sync-test.txt
```

**Checkpoint:** bidirectional `~/dev` sync working.

---

## Phase 6 — Scale to multiple sessions

Each tmux window/pane = one session. Same flow as Phase 4.4. Different cwd → different thread name.

Test parallelism:

```bash
tmux new -s work
# pane 1
cd ~/dev/foo && dclaude
# split, pane 2
cd ~/dev/bar && dclaude
# split, pane 3
cd ~/dev/baz && dclaude
```

Discord: 3 threads under the sessions channel. DM `list` → 3 sessions.

---

## Phase 7 — Mobile / phone access

- **Tailscale app** running → VPS reachable as `claude-vps`.
- **Termius / Blink Shell / a-Shell** → mosh into VPS for tmux. Reconnects survive network changes.
- **Discord mobile** → chat with sessions via threads.

Typical mobile workflow:
1. Open Discord, post in thread `bg-foo-abc1`: "status?"
2. Session replies in thread.
3. If you want to drive the session interactively, Termius → `mosh claude-vps` → `tmux attach`.

---

## Reference — operational commands

### Daemon logs
```bash
journalctl -u discord-daemon -f
journalctl -u discord-daemon --since "10m ago"
```

### Restart daemon
```bash
sudo systemctl restart discord-daemon
```

### Update daemon code
```bash
# laptop
scp -r ~/dev/claude-code-config/discord-daemon bryan@claude-vps:~/
ssh bryan@claude-vps 'sudo cp -r ~/discord-daemon/. /home/bryan/discord-daemon/ && sudo systemctl restart discord-daemon'
```

### List sessions
```bash
curl -H "x-daemon-token: $DISCORD_DAEMON_TOKEN" http://claude-vps:7777/sessions | jq
```

### Mutagen pause/resume
```bash
mutagen sync pause dev
mutagen sync resume dev
mutagen sync list
```

### Tailscale
```bash
tailscale status
tailscale ping claude-vps
```

---

## Cost summary

| Item | $/mo |
|---|---|
| Hetzner CCX33 | ~40 |
| Tailscale (Free up to 100 devices, 3 users) | 0 |
| Discord | 0 |
| Mutagen | 0 |
| **Total** | **~40** |

---

## Lessons learned from the first run (2026-05-23)

Captured during the real provisioning so the runbook accounts for them. Apply when re-running on a fresh VPS or a new platform.

### Stow 2.3.1 won't create the target dir
Ubuntu 24.04 ships stow 2.3.1. It refuses to stow if `~/.claude` doesn't already exist. `install.sh` does not pre-create it.

Fix:
```bash
mkdir -p ~/.claude
cd ~/dev && stow --restow -t ~/.claude claude-code-config
```

### Daemon must bind 0.0.0.0 for same-host sessions
If `DAEMON_BIND_HOST=<tailnet-ip>`, the daemon doesn't listen on loopback. A claude session-mcp running on the same host can't reach `127.0.0.1:7777`. Override `~/.claude/channels/discord/.env`:

```
DAEMON_BIND_HOST=0.0.0.0
```

Hetzner cloud firewall (configured by `provision-hetzner.sh`) blocks public 7777 → safe. Loopback + tailnet both reachable.

### Tailscale SSH strips file mode bits
`mutagen sync create` fails with `Permission denied` running its uploaded agent. The agent lands chmod 644 because Tailscale's SSH proxy doesn't preserve exec bits during SFTP.

Fix: use the public IP for Mutagen, not the tailnet hostname:
```bash
mutagen sync create --name=dev \
  /Users/bryan/dev bryan@<public-ip>:/home/bryan/dev   # NOT bryan@claude-vps
```

Regular sshd on port 22 preserves modes. Hetzner firewall already allows SSH from anywhere.

### --channels needs `server:` prefix and a dev flag for ad-hoc MCPs
Claude CLI:
```bash
claude --dangerously-load-development-channels server:discord
```
Not `--channels server:discord` alone. The `--channels` flag exists but rejects `server:` entries unless the dev flag is also passed. Both flags take the same `<servers...>` arg — pass it once on the dev flag.

If you registered the channel via a plugin instead of `claude mcp add`, use `plugin:<name>@<marketplace>` and you can drop the dev flag.

### MCP must be registered via `claude mcp add`, not just settings.json
Claude does NOT auto-load `mcpServers` from `~/.claude/settings.json` for the CLI's MCP list. Register explicitly:
```bash
claude mcp add discord /home/bryan/.bun/bin/bun \
  --scope user \
  -e DISCORD_DAEMON_URL=http://127.0.0.1:7777 \
  -e DISCORD_DAEMON_TOKEN=$TOKEN \
  -- run /home/bryan/dev/claude-code-config/session-mcp/src/server.ts
```
This writes `~/.claude.json`. Verify with `claude mcp list`.

### Stowed hooks hardcode laptop paths
The committed `settings.json` references absolute laptop paths (`/Users/bryan/.nvm/versions/node/v24.11.1/bin/node`, `/Users/bryan/.local/bin/giantmem`, etc.). On Linux VPS these fail with `node: not found`.

Quick bridge (no code changes):
```bash
sudo mkdir -p /Users
sudo ln -sfn /home/bryan /Users/bryan
mkdir -p ~/.nvm/versions/node/v24.11.1/bin
ln -sfn /usr/bin/node ~/.nvm/versions/node/v24.11.1/bin/node
```

Long-term: edit `settings.json` to use `$HOME` / PATH-relative commands. Or move host-specific MCPs to `settings.local.json` (gitignored).

### Bot must be added to private channels
`DISCORD_SESSIONS_CHANNEL_ID` pointing to a private channel → thread create fails until the bot is added as a member. Channel settings → Permissions → Add member → pick the bot.

### Restart MCP after access.json edits — usually not, but sometimes
`access.json` is re-read on every gate check, so allowlist additions take effect live. **But** the bundled discord plugin caches some DM channel state in memory; if you've been failing pre-allowlist, a process restart clears that.

```bash
pkill -f 'discord/0.0.4'   # then /mcp in claude
```

### Initial Mutagen sync is slow
With ~80GB raw under `~/dev` (post-excludes ~25-40GB), expect 30-60 min over typical home upload. Sync runs independently of daemon — you can spin up VPS claude sessions for any subtree that's already arrived (`du -sh ~/dev/<repo>` on VPS to confirm).

### Mutagen ignores need more than "node_modules"
Default-ish excludes that should ship with the sync create:

```
node_modules .venv venv __pycache__
target/ dist/ build/ .next/ .nuxt/
*.pyc .DS_Store .mypy_cache .pytest_cache .tox .gradle
plugins/cache/ plugins/marketplaces/ plugins/repos/ plugins/subtask/ plugins/install-counts-cache.json
.giantmem
```

The `plugins/*` excludes matter: claude-code-config has `~/.claude/plugins/cache/` (gitignored) as runtime cache. Both sides regenerate it independently → otherwise hundreds of conflicts on first sync.

### Mutagen symlink mode: use `posix-raw`, not `portable`
Default is `portable` which rejects any symlink whose target is an absolute path. Lots of real-world repos have those:
- Python venvs (`bin/python3 → /opt/homebrew/...`)
- Tooling links (`claude-code-config/lib/workspace → /Users/bryan/dev/giant-tooling/...`)
- Container artifacts (`dbt_packages/shared_macros → /repo/...`)

```bash
mutagen sync create --symlink-mode=posix-raw ...
```

`posix-raw` passes the symlink verbatim. Combined with the `/Users/bryan → /home/bryan` root symlink on the VPS, most laptop-absolute paths inside `~/dev` resolve correctly on the VPS too.

### Sync mirrors code, not runtime
The remote will not behave 1:1 with local right after sync. Per-project on VPS, first time you want to run something:

```bash
cd ~/dev/<project>
# Python:
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
# Node:
bun install     # or npm i, pnpm i
# Rust:
cargo build
```

`venv/`, `node_modules/`, `target/`, `build/`, `dist/` are excluded from sync — recreate them on VPS. After that, source edits propagate live in seconds. Container-only paths (e.g. dbt `/repo/...`, liquibase `/home/tradergt/...`) stay broken outside their containers, same as on laptop.

### Mutagen sync via tailnet hostname doesn't work
Tailscale SSH (`--ssh` on `tailscale up`) strips file mode bits during SFTP transfer. Mutagen's agent uploads chmod 644 → can't execute. Always use **public IP** for Mutagen even though everything else uses tailnet:

```bash
mutagen sync create --name=dev /Users/bryan/dev bryan@<public-ip>:/home/bryan/dev
# NOT bryan@claude-vps
```

Hetzner firewall rule (port 22 open from anywhere by default) already allows it. Tailscale SSH is for interactive shells; regular sshd handles the rest.

---

## Where you left off

Phase 0 blocked on Hetzner passport verification. Pick up at **0.1 step 4** once ID uploaded and account approved. Everything from 0.2 onward is laptop-local prep — can be done in any order before VPS is created.

Pre-VPS work to do offline:
- 0.2 hcloud CLI install (`brew install hcloud`)
- 0.3 SSH key check
- 0.4 Tailscale account + auth key
- 0.5 Discord bot + token + channel ID

Once Hetzner is verified: jump to Phase 1.
