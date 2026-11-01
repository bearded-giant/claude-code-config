#!/usr/bin/env bash
# Idempotent devbox bootstrap. Runs ON the box (Debian 13) as the sudo-capable
# login user. scripts/bootstrap-vps.sh drives it from the laptop and rsyncs
# the code first. Expects:
#   ~/dev/claude-code-config/    (rsynced)
#   ~/dev/giant-tooling/         (rsynced)
#   ~/dev/lua/do-it.nvim/        (rsynced, doit MCP)
#   ~/.local/bin/giantmem        (cross-built on the laptop, scp'd)
#
# Env knobs:
#   SESSIONS_CHANNEL_ID  Discord channel that holds session threads
#   BACKUP_FILE/AGE_KEY  restore an age-encrypted daemon state tarball
#   SKIP_EMBED=1         skip the sentence-transformers venv (torch CPU, ~2 GB)
#   SKIP_LSP=1           skip pyright/tsserver/rust-analyzer/lua-language-server
#
# Usage:
#   ssh devbox 'SESSIONS_CHANNEL_ID=... bash -s' < scripts/setup-vps.sh

set -euo pipefail

# laptop home. stowed hooks, config/repos.csv, ~/.claude/projects slugs and
# giantmem path keys all hold /Users/bryan/..., so the box answers to it too.
BRIDGE=/Users/bryan
CONFIG_DIR="$BRIDGE/dev/claude-code-config"
TOOLING_DIR="$BRIDGE/dev/giant-tooling"
DOIT_DIR="$BRIDGE/dev/lua/do-it.nvim"
STATE_DIR="$HOME/.claude/channels/discord"
VENV="$HOME/.venvs/giant-ai"
BIN="$HOME/.local/bin"
SESSIONS_CHANNEL_ID="${SESSIONS_CHANNEL_ID:-1507722242551971870}"
BACKUP_FILE="${BACKUP_FILE:-}"
AGE_KEY="${AGE_KEY:-$HOME/.config/age/discord-daemon.key}"

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
dim()   { printf '\033[0;90m%s\033[0m\n' "$*"; }
step()  { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }

step "Path bridge $BRIDGE -> $HOME"
sudo mkdir -p "$(dirname "$BRIDGE")"
[ -L "$BRIDGE" ] || sudo ln -sfn "$HOME" "$BRIDGE"
green "  $(readlink -f "$BRIDGE")"

for d in "$CONFIG_DIR" "$TOOLING_DIR" "$DOIT_DIR"; do
  [ -d "$d" ] || { red "missing: $d (run scripts/bootstrap-vps.sh from the laptop)"; exit 1; }
done
[ -d "$BRIDGE/dotfiles/shell" ] || dim "no $BRIDGE/dotfiles/shell: laptop aliases and .creds.secret not sourced"

step "apt deps"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  curl git unzip ca-certificates jq stow patch rsync ripgrep sqlite3 tmux openssl \
  python3 python3-venv python3-pip nodejs npm >/dev/null
green "  apt ok (node $(node --version))"

step "systemd user services survive logout, journal readable"
sudo loginctl enable-linger "$USER"
id -nG | tr " " "\n" | grep -qx systemd-journal || sudo usermod -aG systemd-journal "$USER"
green "  linger on for $USER; journalctl --user works from the next login"

step "Bun"
[ -x "$HOME/.bun/bin/bun" ] || curl -fsSL https://bun.sh/install | bash >/dev/null
green "  bun $("$HOME/.bun/bin/bun" --version)"

# settings.json pins the laptop's nvm node for the doit MCP
step "node shim for settings.json"
mkdir -p "$HOME/.nvm/versions/node/v24.11.1/bin"
ln -sfn "$(command -v node)" "$HOME/.nvm/versions/node/v24.11.1/bin/node"
green "  ~/.nvm/versions/node/v24.11.1/bin/node -> $(command -v node)"

if [ "${SKIP_LSP:-0}" != "1" ]; then
  step "LSP runtimes (settings.json enables pyright, typescript, rust-analyzer, lua)"
  mkdir -p "$BIN"
  npm install -g --silent --prefix "$HOME/.local" pyright typescript-language-server typescript
  if ! [ -x "$HOME/.cargo/bin/rustup" ]; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable >/dev/null
  fi
  "$HOME/.cargo/bin/rustup" component add rust-analyzer >/dev/null 2>&1 || true
  LLS_VER=3.18.2
  if [ ! -x "$HOME/.local/lua-language-server/bin/lua-language-server" ]; then
    mkdir -p "$HOME/.local/lua-language-server"
    curl -fsSL "https://github.com/LuaLS/lua-language-server/releases/download/${LLS_VER}/lua-language-server-${LLS_VER}-linux-x64.tar.gz" \
      | tar -xz -C "$HOME/.local/lua-language-server"
  fi
  ln -sf "$HOME/.local/lua-language-server/bin/lua-language-server" "$BIN/lua-language-server"
  green "  pyright, typescript-language-server, rust-analyzer, lua-language-server"
fi

step "Claude Code CLI"
[ -x "$BIN/claude" ] || curl -fsSL https://claude.ai/install.sh | bash >/dev/null
green "  $("$BIN/claude" --version)"

step "gh + glab (user-space)"
install_release_bin() {
  local name="$1" url="$2" tmp
  tmp=$(mktemp -d)
  curl -fsSL "$url" -o "$tmp/pkg"
  case "$url" in
    *.tar.gz) tar -xzf "$tmp/pkg" -C "$tmp" && find "$tmp" -type f -name "$name" -perm -u+x -exec install -m 0755 {} "$BIN/$name" \; ;;
    *.deb)    dpkg-deb -x "$tmp/pkg" "$tmp/x" && install -m 0755 "$tmp/x/usr/bin/$name" "$BIN/$name" ;;
  esac
  rm -rf "$tmp"
}
if ! [ -x "$BIN/gh" ]; then
  GH_VER=$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest | jq -r .tag_name | sed 's/^v//')
  install_release_bin gh "https://github.com/cli/cli/releases/download/v${GH_VER}/gh_${GH_VER}_linux_amd64.tar.gz"
fi
if ! [ -x "$BIN/glab" ]; then
  GLAB_VER=$(curl -fsSL "https://gitlab.com/api/v4/projects/gitlab-org%2Fcli/releases?per_page=1" | jq -r '.[0].tag_name' | sed 's/^v//')
  install_release_bin glab "https://gitlab.com/gitlab-org/cli/-/releases/v${GLAB_VER}/downloads/glab_${GLAB_VER}_linux_amd64.deb"
fi
green "  $("$BIN/gh" --version | head -1), $("$BIN/glab" --version | head -1)"

step "giantmem"
if [ -x "$BIN/giantmem" ]; then
  green "  $("$BIN/giantmem" version | head -1)"
else
  red "  ~/.local/bin/giantmem missing; bootstrap-vps.sh cross-builds and scp's it"
fi
if [ "${SKIP_EMBED:-0}" != "1" ]; then
  if ! "$VENV/bin/python3" -c 'import sentence_transformers' 2>/dev/null; then
    dim "  building embedder venv at $VENV (torch cpu + sentence-transformers)"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q torch --index-url https://download.pytorch.org/whl/cpu
    "$VENV/bin/pip" install -q sentence-transformers
  fi
  green "  embedder venv ok: $VENV"
fi

step "install.sh (stow ~/.claude, settings merge, ccmd)"
mkdir -p "$HOME/.claude"
export PATH="$BIN:$PATH"
bash "$CONFIG_DIR/install.sh" --tooling-dir "$TOOLING_DIR"
cat > "$HOME/.claude/settings.local.json" <<'JSON'
{
  "enabledPlugins": {
    "discord@claude-plugins-official": false
  },
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
JSON
chmod 600 "$HOME/.claude/settings.local.json"
green "  stowed + settings.local.json"

step "doit MCP deps"
( cd "$DOIT_DIR/mcp" && npm install --silent --omit=dev >/dev/null 2>&1 ) || dim "  npm install in do-it.nvim/mcp failed; node_modules may already be in place"
green "  $DOIT_DIR/mcp"

step "Daemon state dir"
mkdir -p "$STATE_DIR/inbox" "$STATE_DIR/approved"
chmod 700 "$STATE_DIR"
if [ -n "$BACKUP_FILE" ]; then
  [ -r "$BACKUP_FILE" ] || { red "  BACKUP_FILE not readable: $BACKUP_FILE"; exit 1; }
  [ -r "$AGE_KEY" ] || { red "  AGE_KEY not readable: $AGE_KEY"; exit 1; }
  command -v age >/dev/null || sudo apt-get install -y -qq age >/dev/null
  age -d -i "$AGE_KEY" < "$BACKUP_FILE" | tar -C "$HOME/.claude/channels" -x
  green "  restored from $BACKUP_FILE"
fi
touch "$STATE_DIR/.env"; chmod 600 "$STATE_DIR/.env"
ensure_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$STATE_DIR/.env"; then
    if [ -n "$val" ] && [ -z "$(grep "^${key}=" "$STATE_DIR/.env" | cut -d= -f2-)" ]; then
      sed -i "s|^${key}=.*|${key}=${val}|" "$STATE_DIR/.env"
    fi
  else
    echo "${key}=${val}" >> "$STATE_DIR/.env"
  fi
}
ensure_env DISCORD_BOT_TOKEN ""
ensure_env DISCORD_SESSIONS_CHANNEL_ID "$SESSIONS_CHANNEL_ID"
ensure_env DAEMON_TOKEN "$(openssl rand -hex 32)"
ensure_env DAEMON_BIND_HOST 127.0.0.1
ensure_env DAEMON_BIND_PORT 7777
if [ ! -f "$STATE_DIR/access.json" ]; then
  printf '{\n  "dmPolicy": "allowlist",\n  "allowFrom": [],\n  "groups": {},\n  "pending": {}\n}\n' > "$STATE_DIR/access.json"
  chmod 600 "$STATE_DIR/access.json"
  dim "  fresh access.json: add your Discord user id to allowFrom"
fi
TOKEN=$(grep '^DAEMON_TOKEN=' "$STATE_DIR/.env" | cut -d= -f2-)
BOT_TOKEN=$(grep '^DISCORD_BOT_TOKEN=' "$STATE_DIR/.env" | cut -d= -f2-)
CHANNEL=$(grep '^DISCORD_SESSIONS_CHANNEL_ID=' "$STATE_DIR/.env" | cut -d= -f2-)
green "  $STATE_DIR/.env (bot token: $([ -n "$BOT_TOKEN" ] && echo set || echo EMPTY), channel: ${CHANNEL:-EMPTY})"

step "Bun deps for daemon + session-mcp"
( cd "$CONFIG_DIR/discord-daemon" && "$HOME/.bun/bin/bun" install --production 2>&1 | tail -1 )
( cd "$CONFIG_DIR/session-mcp"    && "$HOME/.bun/bin/bun" install --production 2>&1 | tail -1 )

step "systemd user unit"
mkdir -p "$HOME/.config/systemd/user"
install -m 0644 "$CONFIG_DIR/discord-daemon/systemd/discord-daemon.service" "$HOME/.config/systemd/user/discord-daemon.service"
systemctl --user daemon-reload
green "  ~/.config/systemd/user/discord-daemon.service"

step "Shell env"
DOTFILES="$BRIDGE/dotfiles"
[ -f "$DOTFILES/shell/.recharge-aliases" ] && ln -sfn "$DOTFILES/shell/.recharge-aliases" "$HOME/.recharge-aliases"
cat > "$HOME/.claude-devbox.sh" <<ENV
# sourced from ~/.profile (login, non-interactive: tmux bash -lc) and ~/.bashrc
export PATH="\$HOME/.local/bin:\$HOME/.bun/bin:\$HOME/.cargo/bin:\$PATH"
export GIANT_TOOLING_DIR="$TOOLING_DIR"
[ -f "\$GIANT_TOOLING_DIR/workspace/workspace-lib.sh" ] && source "\$GIANT_TOOLING_DIR/workspace/workspace-lib.sh"
export GIANTMEM_EMBED_PYTHON="$VENV/bin/python3"
export DISCORD_DAEMON_URL=http://127.0.0.1:7777
export DISCORD_DAEMON_TOKEN=$TOKEN
[ -f "$DOTFILES/.creds.secret" ] && source "$DOTFILES/.creds.secret"
[ -f "$DOTFILES/shell/.bash_aliases" ] && source "$DOTFILES/shell/.bash_aliases"
# worktree prefix functions (ccw, few, ...) so sessions open repo worktrees the same way as on the laptop
for __wt in "$DOTFILES"/shell/scripts/worktrees/wt-*.sh; do [ -f "\$__wt" ] && source "\$__wt"; done 2>/dev/null; unset __wt
# claude must see the OAuth slot, not the API key from .creds.secret (remote-control needs claude.ai login);
# these override the laptop aliases sourced above
alias claude='env -u ANTHROPIC_API_KEY DEBUG= claude'
alias claude-team='env -u ANTHROPIC_API_KEY CLAUDE_SECURESTORAGE_CONFIG_DIR=\$HOME/.claude-team claude'
alias claude-ent='env -u ANTHROPIC_API_KEY CLAUDE_SECURESTORAGE_CONFIG_DIR=\$HOME/.claude-ent claude'
alias clc='claude-team'
alias clce='claude-ent'
dclaude() { env -u ANTHROPIC_API_KEY claude --dangerously-load-development-channels server:discord --dangerously-skip-permissions "\$@"; }
alias bye='tmux detach 2>/dev/null; exit'
ENV
chmod 600 "$HOME/.claude-devbox.sh"
for rc in "$HOME/.profile" "$HOME/.bashrc"; do
  grep -q 'claude-devbox.sh' "$rc" 2>/dev/null || printf '\n[ -f "$HOME/.claude-devbox.sh" ] && . "$HOME/.claude-devbox.sh"\n' >> "$rc"
done
# GitLab over https with the token from .creds.secret: no agent needed in daemon-started sessions
git config --global credential."https://gitlab.rechargeapps.net".helper '!f() { echo username=oauth2; echo "password=$GITLAB_TOKEN"; }; f'
green "  ~/.claude-devbox.sh sourced from .profile and .bashrc; gitlab https credential helper set"

step "tmux.conf"
if [ ! -f "$HOME/.tmux.conf" ]; then
  cat > "$HOME/.tmux.conf" <<'TMUX'
unbind C-a
set -g prefix C-b
bind C-b send-prefix
set -g status-bg colour52
set -g status-fg white
set -g status-left "#[bg=colour88,fg=white,bold] DEVBOX #[default] "
set -g mouse on
set -g history-limit 50000
set -g base-index 1
setw -g pane-base-index 1
setw -g mode-keys vi
set -s set-clipboard on
TMUX
  green "  ~/.tmux.conf written (C-b prefix, red bar: nests under the laptop's C-a)"
else
  dim "  ~/.tmux.conf exists, untouched"
fi

step "ssh key for git"
mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"
[ -f "$HOME/.ssh/id_ed25519" ] || ssh-keygen -q -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" -C "devbox-$(hostname)"
for h in gitlab.rechargeapps.net github.com; do
  grep -q "^$h " "$HOME/.ssh/known_hosts" 2>/dev/null || ssh-keyscan -H "$h" >> "$HOME/.ssh/known_hosts" 2>/dev/null
done
green "  $(cat "$HOME/.ssh/id_ed25519.pub")"

step "claude mcp add discord (user scope)"
if "$BIN/claude" mcp list 2>/dev/null | grep -q '^discord'; then
  dim "  already registered"
else
  "$BIN/claude" mcp add discord "$HOME/.bun/bin/bun" --scope user \
    -e DISCORD_DAEMON_URL=http://127.0.0.1:7777 -e DISCORD_DAEMON_TOKEN="$TOKEN" \
    -- run "$CONFIG_DIR/session-mcp/src/server.ts" >/dev/null
  green "  registered"
fi

step "discord-daemon"
if [ -n "$BOT_TOKEN" ] && [ -n "$CHANNEL" ]; then
  systemctl --user enable --now discord-daemon >/dev/null 2>&1
  systemctl --user restart discord-daemon
  sleep 3
  if systemctl --user is-active discord-daemon >/dev/null; then
    green "  active"
    journalctl --user -u discord-daemon -n 6 --no-pager -o cat | grep -E "daemon:" | tail -4 || true
  else
    red "  failed"; journalctl --user -u discord-daemon -n 20 --no-pager -o cat; exit 1
  fi
else
  dim "  not started: fill DISCORD_BOT_TOKEN and DISCORD_SESSIONS_CHANNEL_ID in $STATE_DIR/.env, then: systemctl --user enable --now discord-daemon"
fi

cat <<DONE

$(green "=== setup-vps.sh complete on $(hostname) ===")

Next, over ssh:
  1. CLAUDE_SECURESTORAGE_CONFIG_DIR=\$HOME/.claude-team claude auth login     (rc-team)
     CLAUDE_SECURESTORAGE_CONFIG_DIR=\$HOME/.claude-ent  claude auth login     (rc-inc)
  2. add the key above to GitLab and GitHub, then: gh auth login; glab auth login --hostname gitlab.rechargeapps.net
  3. tmux new -A -s main -c $BRIDGE/dev; dclaude

Verify:
  curl -s -H "x-daemon-token: $TOKEN" http://127.0.0.1:7777/health
  systemctl --user status discord-daemon
  journalctl --user -u discord-daemon -f
DONE
