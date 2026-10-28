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
CD_RE = re.compile(r"(?:^|[;&|(]\s*)cd\s+(\S+)")
SUMMARY_SHA_RE = re.compile(r"/commit/([0-9a-f]{7,40})")


def push_dir(command, cwd):
    m = PUSH_RE.search(command)
    if not m:
        return None
    # each cd resolves against the directory the previous one left: `cd sub && ...; cd ../..`
    d = cwd
    for target in [*CD_RE.findall(command[: m.start()]), *([m.group(1)] if m.group(1) else [])]:
        p = Path(target.strip("'\"")).expanduser()
        d = os.path.normpath(p if p.is_absolute() else Path(d) / p)
    return d


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


def mr_notes(top, iid):
    raw = _run(["glab", "api", f"projects/:id/merge_requests/{iid}/notes?sort=desc&order_by=created_at&per_page=100"], top)
    try:
        return json.loads(raw or "[]")
    except json.JSONDecodeError:
        return None


# a repo can be reviewed by greptile with no .greptile/ in the tree; its approvals on the MR say so
def greptile_reviews(notes):
    return any(n.get("author", {}).get("username") == "greptile" for n in notes)


def already_requested(notes, head, head_time):
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
    if not top:
        return None
    has_config = Path(top, ".greptile").is_dir() or Path(top, "greptile.json").exists()
    branch = _git(top, "rev-parse", "--abbrev-ref", "HEAD")
    if branch in PROTECTED or not pushes_branch(command, branch):
        return None
    head = _git(top, "rev-parse", "HEAD")
    if not head:
        return None
    github = request_github_review(top, branch, head)
    if "gitlab" not in _git(top, "remote", "get-url", "origin"):
        return github
    if head != _git(top, "rev-parse", "@{u}"):
        return github
    try:
        mrs = json.loads(_run(["glab", "mr", "list", f"--source-branch={branch}", "-F", "json"], top) or "[]")
    except json.JSONDecodeError:
        return None
    if len(mrs) != 1:
        return None
    iid = mrs[0]["iid"]
    notes = mr_notes(top, iid)
    if notes is None or not (has_config or greptile_reviews(notes)):
        return None
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
    if already_requested(notes, head, _ts(_git(top, "log", "-1", "--format=%cI"))):
        return None
    _run(["glab", "mr", "note", str(iid), "-m", "@greptile review"], top)
    msg = (
        f"greptile_rereview hook posted `@greptile review` on MR !{iid} for head {head[:8]}. "
        "Greptile reviews only on MR open, so every later push needs this request; it is done, do not post another."
    )
    return f"{msg} {github}" if github else msg


def request_github_review(top, branch, head):
    # greptile reviews a github pr on open only; a `@greptile review` comment re-reviews the pushed head
    url = _git(top, "remote", "get-url", "github")
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url or "")
    if not m:
        return None
    repo = m.group(1)
    try:
        prs = json.loads(_run(["gh", "pr", "list", "-R", repo, "--head", branch, "--json", "number,headRefOid"], top) or "[]")
    except json.JSONDecodeError:
        return None
    if len(prs) != 1 or prs[0].get("headRefOid") != head:
        return None
    number = prs[0]["number"]
    try:
        reviews = json.loads(_run(["gh", "api", f"repos/{repo}/pulls/{number}/reviews"], top) or "[]")
    except json.JSONDecodeError:
        return None
    if any(r.get("user", {}).get("login", "").startswith("greptile") and r.get("commit_id") == head for r in reviews):
        return None
    _run(["gh", "pr", "comment", str(number), "-R", repo, "--body", "@greptile review"], top)
    return f"Also posted `@greptile review` on GitHub PR {repo}#{number} for head {head[:8]}; do not post another."


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
