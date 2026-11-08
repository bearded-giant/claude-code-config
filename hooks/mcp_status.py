#!/usr/bin/env python3
import subprocess
import sys

from preflight_check import write_json


def parse(output):
    total = auth = 0
    for line in output.splitlines():
        if ": " not in line or " - " not in line:
            continue
        status = line.rsplit(" - ", 1)[1]
        if "Disabled" in status:
            continue
        total += 1
        if "Needs authentication" in status:
            auth += 1
    return {"total": total, "auth": auth}


def main():
    cwd, out = sys.argv[1:3]
    try:
        r = subprocess.run(
            ["claude", "mcp", "list"],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # keep the last good read; the statusline ages it out
        return
    if r.returncode != 0:
        return
    write_json(out, parse(r.stdout))


if __name__ == "__main__":
    main()
