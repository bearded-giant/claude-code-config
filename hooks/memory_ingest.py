#!/usr/bin/env python3
"""SessionStart hook: ingest harness memory files into archives.db.

Runs `giantmem db ingest --source memory-md` detached, so ~/.claude/projects/*/memory/*.md
land in the durable store (backed up, survives a live.db rebuild) without adding
SessionStart latency. Same-session immediacy still comes from live_index.py
writing memory files into live.db on PostToolUse.

Writes nothing to stdout so it never injects into the session context.
"""

import os
import shutil
import subprocess


def main() -> None:
    binary = shutil.which("giantmem") or os.path.expanduser("~/.local/bin/giantmem")
    if not os.path.isfile(binary):
        return
    args = [binary, "db", "ingest", "--source", "memory-md"]
    cmd = " ".join(["'" + a.replace("'", "'\\''") + "'" for a in args])
    cmd = f"({cmd} </dev/null >/dev/null 2>&1 & disown) 2>/dev/null"
    try:
        subprocess.Popen(
            ["/bin/bash", "-c", cmd],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        pass


if __name__ == "__main__":
    main()
