#!/usr/bin/env python3
"""
SessionEnd hook: kick off a sessions-only ingest for the just-ended JSONL.

Runs in the background so it doesn't block session shutdown. Updates
archives.db so the session is searchable immediately.

Stdlib only.
"""

import json
import os
import shutil
import subprocess
import sys


def _try_log(msg: str) -> None:
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_giantmem_log", os.path.join(os.path.dirname(__file__), "_giantmem_log.py")
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.log("session_end_ingest", msg)
    except Exception:
        pass


def _detect_project(cwd: str) -> str:
    # the project-slug directory name is lossy (hyphens in the repo name are
    # indistinguishable from path separators), so ask live_index's detector,
    # which is the one giantmem's Go side mirrors
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_live_index", os.path.join(os.path.dirname(__file__), "live_index.py")
        )
        if not (spec and spec.loader):
            return ""
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.detect_project(cwd, mod.ARCHIVE_BASE)[0]
    except Exception:
        return ""


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    binary = shutil.which("giantmem") or os.path.expanduser("~/.local/bin/giantmem")
    if not os.path.isfile(binary):
        return

    transcript = data.get("transcript_path") or ""
    project_filter = _detect_project(data.get("cwd") or os.getcwd())

    # run as a detached process so the session shutdown isn't blocked
    args = [binary, "db", "ingest", "--sessions-only"]
    if project_filter:
        args += ["--project", project_filter]

    _spawn(args, f"transcript={transcript}, project={project_filter}")

    # once a day: flip stale, never-accessed candidates to deprecated
    marker = os.path.expanduser("~/.cache/giantmem/last-autodeprecate")
    today = __import__("datetime").date.today().isoformat()
    try:
        stamp = open(marker, encoding="utf-8").read().strip()
    except OSError:
        stamp = ""
    if stamp != today:
        try:
            os.makedirs(os.path.dirname(marker), exist_ok=True)
            with open(marker, "w", encoding="utf-8") as f:
                f.write(today)
        except OSError:
            pass
        _spawn(
            [binary, "artifact", "stale", "--days", "0", "--all-repos", "--apply"],
            "autodeprecate",
        )


def _spawn(args, context: str) -> None:
    # detached so session shutdown is never blocked
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
    except Exception as e:
        _try_log(f"spawn failed ({context}): {e}")


if __name__ == "__main__":
    main()
