#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse

RUNNING = {
    "created",
    "pending",
    "running",
    "preparing",
    "waiting_for_resource",
    "scheduled",
}


def project_from_remote(url):
    m = re.match(
        r"^(?:[a-z+]+://)?(?:[^@/]+@)?([^/:]+)(?::\d+)?[:/](.+?)(?:\.git)?/?$",
        url.strip(),
    )
    return (m.group(1), m.group(2)) if m else (None, None)


def verdict(mr):
    pipe = mr.get("head_pipeline") or {}
    status = pipe.get("status")
    merge = mr.get("detailed_merge_status") or ""
    if mr.get("has_conflicts") or merge == "conflict":
        return "conflicts", "bad"
    if status in ("failed", "canceled"):
        return "pipe:failed", "bad"
    if merge == "need_rebase":
        return "rebase", "bad"
    if status in RUNNING:
        return "pipe:running", "wait"
    if not status:
        return "no pipe", "wait"
    if pipe.get("sha") and pipe["sha"] != mr.get("sha"):
        return "pipe:stale", "wait"
    if mr.get("draft") or merge == "draft_status":
        return "draft", "wait"
    if merge == "discussions_not_resolved":
        return "threads", "wait"
    if merge in ("not_approved", "requested_changes"):
        return "approval", "wait"
    if merge == "mergeable":
        return "GREEN", "ok"
    return merge or status, "wait"


def api(host, path):
    r = subprocess.run(
        ["glab", "api", "--hostname", host, path],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return json.loads(r.stdout)


def write_json(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def main():
    repo, branch, out = sys.argv[1:4]
    remote = subprocess.run(
        ["git", "-C", repo, "remote", "get-url", "origin"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout
    host, project = project_from_remote(remote)
    if host is None or project is None or "gitlab" not in host:
        write_json(out, {})
        return
    enc = urllib.parse.quote(project, safe="")
    src = urllib.parse.quote(branch, safe="")
    try:
        found = api(
            host,
            f"projects/{enc}/merge_requests?source_branch={src}&state=opened&per_page=1",
        )
        mr = (
            api(host, f"projects/{enc}/merge_requests/{found[0]['iid']}")
            if found
            else None
        )
    except (RuntimeError, subprocess.TimeoutExpired, ValueError, OSError):
        # keep the last good read; the statusline ages it out
        return
    if mr is None:
        write_json(out, {})
        return
    tag, level = verdict(mr)
    write_json(out, {"iid": mr["iid"], "tag": tag, "level": level})


if __name__ == "__main__":
    main()
