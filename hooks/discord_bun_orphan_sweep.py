#!/usr/bin/env python3
"""SessionStart hook: sweep `bun server.ts` processes with no live claude
ancestor. These are leftovers from crashed/SIGKILL'd claude sessions —
SessionEnd reaper never ran for them.

Safe: only kills bun discord servers whose entire ancestor chain lacks a
live `claude` process. Active sessions' bun children are untouched.
"""

import os
import subprocess
import sys


def cmd_of(pid: int) -> str:
    try:
        return subprocess.check_output(
            ["ps", "-o", "command=", "-p", str(pid)], text=True
        ).strip()
    except subprocess.CalledProcessError:
        return ""


def has_claude_ancestor(pid: int, max_depth: int = 20) -> bool:
    cur = pid
    seen = set()
    for _ in range(max_depth):
        try:
            ppid = subprocess.check_output(
                ["ps", "-o", "ppid=", "-p", str(cur)], text=True
            ).strip()
        except subprocess.CalledProcessError:
            return False
        if not ppid or ppid == "0":
            return False
        ppid_i = int(ppid)
        if ppid_i in seen:
            return False
        seen.add(ppid_i)
        anc_cmd = cmd_of(ppid_i)
        # Match the actual claude binary, not random scripts mentioning the word
        if anc_cmd.endswith("/claude") or anc_cmd == "claude" or "/bin/claude" in anc_cmd:
            return True
        cur = ppid_i
    return False


def main() -> None:
    try:
        out = subprocess.check_output(["pgrep", "-f", "bun server.ts"], text=True)
    except subprocess.CalledProcessError:
        return

    for line in out.strip().splitlines():
        try:
            bun_pid = int(line.strip())
        except ValueError:
            continue
        if not has_claude_ancestor(bun_pid):
            try:
                os.kill(bun_pid, 15)
                print(f"discord_bun_orphan_sweep: killed orphan bun {bun_pid}", file=sys.stderr)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"discord_bun_orphan_sweep: error: {e}", file=sys.stderr)
