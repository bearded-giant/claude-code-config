#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://recharge.atlassian.net"
FIELDS = "summary,status,priority,issuetype,labels,created,updated,reporter,assignee,description,comment,attachment"
KEY_RE = re.compile(r"([A-Za-z][A-Za-z0-9]+-\d+)")


def key_of(ref):
    m = KEY_RE.search(ref)
    if not m:
        sys.exit(f"no ticket key in {ref!r}")
    return m.group(1).upper()


def creds():
    cfg = Path("~/.config/gitlab-monitor/config.json").expanduser()
    email = os.environ.get("JIRA_EMAIL")
    if not email and cfg.exists():
        email = json.loads(cfg.read_text()).get("jira", {}).get("email")
    token = os.environ.get("JIRA_API_TOKEN")
    tok = Path("~/.config/gitlab-monitor/jira_token").expanduser()
    if not token and tok.exists():
        token = tok.read_text().strip()
    if not (email and token):
        sys.exit(
            "jira auth missing: JIRA_EMAIL/JIRA_API_TOKEN or the gitlab-monitor jira config"
        )
    return email, token


def fetch(url, auth, raw=False):
    basic = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {basic}",
            "Accept": "*/*" if raw else "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if raw else json.load(r)


def name(v):
    return (v or {}).get("displayName") or (v or {}).get("name") or ""


def render(issue, attachments):
    f = issue["fields"]
    key = issue["key"]
    out = [
        f"# {key}: {f.get('summary', '')}",
        "",
        f"- url: {BASE}/browse/{key}",
        f"- type: {name(f.get('issuetype'))} | status: {name(f.get('status'))} | priority: {name(f.get('priority'))}",
        f"- labels: {', '.join(f.get('labels') or [])}",
        f"- reporter: {name(f.get('reporter'))} | assignee: {name(f.get('assignee')) or 'unassigned'}",
        f"- created: {f.get('created', '')} | updated: {f.get('updated', '')}",
        "",
        "## Description",
        "",
        f.get("description") or "(empty)",
    ]
    comments = (f.get("comment") or {}).get("comments") or []
    out += ["", f"## Comments ({len(comments)})"]
    for c in comments:
        out += [
            "",
            f"### {name(c.get('author'))} · {c.get('created', '')}",
            "",
            c.get("body") or "",
        ]
    out += ["", f"## Attachments ({len(attachments)})"]
    out += [
        f"- {a['filename']} ({a['size']} bytes) {a.get('path') or '(not downloaded)'}"
        for a in attachments
    ]
    return "\n".join(out) + "\n"


def download(attachments, out_dir, auth):
    out_dir.mkdir(parents=True, exist_ok=True)
    for a in attachments:
        path = out_dir / Path(a["filename"]).name
        if not path.exists():
            path.write_bytes(fetch(a["content"], auth, raw=True))
        a["path"] = str(path)
    return attachments


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ticket.py")
    ap.add_argument("ref", nargs="?", help="ticket key or Jira URL")
    ap.add_argument("--out", help="download attachments into <out>/<KEY>/")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args(argv)
    if a.test:
        return self_test()
    if not a.ref:
        ap.error("ref required")
    key = key_of(a.ref)
    auth = creds()
    issue = fetch(f"{BASE}/rest/api/2/issue/{key}?fields={FIELDS}", auth)
    attachments = issue["fields"].get("attachment") or []
    if a.out:
        download(attachments, Path(a.out).expanduser() / key, auth)
    sys.stdout.write(render(issue, attachments))


def self_test():
    assert key_of("https://recharge.atlassian.net/browse/pe-1526") == "PE-1526"
    assert key_of("SFE-5864 ") == "SFE-5864"
    issue = {
        "key": "PE-1",
        "fields": {
            "summary": "s",
            "status": {"name": "Backlog"},
            "priority": {"name": "High"},
            "issuetype": {"name": "Vulnerability"},
            "labels": ["a", "b"],
            "reporter": {"displayName": "R"},
            "assignee": None,
            "created": "c",
            "updated": "u",
            "description": "desc",
            "comment": {
                "comments": [
                    {"author": {"displayName": "A"}, "created": "t", "body": "hi"}
                ]
            },
        },
    }
    md = render(
        issue,
        [
            {"filename": "x.pdf", "size": 3, "path": "/tmp/x.pdf"},
            {"filename": "y.pdf", "size": 4},
        ],
    )
    assert md.startswith(
        "# PE-1: s\n\n- url: https://recharge.atlassian.net/browse/PE-1\n"
    ), md
    assert "status: Backlog | priority: High" in md and "assignee: unassigned" in md, md
    assert "## Comments (1)\n\n### A · t\n\nhi\n" in md, md
    assert (
        "- x.pdf (3 bytes) /tmp/x.pdf\n- y.pdf (4 bytes) (not downloaded)\n" in md
    ), md
    print("ok")


if __name__ == "__main__":
    main()
