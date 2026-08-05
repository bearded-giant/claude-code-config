#!/usr/bin/env python3
"""PostToolUse hook: flag comment patterns CLAUDE.md forbids in Python source.

Hook: PostToolUse (matcher: Write|Edit|MultiEdit)

`## Code Comment Rules` bans multi-line comment blocks, docstrings, section
banners and ticket refs outright, but black/isort/pylint pass them clean, so the
rule had no enforcement and drifted. This inspects only the text the tool just
added -- new_string / content / MultiEdit edits -- so pre-existing comments in
the file never trigger it.

Checks (non-test .py only, tests are exempt by the rule):
- runs of 2+ consecutive comment lines
- docstring opened on the line after a def/class signature
- section banners (# ===, # ---)
- ticket refs (# PE-1234)

Emits hookSpecificOutput.additionalContext. Advisory only -- never blocks.
Debounced per session + file + finding so re-edits don't re-nudge.

Stdlib only.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

NUDGE_DIR = Path("/tmp/claude-comment-nudged")

MIN_COMMENT_RUN = 2

# pragmas and tool directives are not prose comments
PRAGMA_RE = re.compile(
    r"^#\s*(type:|pylint:|noqa|fmt:|isort:|mypy:|pragma:|coding[:=]|!)",
)
BANNER_RE = re.compile(r"^#\s*[-=*_#]{3,}")
TICKET_RE = re.compile(r"^#.*\b[A-Z]{2,}-\d+\b")
SIGNATURE_END_RE = re.compile(r"^\s*(async\s+def|def|class)\b.*:\s*(#.*)?$")
SIGNATURE_START_RE = re.compile(r"^\s*(async\s+def|def|class)\b")
DOCSTRING_RE = re.compile(r'^\s*[rbuf]{0,2}("""|\'\'\')')


def is_python_source(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    parts = Path(path).parts
    name = Path(path).name
    if "tests" in parts or "test" in parts:
        return False
    # this repo's own hooks document themselves; project convention wins over the global rule
    if "claude-code-config" in parts and "hooks" in parts:
        return False
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return False
    return True


def added_texts(tool_input: dict) -> list:
    """Every chunk of text this tool call introduced."""
    texts = []
    content = tool_input.get("content")
    if isinstance(content, str):
        texts.append(content)
    new_string = tool_input.get("new_string")
    if isinstance(new_string, str):
        texts.append(new_string)
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
            texts.append(edit["new_string"])
    return texts


def comment_runs(lines: list) -> list:
    """Start line + length of every run of MIN_COMMENT_RUN+ prose comment lines."""
    runs = []
    run_start = None
    run_len = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        is_prose_comment = stripped.startswith("#") and not PRAGMA_RE.match(stripped)
        if is_prose_comment:
            if run_start is None:
                run_start = idx
            run_len += 1
            continue
        if run_len >= MIN_COMMENT_RUN:
            runs.append((run_start, run_len))
        run_start, run_len = None, 0
    if run_len >= MIN_COMMENT_RUN:
        runs.append((run_start, run_len))
    return runs


def docstring_lines(lines: list) -> list:
    """Line indexes where a docstring opens right after a def/class signature."""
    hits = []
    pending_signature = False
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        if pending_signature and DOCSTRING_RE.match(raw):
            hits.append(idx)
            pending_signature = False
            continue
        if SIGNATURE_END_RE.match(raw):
            pending_signature = True
        elif SIGNATURE_START_RE.match(raw) or (pending_signature and not stripped.endswith(":")):
            # multi-line signature -- stay armed until the closing `:`
            pending_signature = stripped.endswith(":") or pending_signature
        else:
            pending_signature = False
    return hits


def scan(text: str) -> list:
    lines = text.splitlines()
    findings = []

    for start, length in comment_runs(lines):
        findings.append((f"{length}-line comment block", lines[start].strip()))

    for idx in docstring_lines(lines):
        findings.append(("docstring", lines[idx].strip()[:60]))

    for raw in lines:
        stripped = raw.strip()
        if not stripped.startswith("#"):
            continue
        if BANNER_RE.match(stripped):
            findings.append(("section banner", stripped[:60]))
        elif TICKET_RE.match(stripped):
            findings.append(("ticket ref", stripped[:60]))

    return findings


def marker_for(session_id: str, file_path: str, findings: list) -> Path:
    payload = file_path + "|" + "|".join(f"{kind}:{snippet}" for kind, snippet in findings)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return NUDGE_DIR / session_id / digest


def emit(message: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    }
    sys.stdout.write(json.dumps(out))


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path or not is_python_source(file_path):
        return

    findings = []
    for text in added_texts(tool_input):
        findings.extend(scan(text))
    if not findings:
        return

    # de-dup identical findings from repeated chunks, keep order
    seen = set()
    unique = []
    for finding in findings:
        if finding not in seen:
            seen.add(finding)
            unique.append(finding)

    session_id = data.get("session_id") or os.getenv("CLAUDE_SESSION_ID") or "nosid"
    marker = marker_for(session_id, file_path, unique)
    if marker.exists():
        return
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except Exception:
        pass

    listed = "; ".join(f"{kind} -> {snippet}" for kind, snippet in unique[:6])
    message = (
        f"Comment-rule check on {os.path.basename(file_path)}: {listed}. "
        f"CLAUDE.md `## Code Comment Rules` forbids multi-line comment blocks, docstrings, "
        f"section banners and ticket refs in source. Default is ZERO comments; the only allowed "
        f"shape is one lowercase line stating a non-obvious WHY (hidden constraint, subtle "
        f"invariant, workaround). Decision rationale for reviewers belongs in the MR body or a "
        f".giantmem/ doc, not at the call site. Re-read what you just added and delete or compress "
        f"it to one line, unless the user explicitly asked for comments or docstrings."
    )
    emit(message)


if __name__ == "__main__":
    main()
