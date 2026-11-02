#!/usr/bin/env bash
# Laptop-side driver: brings the devbox to "claude auth login ready" state.
# rsyncs code -> cross-builds giantmem -> copies the Discord bot token ->
# runs scripts/setup-vps.sh on the box.
#
# Usage:
#   scripts/bootstrap-vps.sh [host] [--channel <discord-channel-id>] [--restore <backup.tar.age>] [--skip-embed] [--skip-lsp]
#
# host defaults to the ssh alias `devbox`. Requires ssh + rsync, and go for the giantmem build.

set -euo pipefail

VPS_HOST=devbox
RESTORE=""; CHANNEL=""; SKIP_EMBED=0; SKIP_LSP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --restore)    RESTORE="$2"; shift 2;;
    --channel)    CHANNEL="$2"; shift 2;;
    --skip-embed) SKIP_EMBED=1; shift;;
    --skip-lsp)   SKIP_LSP=1; shift;;
    -h|--help)    sed -n '2,9p' "$0"; exit 0;;
    -*)           echo "unknown flag: $1"; exit 1;;
    *)            VPS_HOST="$1"; shift;;
  esac
done

CONFIG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEV_DIR="$(dirname "$CONFIG_DIR")"
TOOLING_DIR="${TOOLING_DIR:-$DEV_DIR/giant-tooling}"
DOIT_DIR="${DOIT_DIR:-$DEV_DIR/lua/do-it.nvim}"
LOCAL_STATE="$HOME/.claude/channels/discord"

echo "==> sanity: ssh ${VPS_HOST}"
ssh -o ConnectTimeout=8 "$VPS_HOST" 'echo "    $(hostname) $(. /etc/os-release && echo "$PRETTY_NAME")"'

if [ -x "$CONFIG_DIR/scripts/sync-gitconfig.sh" ]; then
  echo "==> git config -> ${VPS_HOST} (GPG stripped; KEEP_GPG=1 to keep)"
  "$CONFIG_DIR/scripts/sync-gitconfig.sh" "$VPS_HOST" || echo "    (git config sync skipped)"
fi

RSYNC=(rsync -az --delete --exclude=node_modules --exclude=.giantmem --exclude=scratch --exclude=archive
       --exclude='*.jsonl' --exclude='*.db' --exclude='*.db-*' --exclude=.DS_Store)
ssh "$VPS_HOST" 'mkdir -p ~/dev/lua'
# the devbox copy is a git clone and origin/main is the truth; rsync only seeds a box that has no clone yet
if ssh "$VPS_HOST" 'test -d ~/dev/claude-code-config/.git'; then
  if git -C "$CONFIG_DIR" status --porcelain | grep -q .; then
    echo "WARN: laptop claude-code-config has uncommitted changes; the devbox clone follows origin/main"
  fi
  echo "==> claude-code-config: fast-forward the devbox clone"
  ssh "$VPS_HOST" 'bash -lc "cd ~/dev/claude-code-config && git pull --ff-only && git log -1 --format=\"    %h %s\""'
else
  echo "==> rsync claude-code-config -> ${VPS_HOST}:~/dev/ (seed; turn it into a clone of origin afterwards)"
  "${RSYNC[@]}" --exclude='plugins/cache' --exclude='plugins/marketplaces' --exclude='plugins/repos' --exclude='plugins/subtask' --exclude=.git \
    "$CONFIG_DIR/" "$VPS_HOST:dev/claude-code-config/"
fi
echo "==> rsync giant-tooling -> ${VPS_HOST}:~/dev/ (gui excluded)"
"${RSYNC[@]}" --exclude='giantmem/gui' "$TOOLING_DIR/" "$VPS_HOST:dev/giant-tooling/"
echo "==> rsync do-it.nvim -> ${VPS_HOST}:~/dev/lua/"
rsync -az --delete --exclude=.giantmem --exclude=.DS_Store "$DOIT_DIR/" "$VPS_HOST:dev/lua/do-it.nvim/"
DOTFILES="${DOTFILES:-$HOME/dotfiles}"
if [ -d "$DOTFILES/shell" ]; then
  echo "==> rsync dotfiles/shell + .creds.secret -> ${VPS_HOST}:~/dotfiles/"
  ssh "$VPS_HOST" 'mkdir -p ~/dotfiles && chmod 700 ~/dotfiles'
  rsync -az --delete --exclude=.DS_Store --exclude='*.bak' "$DOTFILES/shell/" "$VPS_HOST:dotfiles/shell/"
  [ -f "$DOTFILES/.creds.secret" ] && scp -q "$DOTFILES/.creds.secret" "$VPS_HOST:dotfiles/.creds.secret" && ssh "$VPS_HOST" 'chmod 600 ~/dotfiles/.creds.secret'
fi

if command -v go >/dev/null; then
  echo "==> giantmem: cross-build linux/amd64 -> ${VPS_HOST}:~/.local/bin/giantmem"
  BUILD=$(mktemp -d)
  ( cd "$TOOLING_DIR/giantmem" && \
    V=$(git describe --tags --always --dirty 2>/dev/null || echo dev) && C=$(git rev-parse --short HEAD 2>/dev/null || echo unknown) && \
    GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build \
      -ldflags "-s -w -X github.com/bearded-giant/giant-tooling/giantmem/cmd.Version=$V -X github.com/bearded-giant/giant-tooling/giantmem/cmd.Commit=$C -X github.com/bearded-giant/giant-tooling/giantmem/cmd.BuildDate=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      -o "$BUILD/giantmem" . )
  ssh "$VPS_HOST" 'mkdir -p ~/.local/bin'
  # a running giantmem daemon keeps the binary busy; mv over it instead of writing into it
  scp -q "$BUILD/giantmem" "$VPS_HOST:.local/bin/giantmem.new" && ssh "$VPS_HOST" 'mv -f ~/.local/bin/giantmem.new ~/.local/bin/giantmem'
  rm -rf "$BUILD"
else
  echo "==> go not found on the laptop; giantmem binary not shipped"
fi

echo "==> Discord state: copy bot token + allowlist if the box has none"
ssh "$VPS_HOST" 'mkdir -p ~/.claude/channels/discord && chmod 700 ~/.claude/channels/discord'
for f in .env access.json; do
  if [ -f "$LOCAL_STATE/$f" ] && ! ssh "$VPS_HOST" "test -s ~/.claude/channels/discord/$f"; then
    scp -q "$LOCAL_STATE/$f" "$VPS_HOST:.claude/channels/discord/$f"
    echo "    copied $f"
  fi
done

EXTRA_ENV="SKIP_EMBED=$SKIP_EMBED SKIP_LSP=$SKIP_LSP"
[ -n "$CHANNEL" ] && EXTRA_ENV="$EXTRA_ENV SESSIONS_CHANNEL_ID=$CHANNEL"
if [ -n "$RESTORE" ]; then
  [ -f "$RESTORE" ] || { echo "missing backup: $RESTORE" >&2; exit 1; }
  REMOTE_BACKUP="/tmp/$(basename "$RESTORE")"
  scp -q "$RESTORE" "$VPS_HOST:$REMOTE_BACKUP"
  AGE_KEY="${AGE_KEY:-$HOME/.config/age/discord-daemon.key}"
  if [ -f "$AGE_KEY" ]; then
    scp -q "$AGE_KEY" "$VPS_HOST:/tmp/discord-daemon.key"
    EXTRA_ENV="$EXTRA_ENV BACKUP_FILE=$REMOTE_BACKUP AGE_KEY=/tmp/discord-daemon.key"
  else
    echo "WARN: AGE_KEY not found ($AGE_KEY); restore will fail"
    EXTRA_ENV="$EXTRA_ENV BACKUP_FILE=$REMOTE_BACKUP"
  fi
fi

echo "==> running setup-vps.sh on ${VPS_HOST}"
# shellcheck disable=SC2029
ssh "$VPS_HOST" "$EXTRA_ENV bash -s" < "$CONFIG_DIR/scripts/setup-vps.sh"
