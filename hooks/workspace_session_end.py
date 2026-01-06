#!/usr/bin/env python3
"""
Workspace Session End Hook for Claude Code
Hook: SessionEnd

Extracts discoveries and plans from session transcript and persists
them to the workspace scratch/ directory.

Input (JSON on stdin):
{
    "session_id": "...",
    "cwd": "/current/working/directory",
    "transcript_path": "~/.claude/projects/.../session.jsonl"
}

Workflow:
1. Check if scratch/ exists in cwd
2. Read and parse transcript JSONL
3. Extract discoveries (codebase learnings, patterns, gotchas)
4. Extract plans (implementation steps, TODOs)
5. Append to scratch/context/discoveries.md
6. Update scratch/plans/current.md if plans found

NOTE: Uses only Python standard library (no external dependencies)
"""

import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

# Discovery categories to look for
DISCOVERY_PATTERNS = [
    (r'\b(discovered|found|learned|realized|noticed)\b.{10,100}', 'finding'),
    (r'\b(pattern|architecture|structure)\b.{10,100}', 'architecture'),
    (r'\b(gotcha|caveat|watch out|careful|note that|important)\b.{10,100}', 'gotcha'),
    (r'\b(convention|standard|style|naming)\b.{10,100}', 'convention'),
    (r'\b(dependency|requires|depends on|imports?)\b.{10,100}', 'dependency'),
    (r'\b(config|configuration|setting|environment)\b.{10,100}', 'config'),
    (r'\b(entry\s*point|main|bootstrap|init)\b.{10,100}', 'entry'),
]

# Plan indicators
PLAN_PATTERNS = [
    r'(?:^|\n)\s*(?:\d+[\.\)]\s+|[-*]\s+)(.+?)(?=\n|$)',  # numbered/bulleted lists
    r'\b(TODO|FIXME|NEXT|STEP)\b[:\s]+(.+?)(?=\n|$)',
    r'\b(will|should|need to|must)\s+(\w+.{10,80})',
]


def read_transcript(transcript_path: str) -> List[dict]:
    """Read and parse the JSONL transcript file."""
    messages = []
    full_path = os.path.expanduser(transcript_path)

    if not os.path.exists(full_path):
        return messages

    try:
        with open(full_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        msg = json.loads(line)
                        messages.append(msg)
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return messages


def extract_assistant_content(messages: List[dict]) -> str:
    """Extract text content from assistant messages."""
    content_parts = []

    for msg in messages:
        if msg.get('type') == 'assistant':
            message = msg.get('message', {})
            content = message.get('content', [])

            for block in content:
                if isinstance(block, dict) and block.get('type') == 'text':
                    content_parts.append(block.get('text', ''))
                elif isinstance(block, str):
                    content_parts.append(block)

    return '\n'.join(content_parts)


def extract_discoveries(content: str) -> List[Tuple[str, str]]:
    """
    Extract potential discoveries from assistant content.
    Returns list of (category, finding) tuples.
    """
    discoveries = []
    seen = set()

    for pattern, category in DISCOVERY_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            # Clean up the match
            if isinstance(match, tuple):
                match = ' '.join(match)

            finding = match.strip()
            # Skip short or duplicate findings
            if len(finding) < 20 or finding in seen:
                continue

            # Truncate long findings
            if len(finding) > 200:
                finding = finding[:200] + '...'

            seen.add(finding)
            discoveries.append((category, finding))

    # Limit to most relevant discoveries
    return discoveries[:10]


def extract_plans(content: str) -> List[str]:
    """Extract implementation plans/steps from content."""
    plans = []
    seen = set()

    # Look for numbered lists that might be plans
    list_pattern = r'(?:^|\n)\s*(\d+[\.\)]\s+.+?)(?=\n\s*\d+[\.\)]|\n\n|$)'
    matches = re.findall(list_pattern, content, re.MULTILINE | re.DOTALL)

    for match in matches:
        step = match.strip()
        if len(step) > 15 and step not in seen:
            seen.add(step)
            plans.append(step)

    # Look for TODO/NEXT markers
    todo_pattern = r'\b(?:TODO|NEXT|STEP)\s*[:\-]?\s*(.+?)(?=\n|$)'
    matches = re.findall(todo_pattern, content, re.IGNORECASE)

    for match in matches:
        step = match.strip()
        if len(step) > 10 and step not in seen:
            seen.add(step)
            plans.append(f"TODO: {step}")

    return plans[:15]


def append_discoveries(scratch_dir: Path, discoveries: List[Tuple[str, str]]) -> int:
    """Append discoveries to discoveries.md. Returns count added."""
    if not discoveries:
        return 0

    discoveries_file = scratch_dir / "context" / "discoveries.md"
    discoveries_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = []
    for category, finding in discoveries:
        # Clean up finding text
        finding = finding.replace('\n', ' ').strip()
        lines.append(f"- {timestamp}: [{category}] {finding}")

    try:
        with open(discoveries_file, 'a') as f:
            f.write('\n'.join(lines) + '\n')
        return len(lines)
    except Exception:
        return 0


def save_plans(scratch_dir: Path, plans: List[str]) -> bool:
    """Save plans to plans/current.md. Returns success."""
    if not plans:
        return False

    plans_file = scratch_dir / "plans" / "current.md"
    plans_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    content = f"# Current Plan\nUpdated: {timestamp}\n\n"
    content += "## Steps\n"
    for i, plan in enumerate(plans, 1):
        # Clean up
        plan = plan.replace('\n', ' ').strip()
        if not plan.startswith(('TODO', 'FIXME', 'NEXT')):
            content += f"{i}. {plan}\n"
        else:
            content += f"- {plan}\n"

    try:
        # Only overwrite if file doesn't exist or is older than 1 hour
        if plans_file.exists():
            mtime = plans_file.stat().st_mtime
            age_hours = (datetime.now().timestamp() - mtime) / 3600
            if age_hours < 1:
                # Append instead
                with open(plans_file, 'a') as f:
                    f.write(f"\n---\n{content}")
                return True

        with open(plans_file, 'w') as f:
            f.write(content)
        return True
    except Exception:
        return False


def update_session_history(scratch_dir: Path, session_id: str, discoveries_count: int, has_plans: bool):
    """Add session marker to history."""
    history_file = scratch_dir / "history" / "sessions.md"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    summary_parts = []
    if discoveries_count > 0:
        summary_parts.append(f"{discoveries_count} discoveries")
    if has_plans:
        summary_parts.append("plans updated")

    summary = ", ".join(summary_parts) if summary_parts else "no extractions"

    try:
        with open(history_file, 'a') as f:
            f.write(f"\n## Session: {timestamp}\n")
            f.write(f"- ID: {session_id[:8]}...\n")
            f.write(f"- Extracted: {summary}\n")
    except Exception:
        pass


def main():
    """Main hook entry point."""
    try:
        input_data = json.load(sys.stdin)

        session_id = input_data.get("session_id", "unknown")
        cwd = input_data.get("cwd", os.getcwd())
        transcript_path = input_data.get("transcript_path", "")

        scratch_dir = Path(cwd) / "scratch"

        # Only process if workspace exists
        if not scratch_dir.exists():
            return

        # Need transcript to extract from
        if not transcript_path:
            return

        # Read and parse transcript
        messages = read_transcript(transcript_path)
        if not messages:
            return

        # Extract assistant content
        content = extract_assistant_content(messages)
        if not content:
            return

        # Extract discoveries and plans
        discoveries = extract_discoveries(content)
        plans = extract_plans(content)

        # Persist to workspace
        discoveries_count = append_discoveries(scratch_dir, discoveries)
        has_plans = save_plans(scratch_dir, plans)

        # Update session history
        update_session_history(scratch_dir, session_id, discoveries_count, has_plans)

        # Output summary
        if discoveries_count > 0 or has_plans:
            parts = []
            if discoveries_count > 0:
                parts.append(f"{discoveries_count} discoveries")
            if has_plans:
                parts.append("plans")
            print(f"Workspace: saved {', '.join(parts)}", file=sys.stderr)

    except Exception:
        # Never crash the hook
        pass


if __name__ == "__main__":
    main()
