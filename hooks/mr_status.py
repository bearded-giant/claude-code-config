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
GH_FAILED = {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "ERROR", "STARTUP_FAILURE"}
GH_FIELDS = "number,isDraft,mergeable,mergeStateStatus,reviewDecision,headRefOid,statusCheckRollup"


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


def github_verdict(pr):
    checks = pr.get("statusCheckRollup") or []
    state = pr.get("mergeStateStatus") or ""
    outcomes = {c.get("conclusion") or c.get("state") for c in checks}
    if pr.get("mergeable") == "CONFLICTING" or state == "DIRTY":
        return "conflicts", "bad"
    if outcomes & GH_FAILED:
        return "pipe:failed", "bad"
    if state == "BEHIND":
        return "rebase", "bad"
    if any(c.get("status") not in (None, "COMPLETED") or c.get("state") in ("PENDING", "EXPECTED") for c in checks):
        return "pipe:running", "wait"
    if not checks:
        return "no pipe", "wait"
    if pr.get("isDraft"):
        return "draft", "wait"
    if pr.get("reviewDecision") in ("REVIEW_REQUIRED", "CHANGES_REQUESTED"):
        return "approval", "wait"
    if state == "BLOCKED":
        return "threads", "wait"
    if state in ("CLEAN", "HAS_HOOKS"):
        return "GREEN", "ok"
    return state.lower() or "unknown", "wait"


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


def github_pr(project, branch):
    r = subprocess.run(
        ["gh", "pr", "list", "-R", project, "--head", branch, "--state", "open", "--limit", "1", "--json", GH_FIELDS],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    found = json.loads(r.stdout)
    return found[0] if found else None


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
    if host is None or project is None or not (host == "github.com" or "gitlab" in host):
        write_json(out, {})
        return
    try:
        if host == "github.com":
            pr = github_pr(project, branch)
            result = pr and {"iid": pr["number"], "host": "github", **dict(zip(("tag", "level"), github_verdict(pr)))}
        else:
            enc = urllib.parse.quote(project, safe="")
            src = urllib.parse.quote(branch, safe="")
            found = api(
                host,
                f"projects/{enc}/merge_requests?source_branch={src}&state=opened&per_page=1",
            )
            mr = api(host, f"projects/{enc}/merge_requests/{found[0]['iid']}") if found else None
            result = mr and {"iid": mr["iid"], **dict(zip(("tag", "level"), verdict(mr)))}
    except (RuntimeError, subprocess.TimeoutExpired, ValueError, OSError):
        # keep the last good read; the statusline ages it out
        return
    write_json(out, result or {})


if __name__ == "__main__":
    main()
