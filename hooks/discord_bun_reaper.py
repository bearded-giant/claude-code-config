#!/usr/bin/env python3
"""SessionEnd hook: kill bun server.ts processes whose ancestor chain
contains this claude session's PID. Prevents discord MCP orphans when
claude is SIGKILL'd or terminal is closed.

The discord plugin spawns `bun run --cwd ... start` which spawns `bun server.ts`.
On clean claude exit, MCP transport closes stdin and bun shuts down. On SIGKILL
or terminal close, the bash/bun-run wrapper doesn't propagate EOF and the inner
bun server.ts is orphaned. Each orphan stays connected to Discord gateway with
the same token, racing future sessions over inbound DMs.
"""

import os
import sys
import subprocess


def get_ancestors(pid: int, max_depth: int = 20) -> set[int]:
    chain = set()
    cur = pid
    for _ in range(max_depth):
        try:
            ppid = subprocess.check_output(
                ["ps", "-o", "ppid=", "-p", str(cur)], text=True
            ).strip()
        except subprocess.CalledProcessError:
            break
        if not ppid or ppid == "0":
            break
        ppid_i = int(ppid)
        if ppid_i in chain:
            break
        chain.add(ppid_i)
        cur = ppid_i
    return chain


def main() -> None:
    claude_pid = os.getppid()

    try:
        out = subprocess.check_output(["pgrep", "-f", "bun server.ts"], text=True)
    except subprocess.CalledProcessError:
        return

    for line in out.strip().splitlines():
        try:
            bun_pid = int(line.strip())
        except ValueError:
            continue
        if claude_pid in get_ancestors(bun_pid):
            try:
                os.kill(bun_pid, 15)
                print(f"discord_bun_reaper: killed bun {bun_pid}", file=sys.stderr)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"discord_bun_reaper: error: {e}", file=sys.stderr)
