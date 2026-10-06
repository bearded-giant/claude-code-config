#!/usr/bin/env python3
import argparse
import datetime
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

AREAS = [
    "auth",
    "ai-tooling",
    "migration",
    "platform",
    "infra",
    "dev-process",
    "dev-tools",
    "personal",
]


def vault():
    return Path(os.environ.get("OBSIDIAN_VAULT", "~/Recharge-Notes")).expanduser()


def slug(title):
    s = re.sub(r"[^A-Za-z0-9-]", "", title.replace(" ", "-")).lower()
    return re.sub(r"-+", "-", s).strip("-")


def git_project(cwd):
    # worktree layouts like ~/dev/python/cc-wt/stage resolve to "cc"; pass --project when that is too terse
    try:
        common = subprocess.run(
            [
                "git",
                "-C",
                cwd,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""
    name = Path(common).parent.name
    return re.sub(r"(-wt)?(--bare)?$", "", name)


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def unique_path(area_dir, base, created):
    path = area_dir / f"{base}.md"
    if not path.exists():
        return path
    path = area_dir / f"{base}-{created[:10]}.md"
    n = 2
    while path.exists():
        path = area_dir / f"{base}-{created[:10]}-{n}.md"
        n += 1
    return path


def cmd_new(a):
    body = (
        Path(a.body_file).read_text(encoding="utf-8")
        if a.body_file
        else sys.stdin.read()
    )
    body = body.strip()
    created = a.created or now_iso()
    area_dir = vault() / "areas" / a.area
    area_dir.mkdir(parents=True, exist_ok=True)
    path = unique_path(area_dir, slug(a.title), created)
    tags = ["claude"] + [t.strip() for t in (a.tags or "").split(",") if t.strip()]
    project = a.project if a.project is not None else git_project(os.getcwd())
    heading = "" if body.startswith("# ") else f"# {a.title}\n\n"
    fm = "\n".join(
        [
            "---",
            f"id: {path.stem}",
            "aliases: []",
            f"tags: [{', '.join(tags)}]",
            f"area: {a.area}",
            f"project: {project}" if project else 'project: ""',
            f"created: {created}",
            "---",
        ]
    )
    path.write_text(f"{fm}\n\n{heading}{body}\n", encoding="utf-8")
    print(path)
    return path


def parse_fm(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    fm, cur = {}, None
    for line in text[4:end].splitlines():
        if line.startswith("-") or line.startswith("  -"):
            if cur:
                fm[cur].append(line.split("-", 1)[1].strip().strip('"'))
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        cur, v = k.strip(), v.strip()
        fm[cur] = (
            re.findall(r"[\w./-]+", v)
            if v.startswith("[")
            else ([v.strip('"')] if v else [])
        )
    m = re.search(r"^# (.+)$", text[end:], re.M)
    fm["title"] = [m.group(1) if m else path.stem]
    return fm


def cmd_list(a):
    cutoff = ""
    if a.since:
        cutoff = (datetime.date.today() - datetime.timedelta(days=a.since)).isoformat()
    rows = []
    for p in sorted((vault() / "areas").rglob("*.md")):
        if p.stem == "index":
            continue
        fm = parse_fm(p)
        if not fm:
            continue

        def first(k):
            return (fm.get(k) or [""])[0]

        if a.area and first("area") != a.area:
            continue
        if a.project and first("project") != a.project:
            continue
        if a.tag and a.tag not in fm.get("tags", []):
            continue
        if cutoff and first("created")[:10] < cutoff:
            continue
        rows.append(
            (
                first("created"),
                first("area"),
                first("project"),
                str(p.relative_to(vault())),
                first("title"),
            )
        )
    rows.sort(reverse=True)
    for r in rows:
        print(" | ".join(r))
    return rows


def self_test():
    with tempfile.TemporaryDirectory() as d:
        os.environ["OBSIDIAN_VAULT"] = d

        def ns(**kw):
            return argparse.Namespace(
                **{
                    "body_file": None,
                    "created": None,
                    "tags": None,
                    "project": "proj",
                    **kw,
                }
            )

        sys.stdin = io.StringIO("")
        p1 = cmd_new(
            ns(
                title="Redis Keys & TTLs",
                area="auth",
                tags="redis, ttl",
                created="2026-09-01T10:00:00-07:00",
            )
        )
        assert p1.name == "redis-keys-ttls.md", p1
        text = p1.read_text()
        assert text.startswith(
            "---\nid: redis-keys-ttls\naliases: []\ntags: [claude, redis, ttl]\narea: auth\nproject: proj\ncreated: 2026-09-01T10:00:00-07:00\n---\n\n# Redis Keys & TTLs\n"
        ), text
        p2 = cmd_new(
            ns(
                title="Redis Keys & TTLs",
                area="auth",
                created="2026-09-02T10:00:00-07:00",
            )
        )
        assert p2.name == "redis-keys-ttls-2026-09-02.md", p2
        p3 = cmd_new(
            ns(
                title="Redis Keys & TTLs",
                area="auth",
                created="2026-09-02T11:00:00-07:00",
            )
        )
        assert p3.name == "redis-keys-ttls-2026-09-02-2.md", p3
        blk = Path(d) / "areas" / "infra" / "block.md"
        blk.parent.mkdir(parents=True)
        blk.write_text(
            encoding="utf-8",
            data='---\nid: block\naliases: []\ntags:\n  - claude\n  - es\narea: infra\nproject: ""\ncreated: 2026-09-03T00:00:00-07:00\n---\n\n# Block Form\n',
        )
        rows = cmd_list(
            argparse.Namespace(area=None, project=None, tag="es", since=None)
        )
        assert [r[4] for r in rows] == ["Block Form"], rows
        rows = cmd_list(
            argparse.Namespace(area="auth", project=None, tag=None, since=None)
        )
        assert (
            len(rows) == 3
            and rows[0][3] == "areas/auth/redis-keys-ttls-2026-09-02-2.md"
        ), rows
        rows = cmd_list(
            argparse.Namespace(area=None, project="proj", tag="ttl", since=None)
        )
        assert [r[3] for r in rows] == ["areas/auth/redis-keys-ttls.md"], rows
    print("ok")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="note.py")
    ap.add_argument("--test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    n = sub.add_parser("new")
    n.add_argument("--title", required=True)
    n.add_argument("--area", required=True, choices=AREAS)
    n.add_argument("--project")
    n.add_argument("--tags", help="comma separated")
    n.add_argument("--created", help="ISO 8601, default now")
    n.add_argument("--body-file", help="default stdin")
    l = sub.add_parser("list")
    l.add_argument("--area", choices=AREAS)
    l.add_argument("--project")
    l.add_argument("--tag")
    l.add_argument("--since", type=int, help="days")
    a = ap.parse_args(argv)
    if a.test:
        return self_test()
    if a.cmd == "new":
        return cmd_new(a)
    if a.cmd == "list":
        return cmd_list(a)
    ap.print_help()


if __name__ == "__main__":
    main()
