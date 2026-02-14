#!/usr/bin/env python3
"""
Memory Session Start Hook for Claude Code
Hook: SessionStart

Injects session primer when a new session begins.
The primer provides temporal context - when we last spoke,
what we were working on, project status.

The hook receives JSON on stdin:
{
    "session_id": "...",
    "cwd": "/current/working/directory",
    "source": "startup" | "resume" | "clear"
}

Output to stdout is injected as context for the session.

NOTE: Uses only Python standard library (no external dependencies)
"""

import sys
import json
import os
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Configuration
MEMORY_API_URL = os.getenv("MEMORY_API_URL", "http://localhost:8765")
DEFAULT_PROJECT_ID = os.getenv("MEMORY_PROJECT_ID", "default")
TIMEOUT_SECONDS = 5


def http_post(url: str, data: dict, timeout: int = 5) -> dict:
    """Make HTTP POST request using only standard library."""
    try:
        json_data = json.dumps(data).encode('utf-8')
        request = Request(
            url,
            data=json_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError):
        return {}


def _derive_project_id(path: Path) -> str:
    # prefer git remote name, fall back to directory name
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(path), capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            url = result.stdout.strip().rstrip("/")
            # extract "org/repo" or just "repo" from url
            name = url.split(":")[-1].split("/")[-1]
            return name.removesuffix(".git")
    except Exception:
        pass
    return path.name or DEFAULT_PROJECT_ID


def get_project_id(cwd: str, bootstrap: bool = False) -> str:
    path = Path(cwd)

    for parent in [path] + list(path.parents):
        config_file = parent / ".memory-project.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    return config.get("project_id", DEFAULT_PROJECT_ID)
            except Exception:
                pass

    # no config found — bootstrap one at the project root
    if not bootstrap:
        return _derive_project_id(path)

    project_id = _derive_project_id(path)
    config_path = path / ".memory-project.json"
    try:
        config_path.write_text(json.dumps({"project_id": project_id}, indent=2) + "\n")
    except OSError:
        pass
    return project_id


def get_session_primer(session_id: str, project_id: str) -> str:
    """
    Get session primer from memory system.
    
    The primer provides continuity context:
    - When we last spoke
    - What happened in previous session
    - Current project status
    """
    result = http_post(
        f"{MEMORY_API_URL}/memory/context",
        {
            "session_id": session_id,
            "project_id": project_id,
            "current_message": "",  # Empty to get just primer
            "max_memories": 0  # No memories, just primer
        },
        timeout=TIMEOUT_SECONDS
    )
    return result.get("context_text", "")


def register_session(session_id: str, project_id: str):
    """
    Register the session with the memory system.
    This increments the message counter so the inject hook
    knows to retrieve memories instead of the primer.
    """
    http_post(
        f"{MEMORY_API_URL}/memory/process",
        {
            "session_id": session_id,
            "project_id": project_id,
            "metadata": {"event": "session_start"}
        },
        timeout=2
    )


def main():
    """Main hook entry point."""
    # Skip if this is being called from the memory curator subprocess
    if os.getenv("MEMORY_CURATOR_ACTIVE") == "1":
        return
    
    try:
        # Read input from stdin
        input_data = json.load(sys.stdin)
        
        session_id = input_data.get("session_id", "unknown")
        # Use CLAUDE_PROJECT_DIR for actual project root (cwd from stdin is bash's current dir)
        cwd = os.getenv("CLAUDE_PROJECT_DIR") or input_data.get("cwd", os.getcwd())
        source = input_data.get("source", "startup")
        
        project_id = get_project_id(cwd, bootstrap=True)
        
        # Get session primer from memory system
        primer = get_session_primer(session_id, project_id)
        
        # Register session so inject hook knows to get memories, not primer
        register_session(session_id, project_id)
        
        # Output primer to stdout (will be injected into session)
        if primer:
            print(primer)
            
    except Exception:
        # Never crash
        pass


if __name__ == "__main__":
    main()
