#!/usr/bin/env bash
# Enable Ubuntu unattended-upgrades for security patches on the VPS.
# Run via SSH: ssh bryan@claude-vps 'sudo bash -s' < scripts/setup-unattended-upgrades.sh

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "run as root (use sudo)" >&2
  exit 1
fi

apt-get update -y
apt-get install -y unattended-upgrades apt-listchanges

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# Force only security updates by default. Override the Origins-Pattern if
# you want broader coverage.
cat > /etc/apt/apt.conf.d/50unattended-upgrades.local <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-Time "03:00";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF

systemctl enable --now unattended-upgrades

unattended-upgrade --dry-run --debug 2>&1 | head -20

echo "==> unattended-upgrades enabled (security only, no auto-reboot)"
echo "    flip Automatic-Reboot to 'true' if you want auto-reboot at 03:00 UTC"
