#!/usr/bin/env python3
"""SessionStart: after /clear, write a handoff of the cleared session in the background and point the new one at it."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MARKER_DIR = Path("/tmp")
ARCHIVE = Path.home() / "giantmem_archive" / "handoff-clear"
INSTRUCTIONS = (
    Path(__file__).resolve().parents[1] / "config" / "compact-instructions.md"
)
ASKS = 3
EXTRACT_HEAD = 20_000
EXTRACT_MAX = 240_000
FALLBACK_TAIL = 6_000
THINKING_CHARS = 1_500
SUMMARY_TIMEOUT = 300
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
PROMPT = (
    "Write a handoff note for the next Claude Code session, which starts empty after /clear. "
    "Below is an extract of the cleared session: the summary of any compacted earlier part, "
    "user asks, assistant replies and thinking, and one line per tool call (tool output dropped). "
    "Thinking may hold hypotheses the session later dropped: mark a claim from thinking alone as inferred. "
    "Markdown, terse, no preamble.\n\n"
)


def claude_proc() -> tuple[int, str] | None:
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
            return pid, lstart
        if ppid <= 1:
            return None
        pid = ppid
    return None


def _texts(content):
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    return [
        b.get("text", "")
        for b in content
        if isinstance(b, dict) and b.get("type") == "text"
    ]


def load(transcript_path: str) -> list[dict]:
    try:
        lines = Path(os.path.expanduser(transcript_path)).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return []
    rows = []
    for line in lines.splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if isinstance(m, dict) and not (m.get("isSidechain") or m.get("isMeta")):
            rows.append(m)
    return rows


def _asks(row: dict) -> list[str]:
    if row.get("type") != "user" or row.get("isCompactSummary"):
        return []
    texts = (t.strip() for t in _texts((row.get("message") or {}).get("content")))
    # command caveats, local stdout, and injected reminders are not asks
    return [t for t in texts if t and not t.startswith("<")]


def _tool_line(block: dict) -> str:
    args = block.get("input") or {}
    arg = next(
        (
            args[k]
            for k in ("command", "file_path", "pattern", "url", "description")
            if isinstance(args.get(k), str)
        ),
        "",
    )
    return f"TOOL {block.get('name')}: {' '.join(arg.split())[:200]}"


def extract(rows: list[dict]) -> str:
    start = max(
        (i for i, r in enumerate(rows) if r.get("isCompactSummary")), default=-1
    )
    parts, edited = [], []
    if start >= 0:
        summary = "\n".join(_texts((rows[start].get("message") or {}).get("content")))
        parts.append(f"COMPACTED EARLIER PART:\n{summary.strip()}")
    for i, row in enumerate(rows):
        content = (row.get("message") or {}).get("content")
        if row.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict) or b.get("name") not in EDIT_TOOLS:
                    continue
                path = (b.get("input") or {}).get("file_path")
                if path and path not in edited:
                    edited.append(path)
        if i <= start:
            continue
        parts += [f"USER: {t}" for t in _asks(row)]
        if row.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and b.get("text", "").strip():
                    parts.append(f"ASSISTANT: {b['text'].strip()}")
                # transcripts drop many text blocks; the thinking often holds the finding
                elif b.get("type") == "thinking" and b.get("thinking", "").strip():
                    thought = b["thinking"].strip()[:THINKING_CHARS]
                    parts.append(f"ASSISTANT (thinking): {thought}")
                elif b.get("type") == "tool_use":
                    parts.append(_tool_line(b))
    if not any(p.startswith(("USER:", "ASSISTANT:", "COMPACTED")) for p in parts):
        return ""
    if edited:
        parts.append("EDITED FILES:\n" + "\n".join(edited))
    text = "\n\n".join(parts)
    if len(text) > EXTRACT_MAX:
        text = (
            text[:EXTRACT_HEAD]
            + "\n\n[... middle dropped ...]\n\n"
            + text[-(EXTRACT_MAX - EXTRACT_HEAD) :]
        )
    return text


def handoff_path(cwd: str, sid: str, now: datetime) -> Path:
    name = f"{now:%Y%m%d_%H%M%S}_{sid[:8]}.md"
    here, home = Path(cwd or os.getcwd()).resolve(), Path.home().resolve()
    for d in (here, *here.parents):
        if d == home:
            break
        if (d / ".giantmem").is_dir():
            return d / ".giantmem" / "handoff-clear" / name
    return ARCHIVE / name


def summarize(prompt: str) -> str:
    binary = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
    # no setting sources: the child loads no CLAUDE.md and runs no hooks
    args = [
        binary,
        "-p",
        "--model",
        "sonnet",
        "--output-format",
        "text",
        "--no-session-persistence",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--tools",
        "",
        "--setting-sources",
        "",
        "--system-prompt",
        "You write handoff notes between Claude Code sessions.",
    ]
    try:
        proc = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=SUMMARY_TIMEOUT,
            env=dict(os.environ, GIANTMEM_SUMMARY_CHILD="1"),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def write_handoff(sid: str, transcript_path: str, out: Path) -> None:
    body = extract(load(transcript_path))
    try:
        rules = INSTRUCTIONS.read_text(encoding="utf-8").strip()
    except OSError:
        rules = ""
    note = summarize(
        f"{PROMPT}{rules}\n\nEnd with a `## Start here` section: the next concrete step, "
        f"or `none` if the work finished.\n\n<session>\n{body}\n</session>\n"
    )
    if not note:
        note = f"Summarizer failed. Tail of the transcript extract:\n\n{body[-FALLBACK_TAIL:]}"
    giantmem = out.parent.parent
    repo = giantmem.parent.name if giantmem.name == ".giantmem" else "none"
    text = "\n".join(
        [
            "---",
            "type: handoff",
            "status: ready",
            f"repo: {repo}",
            "lifecycle: candidate",
            f"session: {sid}",
            f"created: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            "---",
            "",
            f"# /clear handoff: {sid[:8]}",
            "",
            f"Full transcript: `claude --resume {sid}`",
            "",
            note,
            "",
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)


def spawn(sid: str, transcript_path: str, out: Path) -> None:
    # detached: the summarizer outlives this hook's timeout
    subprocess.Popen(  # pylint: disable=consider-using-with
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--handoff",
            sid,
            transcript_path,
            str(out),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def notice(sid: str, rows: list[dict], out: Path) -> str:
    asks = [" ".join(a.split())[:200] for r in rows for a in _asks(r)][-ASKS:]
    lines = [
        "<system-reminder>",
        (
            f"/clear handoff: this process just cleared session {sid}. A background job is "
            f"writing its handoff to {out} (ready in about a minute). Read it when the next "
            f"ask continues that work; otherwise ignore it. `claude --resume {sid}` restores "
            "the full transcript."
        ),
    ]
    if asks:
        lines += ["", "last asks:"] + [f"- {a}" for a in asks]
    lines.append("</system-reminder>")
    return json.dumps(
        {
            "systemMessage": f"handoff for cleared session {sid[:8]}: {out}",
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n".join(lines),
            },
        }
    )


def main() -> None:
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT", "cli").startswith("sdk"):
        return
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    proc = claude_proc()
    if proc is None:
        return
    pid, lstart = proc
    marker = MARKER_DIR / f"claude-clear-capsule-{pid}.json"
    try:
        prev = json.loads(marker.read_text())
    except (OSError, ValueError):
        prev = {}
    sid = data.get("session_id", "")
    try:
        marker.write_text(
            json.dumps(
                {
                    "session_id": sid,
                    "transcript_path": data.get("transcript_path", ""),
                    "lstart": lstart,
                }
            )
        )
    except OSError:
        pass
    # a reused pid leaves a marker from a dead process; its start time differs
    if data.get("source") != "clear" or prev.get("lstart") != lstart:
        return
    if prev.get("session_id") in (None, "", sid):
        return
    old, transcript = prev["session_id"], prev.get("transcript_path", "")
    rows = load(transcript)
    if not extract(rows):
        return
    out = handoff_path(data.get("cwd", ""), old, datetime.now().astimezone())
    spawn(old, transcript, out)
    print(notice(old, rows, out))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--handoff"] and len(sys.argv) == 5:
        write_handoff(sys.argv[2], sys.argv[3], Path(sys.argv[4]))
    else:
        main()
