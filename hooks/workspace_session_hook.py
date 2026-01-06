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
1. Check if scratch/ exists in cwd
2. If not, bootstrap via workspace-lib.sh
3. Read WORKSPACE.md and discoveries.md
4. Output context for Claude to use

NOTE: Uses only Python standard library (no external dependencies)
"""

import sys
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

# Path to workspace-lib.sh - adjust if needed
WORKSPACE_LIB = Path.home() / "dev/script-hodge-podge/git-things/workspace-lib.sh"


def bootstrap_workspace(cwd: str) -> bool:
    """
    Bootstrap workspace structure using workspace-lib.sh.
    Returns True if bootstrap was performed.
    """
    scratch_dir = Path(cwd) / "scratch"

    if scratch_dir.exists():
        return False

    if not WORKSPACE_LIB.exists():
        return False

    try:
        # Source the lib and call workspace_init
        cmd = f'source "{WORKSPACE_LIB}" && workspace_init "{cwd}"'
        subprocess.run(
            ["bash", "-c", cmd],
            cwd=cwd,
            capture_output=True,
            timeout=10
        )
        return True
    except Exception:
        return False


def read_workspace_context(cwd: str) -> dict:
    """
    Read workspace context files.
    Returns dict with available context.
    """
    scratch_dir = Path(cwd) / "scratch"
    context = {
        "workspace_md": None,
        "discoveries": None,
        "tree": None,
        "current_plan": None,
        "bootstrapped": False
    }

    if not scratch_dir.exists():
        return context

    # Read WORKSPACE.md
    workspace_file = scratch_dir / "WORKSPACE.md"
    if workspace_file.exists():
        try:
            context["workspace_md"] = workspace_file.read_text()[:2000]
        except Exception:
            pass

    # Read discoveries
    discoveries_file = scratch_dir / "context" / "discoveries.md"
    if discoveries_file.exists():
        try:
            content = discoveries_file.read_text()
            # Get last 20 discoveries (most recent context)
            lines = content.strip().split("\n")
            context["discoveries"] = "\n".join(lines[-20:])
        except Exception:
            pass

    # Read tree (truncated)
    tree_file = scratch_dir / "context" / "tree.md"
    if tree_file.exists():
        try:
            content = tree_file.read_text()
            # Truncate to first 100 lines
            lines = content.split("\n")[:100]
            context["tree"] = "\n".join(lines)
        except Exception:
            pass

    # Read current plan if exists
    plan_file = scratch_dir / "plans" / "current.md"
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
        parts.append("Created scratch/ with: context/, plans/, history/, prompts/, research/, reviews/, filebox/")
        parts.append("")

    if context.get("workspace_md"):
        parts.append("=== WORKSPACE CONTEXT ===")
        parts.append(context["workspace_md"])
        parts.append("")

    if context.get("current_plan"):
        parts.append("=== ACTIVE PLAN ===")
        parts.append(context["current_plan"])
        parts.append("")

    if context.get("discoveries"):
        parts.append("=== RECENT DISCOVERIES ===")
        parts.append(context["discoveries"])
        parts.append("")

    if parts:
        # Add usage reminder
        parts.append("---")
        parts.append("Remember: Save findings to scratch/context/discoveries.md, plans to scratch/plans/")

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

        if output:
            print(output)

    except Exception:
        # Never crash the hook
        pass


if __name__ == "__main__":
    main()
