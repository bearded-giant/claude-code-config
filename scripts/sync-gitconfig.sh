#!/usr/bin/env bash
# Push laptop's git config to the VPS. Idempotent. Run any time your
# local gitconfig changes (new alias, identity tweak, signing key swap).
#
# Reads from XDG path (~/.config/git/config) with fallback to ~/.gitconfig.
# By default strips GPG signing settings (signingkey, commit.gpgsign) since
# the GPG private key isn't on the VPS — commits would otherwise fail.
# Override with KEEP_GPG=1 if you've separately transferred the key.
#
# Usage:
#   ./scripts/sync-gitconfig.sh                  # default remote = claude-vps
#   ./scripts/sync-gitconfig.sh other-host
#   KEEP_GPG=1 ./scripts/sync-gitconfig.sh       # preserve signing settings

set -euo pipefail
REMOTE="${1:-claude-vps}"

if [ -f "$HOME/.config/git/config" ]; then
  SRC="$HOME/.config/git/config"
elif [ -f "$HOME/.gitconfig" ]; then
  SRC="$HOME/.gitconfig"
else
  echo "no git config found on laptop (~/.config/git/config or ~/.gitconfig)" >&2
  exit 1
fi

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
if [ "${KEEP_GPG:-0}" = "1" ]; then
  cp "$SRC" "$TMP"
else
  grep -v -E '^\s*(signingkey|gpgsign|gpgSign|gpgsign\s*=)' "$SRC" \
    | sed 's/^\s*gpgsign\s*=.*/# gpgsign stripped by sync-gitconfig.sh/' \
    > "$TMP"
fi

ssh "$REMOTE" 'mkdir -p ~/.config/git'
scp -q "$TMP" "$REMOTE:~/.config/git/config"
echo "synced $SRC → $REMOTE:~/.config/git/config (KEEP_GPG=${KEEP_GPG:-0})"
ssh "$REMOTE" 'git config --global user.name; git config --global user.email' || true
