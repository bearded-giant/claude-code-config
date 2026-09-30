#!/usr/bin/env python3
import os
import stat
import sys
from pathlib import Path

CONSTRAINTS = Path(__file__).resolve().parents[1] / "config" / "standing-constraints.md"
CAVEMAN_FLAG = (
    Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    / ".caveman-active"
)
CAVEMAN_MODES = {
    "lite",
    "full",
    "ultra",
    "wenyan-lite",
    "wenyan",
    "wenyan-full",
    "wenyan-ultra",
}
MAX_FLAG_BYTES = 64
SUBAGENT_STRATEGY = (
    "STRATEGY: no user to confirm with. State assumptions at the top of your final "
    "report and proceed. Two failed attempts at one approach: stop it, report "
    "evidence + options."
)


def for_subagent(text):
    # subagents cannot wait on the user; confirm-and-wait becomes an early end_turn
    out = []
    for line in text.splitlines():
        if line.startswith("DOIT LIST:"):
            continue
        out.append(SUBAGENT_STRATEGY if line.startswith("STRATEGY:") else line)
    return "\n".join(out)


def caveman_mode():
    # same guards as caveman-config.js readFlag: no symlinks, size cap, whitelist
    try:
        st = CAVEMAN_FLAG.lstat()
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FLAG_BYTES:
            return None
        mode = CAVEMAN_FLAG.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return None
    return mode if mode in CAVEMAN_MODES else None


def main():
    sys.stdin.read()
    parts = []
    mode = caveman_mode()
    if mode:
        parts.append(
            f"CAVEMAN MODE ACTIVE ({mode}). Drop articles/filler/pleasantries/hedging. "
            "Fragments OK. Code/commits/security: write normal. "
            "Applies to your final report to the parent agent."
        )
    try:
        constraints = for_subagent(CONSTRAINTS.read_text(encoding="utf-8").strip())
    except OSError:
        constraints = ""
    if constraints:
        parts.append(constraints)
    if parts:
        print("\n\n".join(parts))


if __name__ == "__main__":
    main()
