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
        spec = importlib.util.spec_from_file_location("_giantmem_log", os.path.join(os.path.dirname(__file__), "_giantmem_log.py"))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.log("session_end_ingest", msg)
    except Exception:
        pass


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    binary = shutil.which("giantmem") or os.path.expanduser("~/.local/bin/giantmem")
    if not os.path.isfile(binary):
        return

    transcript = data.get("transcript_path") or ""
    project_filter = ""
    # the JSONL lives at ~/.claude/projects/<project-slug>/<uuid>.jsonl
    if transcript:
        slug = os.path.basename(os.path.dirname(transcript))
        # strip leading -Users-bryan-
        if slug.startswith("-Users-"):
            parts = slug.split("-", 3)
            if len(parts) >= 4:
                project_filter = parts[3].replace("-", "/")

    # run as a detached process so the session shutdown isn't blocked
    args = [binary, "ingest", "--sessions-only"]
    if project_filter:
        args += ["--project", project_filter]

    cmd = " ".join(["'" + a.replace("'", "'\\''") + "'" for a in args])
    cmd = f"({cmd} </dev/null >/dev/null 2>&1 & disown) 2>/dev/null"
    try:
        subprocess.Popen(["/bin/bash", "-c", cmd], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        _try_log(f"spawn failed (transcript={transcript}, project={project_filter}): {e}")


if __name__ == "__main__":
    main()
