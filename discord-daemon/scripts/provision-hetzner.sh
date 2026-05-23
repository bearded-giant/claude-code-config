#!/usr/bin/env bash
# Provision a Hetzner Cloud VPS for the discord-daemon + claude sessions.
# Requires: hcloud CLI authenticated with an API token (hcloud context create ...).
# Idempotent — safe to re-run; will reuse SSH key + server if names match.

set -euo pipefail

SERVER_NAME="${SERVER_NAME:-claude-vps}"
SERVER_TYPE="${SERVER_TYPE:-ccx33}"        # 8 vCPU dedicated / 32GB / 240GB SSD
SERVER_IMAGE="${SERVER_IMAGE:-ubuntu-24.04}"
SERVER_LOCATION="${SERVER_LOCATION:-ash}"  # ash=Ashburn VA, hil=Hillsboro OR, fsn1=Falkenstein DE
SSH_KEY_NAME="${SSH_KEY_NAME:-${USER}-laptop}"
SSH_PUBKEY_PATH="${SSH_PUBKEY_PATH:-$HOME/.ssh/id_ed25519.pub}"

# Tailscale: pre-auth key from https://login.tailscale.com/admin/settings/keys
# Optional but recommended — lets cloud-init join tailnet automatically.
TAILSCALE_AUTHKEY="${TAILSCALE_AUTHKEY:-}"

require() {
  command -v "$1" >/dev/null || { echo "missing: $1"; exit 1; }
}
require hcloud
require ssh
require jq

if [ ! -f "$SSH_PUBKEY_PATH" ]; then
  echo "no public key at $SSH_PUBKEY_PATH"
  echo "generate with: ssh-keygen -t ed25519"
  exit 1
fi

# === 1. SSH key ===
if ! hcloud ssh-key describe "$SSH_KEY_NAME" >/dev/null 2>&1; then
  echo "==> uploading SSH key '$SSH_KEY_NAME'"
  hcloud ssh-key create --name "$SSH_KEY_NAME" --public-key-from-file "$SSH_PUBKEY_PATH"
else
  echo "==> SSH key '$SSH_KEY_NAME' already present"
fi

# === 2. Firewall (allow SSH + ICMP only; tailnet handles the rest) ===
FW_NAME="${SERVER_NAME}-fw"
if ! hcloud firewall describe "$FW_NAME" >/dev/null 2>&1; then
  echo "==> creating firewall '$FW_NAME'"
  hcloud firewall create --name "$FW_NAME"
  hcloud firewall add-rule "$FW_NAME" \
    --direction in --protocol tcp --port 22 --source-ips 0.0.0.0/0 --source-ips ::/0
  hcloud firewall add-rule "$FW_NAME" \
    --direction in --protocol icmp --source-ips 0.0.0.0/0 --source-ips ::/0
else
  echo "==> firewall '$FW_NAME' already present"
fi

# === 3. cloud-init user-data ===
# Pre-installs Tailscale + joins tailnet if TAILSCALE_AUTHKEY set.
# Creates 'bryan' user with SSH key. Disables root SSH.
CLOUD_INIT=$(cat <<EOF
#cloud-config
users:
  - name: bryan
    groups: sudo
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - $(cat "$SSH_PUBKEY_PATH")
disable_root: true
ssh_pwauth: false
package_update: true
packages:
  - curl
  - git
  - unzip
  - jq
  - ca-certificates
  - mosh
runcmd:
  - curl -fsSL https://tailscale.com/install.sh | sh
$( [ -n "$TAILSCALE_AUTHKEY" ] && echo "  - tailscale up --ssh --hostname=${SERVER_NAME} --authkey=${TAILSCALE_AUTHKEY}" )
  - sudo -u bryan bash -lc 'curl -fsSL https://bun.sh/install | bash'
EOF
)

# === 4. Server ===
if ! hcloud server describe "$SERVER_NAME" >/dev/null 2>&1; then
  echo "==> creating server '$SERVER_NAME' ($SERVER_TYPE in $SERVER_LOCATION)"
  hcloud server create \
    --name "$SERVER_NAME" \
    --type "$SERVER_TYPE" \
    --image "$SERVER_IMAGE" \
    --location "$SERVER_LOCATION" \
    --ssh-key "$SSH_KEY_NAME" \
    --firewall "$FW_NAME" \
    --user-data-from-file <(echo "$CLOUD_INIT")
else
  echo "==> server '$SERVER_NAME' already exists"
fi

IP=$(hcloud server ip "$SERVER_NAME")
echo
echo "==> server ready: $SERVER_NAME @ $IP"
echo
echo "Wait ~60s for cloud-init, then:"
echo "  ssh bryan@$IP"
if [ -z "$TAILSCALE_AUTHKEY" ]; then
  echo
  echo "Tailscale was installed but not joined (no TAILSCALE_AUTHKEY)."
  echo "Run on VPS:  sudo tailscale up --ssh --hostname=${SERVER_NAME}"
fi
echo
echo "Then install daemon:"
echo "  scp -r ../discord-daemon bryan@$IP:~/"
echo "  ssh bryan@$IP 'sudo bash ~/discord-daemon/scripts/install-vps.sh'"
