#!/usr/bin/env python3
"""SessionStart hook — idempotently apply discord plugin patch.

The bundled `discord@claude-plugins-official` 0.0.4 plugin has a partial-DM
recipient bug. We carry a local patch at
`scripts/patches/discord-dm-recipient.patch`. The plugin cache may be wiped
or replaced by claude on update. This hook re-applies the patch if missing.

Safe to run on every session start — checks the marker string first; only
runs `patch` if needed. Logs to stderr so it appears in claude debug.
"""
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
PLUGIN_DIR_CANDIDATES = [
    HOME / ".claude/plugins/cache/claude-plugins-official/discord/0.0.4",
]
PATCH_PATH = HOME / ".claude/scripts/patches/discord-dm-recipient.patch"
MARKER = "Partials.Channel makes DMs partial"


def find_plugin_dir() -> Path | None:
    for p in PLUGIN_DIR_CANDIDATES:
        if (p / "server.ts").exists():
            return p
    # Glob fallback for newer versions
    base = HOME / ".claude/plugins/cache/claude-plugins-official"
    if base.is_dir():
        for d in base.glob("discord/*"):
            if (d / "server.ts").exists():
                return d
    return None


def main() -> int:
    plugin_dir = find_plugin_dir()
    if not plugin_dir:
        return 0  # plugin not installed; nothing to do
    if not PATCH_PATH.exists():
        return 0  # patch file missing; nothing to apply
    server_ts = plugin_dir / "server.ts"
    if MARKER in server_ts.read_text():
        return 0  # already applied
    if not shutil.which("patch"):
        sys.stderr.write("discord_patch_apply: `patch` not on PATH; skipping\n")
        return 0
    try:
        subprocess.run(
            ["patch", "-p1", "-d", str(plugin_dir), "-i", str(PATCH_PATH)],
            check=True, capture_output=True,
        )
        sys.stderr.write(f"discord_patch_apply: applied patch to {plugin_dir}\n")
    except subprocess.CalledProcessError as e:
        sys.stderr.write(
            f"discord_patch_apply: patch failed: {e.stderr.decode(errors='ignore')}\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
