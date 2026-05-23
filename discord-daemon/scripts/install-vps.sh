#!/usr/bin/env bash
# One-shot VPS bootstrap for the Discord multi-session daemon.
# Run on a fresh Ubuntu 24.04 box, as a sudo-capable user.

set -euo pipefail

USERNAME="${SUDO_USER:-$USER}"
HOME_DIR="/home/${USERNAME}"
REPO_URL="${REPO_URL:-https://github.com/yourname/claude-code-config.git}"
REPO_DIR="${HOME_DIR}/claude-code-config"
DAEMON_DIR="${HOME_DIR}/discord-daemon"
STATE_DIR="${HOME_DIR}/.claude/channels/discord"

echo "==> Updating apt"
sudo apt-get update -y
sudo apt-get install -y curl git unzip ca-certificates jq

echo "==> Installing Tailscale"
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
echo "    Run: sudo tailscale up --ssh --hostname=claude-vps"
echo "    (skipped here — needs your tailnet auth interactively)"

echo "==> Installing Bun (as ${USERNAME})"
if [ ! -x "${HOME_DIR}/.bun/bin/bun" ]; then
  sudo -u "${USERNAME}" bash -lc 'curl -fsSL https://bun.sh/install | bash'
fi

echo "==> Cloning repo"
if [ ! -d "${REPO_DIR}" ]; then
  sudo -u "${USERNAME}" git clone "${REPO_URL}" "${REPO_DIR}"
fi

echo "==> Installing daemon"
mkdir -p "${DAEMON_DIR}"
sudo cp -r "${REPO_DIR}/discord-daemon/." "${DAEMON_DIR}/"
sudo chown -R "${USERNAME}:${USERNAME}" "${DAEMON_DIR}"
sudo -u "${USERNAME}" bash -lc "cd ${DAEMON_DIR} && ~/.bun/bin/bun install --production"

echo "==> State dir"
sudo -u "${USERNAME}" mkdir -p "${STATE_DIR}/inbox" "${STATE_DIR}/approved"
sudo -u "${USERNAME}" chmod 700 "${STATE_DIR}"

if [ ! -f "${STATE_DIR}/.env" ]; then
  cat <<EOF | sudo -u "${USERNAME}" tee "${STATE_DIR}/.env" >/dev/null
# Required:
DISCORD_BOT_TOKEN=
DISCORD_SESSIONS_CHANNEL_ID=
DAEMON_TOKEN=$(openssl rand -hex 32)

# Optional (defaults shown):
# DAEMON_BIND_HOST=127.0.0.1   # set to your tailnet IP to expose
# DAEMON_BIND_PORT=7777
EOF
  sudo -u "${USERNAME}" chmod 600 "${STATE_DIR}/.env"
  echo "    Created ${STATE_DIR}/.env — fill in DISCORD_BOT_TOKEN and DISCORD_SESSIONS_CHANNEL_ID"
fi

echo "==> systemd unit"
sudo cp "${DAEMON_DIR}/systemd/discord-daemon.service" /etc/systemd/system/
sudo systemctl daemon-reload
echo "    Enable + start: sudo systemctl enable --now discord-daemon"

echo
echo "Next:"
echo "  1. sudo tailscale up --ssh --hostname=claude-vps"
echo "  2. Edit ${STATE_DIR}/.env (bot token + sessions channel ID)"
echo "  3. Set DAEMON_BIND_HOST to tailnet IP: tailscale ip -4"
echo "  4. sudo systemctl enable --now discord-daemon"
echo "  5. journalctl -u discord-daemon -f"
