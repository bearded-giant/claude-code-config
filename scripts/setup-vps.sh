#!/usr/bin/env bash
# Idempotent VPS bootstrap. Runs ON the VPS, expects:
#   - ~/dev/claude-code-config/   (code present — rsync first if needed)
#   - Ubuntu 24.04 or compatible
#   - Run as a sudo-capable non-root user
#
# This script performs everything install-vps.sh + the manual fix-ups we did
# the first time, in one pass. Re-runnable. Skips finished steps.
#
# What it does NOT do:
#   - Provision the VPS (use scripts/provision-hetzner.sh first)
#   - Tailscale join (cloud-init handles it, or run `sudo tailscale up`)
#   - claude /login (interactive — see end of script)
#
# Restore a previous daemon state by setting BACKUP_FILE to an age-encrypted
# tarball that contains the channels/discord tree. AGE_KEY must point at the
# matching private key.
#
# Usage:
#   ssh bryan@claude-vps 'bash -s' < scripts/setup-vps.sh
#
# Or after scp'ing onto the VPS:
#   bash ~/setup-vps.sh

set -euo pipefail

CONFIG_DIR="${CONFIG_DIR:-$HOME/dev/claude-code-config}"
TOOLING_DIR="${TOOLING_DIR:-$HOME/dev/giant-tooling}"
TOOLING_REPO="${TOOLING_REPO:-https://github.com/bearded-giant/giant-tooling.git}"
STATE_DIR="$HOME/.claude/channels/discord"
BACKUP_FILE="${BACKUP_FILE:-}"
AGE_KEY="${AGE_KEY:-$HOME/.config/age/discord-daemon.key}"

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
dim()   { printf '\033[0;90m%s\033[0m\n' "$*"; }
step()  { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }

if [ ! -d "$CONFIG_DIR" ]; then
  red "missing: $CONFIG_DIR"
  red "run from laptop:  rsync -av --exclude=node_modules ~/dev/claude-code-config bryan@<vps>:~/dev/"
  exit 1
fi

# === 1. apt deps ===
step "apt deps"
sudo apt-get update -y
sudo apt-get install -y \
  curl git unzip ca-certificates jq mosh stow \
  python3 python3-pip patch
green "  apt deps ok"

# === 2. Bun runtime ===
step "Bun"
if [ ! -x "$HOME/.bun/bin/bun" ]; then
  curl -fsSL https://bun.sh/install | bash
fi
"$HOME/.bun/bin/bun" --version
green "  bun ok"

# === 3. /Users/bryan bridge + node bridge ===
step "Laptop-path bridges (so stowed configs resolve)"
sudo mkdir -p /Users
[ -L /Users/bryan ] || sudo ln -sfn "$HOME" /Users/bryan
green "  /Users/bryan → $HOME"

# Node 22 LTS via NodeSource — Ubuntu 24.04 ships v18, too old for
# typescript-language-server (requires >=20). Reinstall if current is <20.
NODE_MAJOR_REQ=20
need_node=true
if command -v node >/dev/null; then
  cur="$(node -p 'process.versions.node.split(".")[0]')"
  [ "$cur" -ge "$NODE_MAJOR_REQ" ] && need_node=false
fi
if $need_node; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
NODE_BIN="$(command -v node)"
mkdir -p "$HOME/.nvm/versions/node/v24.11.1/bin"
ln -sfn "$NODE_BIN" "$HOME/.nvm/versions/node/v24.11.1/bin/node"
green "  node bridge → $NODE_BIN ($(node --version))"

# === 3b. LSP runtimes for claude-code-config ===
# claude-code-config enables 4 LSP plugins (settings.json):
#   pyright-lsp, typescript-lsp, rust-analyzer-lsp, lua-lsp
# These need their language servers on PATH or the LSP tool no-ops.
# Notes:
#   - rust-analyzer not in Ubuntu 24.04 apt; snap channel beta has it.
#   - typescript-language-server requires node >=20 (handled above).
step "LSP runtimes"
sudo npm install -g --silent pyright typescript-language-server typescript
sudo snap install --classic --beta rust-analyzer
sudo ln -sf /snap/rust-analyzer/current/rust-analyzer /usr/local/bin/rust-analyzer
sudo snap install lua-language-server --classic
green "  pyright + typescript-language-server + rust-analyzer + lua-language-server ok"

# === 4. giant-tooling sibling ===
step "giant-tooling sibling repo"
if [ ! -d "$TOOLING_DIR" ]; then
  git clone "$TOOLING_REPO" "$TOOLING_DIR"
fi
ln -sfn "$TOOLING_DIR/workspace" "$CONFIG_DIR/lib/workspace" 2>/dev/null || true
green "  $TOOLING_DIR ok"

# === 5. State dir + restore (or fresh) ===
step "Daemon state dir"
mkdir -p "$STATE_DIR/inbox" "$STATE_DIR/approved"
chmod 700 "$STATE_DIR"

if [ -n "$BACKUP_FILE" ]; then
  if [ ! -r "$BACKUP_FILE" ]; then red "  BACKUP_FILE not readable: $BACKUP_FILE"; exit 1; fi
  if [ ! -r "$AGE_KEY" ]; then red "  AGE_KEY not readable: $AGE_KEY"; exit 1; fi
  command -v age >/dev/null || { red "  install age first (apt install age) — OR run from laptop with AGE pipe"; exit 1; }
  age -d -i "$AGE_KEY" < "$BACKUP_FILE" | tar -C "$HOME/.claude/channels" -x
  green "  restored from $BACKUP_FILE"
else
  if [ ! -f "$STATE_DIR/.env" ]; then
    cat > "$STATE_DIR/.env" <<EOF
DISCORD_BOT_TOKEN=
DISCORD_SESSIONS_CHANNEL_ID=
DAEMON_TOKEN=$(openssl rand -hex 32)
DAEMON_BIND_HOST=0.0.0.0
DAEMON_BIND_PORT=7777
EOF
    chmod 600 "$STATE_DIR/.env"
    dim "  fresh .env created — fill DISCORD_BOT_TOKEN + DISCORD_SESSIONS_CHANNEL_ID"
  else
    dim "  .env exists, untouched"
  fi
  if [ ! -f "$STATE_DIR/access.json" ]; then
    cat > "$STATE_DIR/access.json" <<EOF
{
  "dmPolicy": "allowlist",
  "allowFrom": [],
  "groups": {},
  "pending": {}
}
EOF
    chmod 600 "$STATE_DIR/access.json"
    dim "  fresh access.json — add your Discord user ID to allowFrom"
  else
    dim "  access.json exists, untouched"
  fi
fi

# === 6. Install daemon + session-mcp deps ===
step "Bun install for daemon + session-mcp"
( cd "$CONFIG_DIR/discord-daemon" && "$HOME/.bun/bin/bun" install --production ) | tail -3
( cd "$CONFIG_DIR/session-mcp"    && "$HOME/.bun/bin/bun" install --production ) | tail -3
green "  deps installed"

# === 7. systemd unit ===
step "systemd unit"
SVC_SRC="$CONFIG_DIR/discord-daemon/systemd/discord-daemon.service"
if [ ! -f "$SVC_SRC" ]; then red "  missing unit file: $SVC_SRC"; exit 1; fi
# Patch WorkingDirectory to the stowed-path layout
sudo sed "s|/home/bryan/discord-daemon|$CONFIG_DIR/discord-daemon|g; s|/home/bryan|$HOME|g" "$SVC_SRC" \
  | sudo tee /etc/systemd/system/discord-daemon.service >/dev/null
sudo systemctl daemon-reload
green "  unit installed"

# === 8. Stow personal claude config ===
step "Stow ~/.claude"
mkdir -p "$HOME/.claude"
if [ ! -L "$HOME/.claude" ]; then
  ( cd "$(dirname "$CONFIG_DIR")" && stow --restow -t "$HOME/.claude" "$(basename "$CONFIG_DIR")" ) 2>&1 | grep -v "^$" || true
fi
# settings.local.json overlay
TOKEN=$(grep DAEMON_TOKEN "$STATE_DIR/.env" | cut -d= -f2)
cat > "$HOME/.claude/settings.local.json" <<EOF
{
  "enabledPlugins": {
    "discord@claude-plugins-official": false
  },
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
EOF
chmod 600 "$HOME/.claude/settings.local.json"
green "  stow + settings.local.json ok"

# === 9. Claude CLI ===
step "Claude Code CLI"
if [ ! -x "$HOME/.local/bin/claude" ]; then
  curl -fsSL https://claude.ai/install.sh | bash
fi
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc" ;;
esac
"$HOME/.local/bin/claude" --version
green "  claude installed"

# === 10. Shell env exports ===
step "Shell env (bashrc additions)"
RC="$HOME/.bashrc"
add_export() {
  local line="$1"
  grep -qxF "$line" "$RC" || echo "$line" >> "$RC"
}
add_export "export PATH=\"\$HOME/.local/bin:\$PATH\""
add_export "export GIANT_TOOLING_DIR=\"$TOOLING_DIR\""
add_export "[ -f \"\$GIANT_TOOLING_DIR/workspace/workspace-lib.sh\" ] && source \"\$GIANT_TOOLING_DIR/workspace/workspace-lib.sh\""
add_export "export DISCORD_DAEMON_TOKEN=$TOKEN"
add_export "export DISCORD_DAEMON_URL=http://127.0.0.1:7777"
# claude wrapper: launches w/ Discord channel wired up. Separate name so plain
# `claude` stays usable for non-Discord work.
add_export "dclaude() { claude --dangerously-load-development-channels server:discord --dangerously-skip-permissions \"\$@\"; }"
# one-shot exit: detaches VPS tmux (so claude keeps running) then exits ssh.
add_export "alias bye='tmux detach 2>/dev/null; exit'"
green "  bashrc updated"

# === 10b. tmux config ===
# VPS tmux uses C-b (default). Local convention is C-a → no leader collision
# when nesting local tmux + VPS tmux. Red status bar makes the layer obvious.
step "tmux.conf"
if [ ! -f "$HOME/.tmux.conf" ]; then
  cat > "$HOME/.tmux.conf" <<'TMUX_EOF'
unbind C-a
set -g prefix C-b
bind C-b send-prefix

set -g status-bg colour52
set -g status-fg white
set -g status-left "#[bg=colour88,fg=white,bold] VPS #[default] "

set -g mouse on
set -g history-limit 50000
set -g base-index 1
setw -g pane-base-index 1

# vi-mode in copy-mode
setw -g mode-keys vi
# OSC52: emit clipboard escape so outer (laptop) tmux forwards to terminal.
set -s set-clipboard on
TMUX_EOF
  green "  ~/.tmux.conf written"
else
  green "  ~/.tmux.conf exists, leaving alone"
fi

# === 11. Start daemon ===
step "Start discord-daemon"
sudo systemctl enable --now discord-daemon
sleep 2
if sudo systemctl is-active discord-daemon >/dev/null; then
  green "  discord-daemon active"
  sudo journalctl -u discord-daemon -n 8 --no-pager | grep -E "daemon:" | grep -v Deprecation | tail -5
else
  red "  discord-daemon failed to start"
  sudo journalctl -u discord-daemon -n 20 --no-pager
  exit 1
fi

# === 12. Apply discord plugin patch (if plugin present) ===
step "Discord plugin patch (idempotent)"
if [ -f "$CONFIG_DIR/scripts/apply-discord-patch.sh" ]; then
  bash "$CONFIG_DIR/scripts/apply-discord-patch.sh" || dim "  patch skipped (plugin not yet cached)"
fi

# === 13. Register discord MCP for the user ===
step "claude mcp add discord (user scope)"
if "$HOME/.local/bin/claude" mcp list 2>&1 | grep -q "^discord:"; then
  dim "  discord MCP already registered"
else
  "$HOME/.local/bin/claude" mcp add discord "$HOME/.bun/bin/bun" \
    --scope user \
    -e DISCORD_DAEMON_URL=http://127.0.0.1:7777 \
    -e DISCORD_DAEMON_TOKEN="$TOKEN" \
    -- run "$CONFIG_DIR/session-mcp/src/server.ts"
fi
"$HOME/.local/bin/claude" mcp list 2>&1 | head -5

# === Done ===
cat <<EOF

$(green "=== setup-vps.sh complete ===")

Next:
  1. SSH in interactively: ssh bryan@$(hostname)
  2. claude              # follow /login URL in laptop browser
  3. tmux new -s main; cd ~/dev/test; claude --dangerously-load-development-channels server:discord
  4. DM the bot — try 'list'

Verify:
  curl -H "x-daemon-token: $TOKEN" http://127.0.0.1:7777/health
  curl http://127.0.0.1:7777/metrics | head -10
  sudo journalctl -u discord-daemon -f

State files (back these up):
  $STATE_DIR/.env
  $STATE_DIR/access.json
  $STATE_DIR/sessions.json
EOF
