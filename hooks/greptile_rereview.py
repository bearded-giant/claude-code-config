#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROTECTED = {"main", "master", "stage", "HEAD"}
PUSH_RE = re.compile(r"\bgit\s+(?:-C\s+(\S+)\s+)?push\b")
CD_RE = re.compile(r"(?:^|[;&|]\s*)cd\s+(\S+)\s*&&[^;|]*\bgit\s+(?:-C\s+\S+\s+)?push\b")
SUMMARY_SHA_RE = re.compile(r"/commit/([0-9a-f]{7,40})")


def push_dir(command, cwd):
    m = PUSH_RE.search(command)
    if not m:
        return None
    target = m.group(1)
    if not target:
        cd = CD_RE.search(command)
        target = cd.group(1) if cd else None
    if not target:
        return cwd
    p = Path(target.strip("'\"")).expanduser()
    return str(p if p.is_absolute() else Path(cwd) / p)


def pushes_branch(command, branch):
    m = PUSH_RE.search(command)
    if not m:
        return False
    rest = command[m.end():]
    rest = re.split(r"&&|\|\||[;|]", rest, maxsplit=1)[0]
    try:
        args = shlex.split(rest)
    except ValueError:
        return False
    if any(a in ("--tags", "--delete", "-d", "--mirror") for a in args):
        return False
    refs = [a for a in args if not a.startswith("-")][1:]
    if not refs:
        return True
    return any(r.split(":")[0] in (branch, "HEAD") for r in refs)


def _ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _run(args, cwd, timeout=15):
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _git(top, *args):
    return _run(["git", "-C", top, *args], top)


def already_requested(top, iid, head, head_time):
    raw = _run(["glab", "api", f"projects/:id/merge_requests/{iid}/notes?sort=desc&order_by=created_at&per_page=100"], top)
    try:
        notes = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return True
    for n in notes:
        body = n.get("body", "")
        if "greptile_summary" in body:
            shas = SUMMARY_SHA_RE.findall(body)
            if shas and head.startswith(shas[-1]):
                return True
        if body.strip().startswith("@greptile review") and _ts(n["created_at"]) >= head_time:
            return True
    return False


def request_review(data):
    command = data.get("tool_input", {}).get("command", "")
    d = push_dir(command, data.get("cwd") or os.getcwd())
    if not d:
        return None
    top = _git(d, "rev-parse", "--show-toplevel")
    if not top or not (Path(top, ".greptile").is_dir() or Path(top, "greptile.json").exists()):
        return None
    if "gitlab" not in _git(top, "remote", "get-url", "origin"):
        return None
    branch = _git(top, "rev-parse", "--abbrev-ref", "HEAD")
    if branch in PROTECTED or not pushes_branch(command, branch):
        return None
    head = _git(top, "rev-parse", "HEAD")
    if not head or head != _git(top, "rev-parse", "@{u}"):
        return None
    try:
        mrs = json.loads(_run(["glab", "mr", "list", f"--source-branch={branch}", "-F", "json"], top) or "[]")
    except json.JSONDecodeError:
        return None
    if len(mrs) != 1:
        return None
    iid = mrs[0]["iid"]
    # gitlab registers a push a few seconds late; a request before that reviews the old head
    for _ in range(8):
        try:
            if json.loads(_run(["glab", "mr", "view", str(iid), "-F", "json"], top) or "{}").get("sha") == head:
                break
        except json.JSONDecodeError:
            pass
        time.sleep(2)
    else:
        return None
    if already_requested(top, iid, head, _ts(_git(top, "log", "-1", "--format=%cI"))):
        return None
    _run(["glab", "mr", "note", str(iid), "-m", "@greptile review"], top)
    return (
        f"greptile_rereview hook posted `@greptile review` on MR !{iid} for head {head[:8]}. "
        "Greptile reviews only on MR open, so every later push needs this request; it is done, do not post another."
    )


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("tool_name") != "Bash":
            return
        msg = request_review(data)
    except Exception:  # pylint: disable=broad-exception-caught
        return
    if msg:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))


if __name__ == "__main__":
    main()
