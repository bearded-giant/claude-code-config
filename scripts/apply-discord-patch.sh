#!/usr/bin/env bash
# Apply local patches to the bundled discord plugin in plugins/cache.
# The cache is rewritten on plugin update, so this needs to be re-run after
# any `discord@claude-plugins-official` version change.
#
# Idempotent: skips if patch already applied.

set -euo pipefail

PLUGIN_DIR="${PLUGIN_DIR:-$HOME/.claude/plugins/cache/claude-plugins-official/discord/0.0.4}"
PATCH_DIR="$(cd "$(dirname "$0")/patches" && pwd)"

if [ ! -d "$PLUGIN_DIR" ]; then
  echo "discord plugin not found at $PLUGIN_DIR" >&2
  echo "(may have updated to a newer version — adjust PLUGIN_DIR env)" >&2
  exit 1
fi

apply_patch() {
  local patch_file="$1" marker="$2" desc="$3"
  if grep -q "$marker" "$PLUGIN_DIR/server.ts"; then
    echo "  - $desc: already applied, skipping"
    return 0
  fi
  patch --dry-run -p1 -d "$PLUGIN_DIR" -i "$patch_file" >/dev/null 2>&1 || {
    echo "  ! $desc: dry-run failed — upstream may have changed" >&2
    return 1
  }
  patch -p1 -d "$PLUGIN_DIR" -i "$patch_file" >/dev/null
  echo "  ✓ $desc: applied"
}

echo "==> patching $PLUGIN_DIR"
apply_patch "$PATCH_DIR/discord-dm-recipient.patch" \
  'Partials.Channel makes DMs partial' \
  'DM recipient partial-fetch'

echo
echo "Restart MCP for changes to take effect:"
echo "  pkill -f 'discord/0.0.4'  # then run /mcp in claude session"
