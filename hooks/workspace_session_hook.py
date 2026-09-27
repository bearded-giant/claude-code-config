#!/usr/bin/env python3
"""
Workspace Session Hook for Claude Code
Hook: SessionStart

Bootstraps workspace structure and injects context when session begins.

Input (JSON on stdin):
{
    "session_id": "...",
    "cwd": "/current/working/directory",
    "source": "startup" | "resume" | "clear"
}

Output: Workspace context injected into session via stdout.

Workflow:
1. Check if .giantmem/ exists in cwd (fallback: scratch/)
2. If not, bootstrap via workspace-lib.sh
3. Read WORKSPACE.md and plans/current.md
4. Output context for Claude to use

NOTE: Uses only Python standard library (no external dependencies)
"""

import sys
import json
import os
import subprocess
import time
from pathlib import Path

# path to workspace-lib.sh - local copy in claude-code-config/lib, fallback to giant-tooling
WORKSPACE_LIB = Path(
    os.environ.get(
        "WORKSPACE_LIB", str(Path.home() / ".claude/lib/workspace/workspace-lib.sh")
    )
)
if not WORKSPACE_LIB.exists():
    WORKSPACE_LIB = (
        Path(
            os.environ.get("GIANT_TOOLING_DIR", str(Path.home() / "dev/giant-tooling"))
        )
        / "workspace/workspace-lib.sh"
    )


# not the cache dir: its mtime moves without an install
PLUGIN_PATHS = [Path.home() / ".claude/plugins/installed_plugins.json"]


def claude_process_start() -> float | None:
    pid = os.getpid()
    for _ in range(10):
        try:
            out = subprocess.run(
                ["ps", "-o", "ppid=,lstart=,comm=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            ).stdout.split()
        except (OSError, subprocess.SubprocessError):
            return None
        if len(out) < 7:
            return None
        ppid, lstart, comm = int(out[0]), " ".join(out[1:6]), " ".join(out[6:])
        if Path(comm).name == "claude":
            try:
                return time.mktime(time.strptime(lstart, "%a %b %d %H:%M:%S %Y"))
            except ValueError:
                return None
        if ppid <= 1:
            return None
        pid = ppid
    return None


def stale_plugins(proc_start: float, paths) -> list[str]:
    return [str(p) for p in paths if p.exists() and p.stat().st_mtime > proc_start]


def restart_notice(source: str) -> str:
    # /clear keeps the process, so plugins installed since startup are not loaded
    if source != "clear":
        return ""
    start = claude_process_start()
    if start is None:
        return ""
    stale = stale_plugins(start, PLUGIN_PATHS)
    if not stale:
        return ""
    return (
        "FULL RESTART REQUIRED: plugins changed after this claude process started; "
        "/clear does not reload them:\n  " + "\n  ".join(stale)
    )


def bootstrap_workspace(cwd: str) -> bool:
    """
    Bootstrap workspace structure using workspace-lib.sh.
    Returns True if bootstrap was performed.
    """
    workspace_dir = Path(cwd) / ".giantmem"
    if not workspace_dir.exists():
        workspace_dir = Path(cwd) / "scratch"

    if workspace_dir.exists():
        return False

    if not WORKSPACE_LIB.exists():
        return False

    try:
        cmd = f'source "{WORKSPACE_LIB}" && workspace_init "{cwd}"'
        subprocess.run(["bash", "-c", cmd], cwd=cwd, capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def read_workspace_context(cwd: str) -> dict:
    """
    Read workspace context files.
    Returns dict with available context.
    """
    workspace_dir = Path(cwd) / ".giantmem"
    if not workspace_dir.exists():
        workspace_dir = Path(cwd) / "scratch"
    context = {
        "workspace_md": None,
        "current_plan": None,
        "bootstrapped": False,
    }

    if not workspace_dir.exists():
        return context

    # read WORKSPACE.md
    workspace_file = workspace_dir / "WORKSPACE.md"
    if workspace_file.exists():
        try:
            context["workspace_md"] = workspace_file.read_text()[:3500]
        except Exception:
            pass

    # read current plan if exists
    plan_file = workspace_dir / "plans" / "current.md"
    if plan_file.exists():
        try:
            context["current_plan"] = plan_file.read_text()[:1500]
        except Exception:
            pass

    return context


def format_context_output(context: dict, cwd: str, bootstrapped: bool) -> str:
    """
    Format workspace context for injection into Claude session.
    """
    parts = []

    project_name = Path(cwd).name

    if bootstrapped:
        parts.append(f"[Workspace bootstrapped for {project_name}]")
        parts.append("Created .giantmem/ via workspace_init")
        parts.append("")

    if context.get("workspace_md"):
        parts.append("=== WORKSPACE CONTEXT ===")
        parts.append(context["workspace_md"])
        parts.append("")

    if context.get("current_plan"):
        parts.append("=== ACTIVE PLAN ===")
        parts.append(context["current_plan"])
        parts.append("")

    return "\n".join(parts) if parts else ""


def main():
    """Main hook entry point."""
    try:
        input_data = json.load(sys.stdin)

        cwd = input_data.get("cwd", os.getcwd())
        source = input_data.get("source", "startup")

        # Only bootstrap on fresh startup, not resume
        bootstrapped = False
        if source == "startup":
            bootstrapped = bootstrap_workspace(cwd)

        # Read workspace context
        context = read_workspace_context(cwd)

        # Format and output
        output = format_context_output(context, cwd, bootstrapped)
        notice = restart_notice(source)
        if notice:
            output = notice + ("\n\n" + output if output else "")

        if output:
            print(output)

    except Exception:
        # Never crash the hook
        pass


if __name__ == "__main__":
    main()
