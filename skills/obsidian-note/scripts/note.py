#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
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
    "security",
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


DOMAIN_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_KEYS = ("artifact", "artifact_rev", "artifact_account")
# keep in step with LABEL_OVERRIDES in hooks/usage-fetch.py so labels match the statusline
ACCOUNT_LABELS = {"recharge, inc": "rc-inc", "recharge, team": "rc-team"}
SLOT_LABELS = {"team": "rc-team", "enterprise": "rc-inc"}
STATUSES = ("new", "ready", "blocked", "in_progress", "in_review", "done", "wont_fix")


def domain_arg(v):
    if not DOMAIN_RE.match(v):
        raise argparse.ArgumentTypeError(f"domain must be lowercase-hyphenated: {v!r}")
    return v


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def key_arg(v):
    v = v.upper()
    if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", v):
        raise argparse.ArgumentTypeError(f"ticket key must look like PE-1234: {v!r}")
    return v


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
    area_dir = vault() / "areas" / a.area / a.domain
    area_dir.mkdir(parents=True, exist_ok=True)
    key = getattr(a, "key", None)
    base = slug(a.title)
    if key:
        rest = re.sub(rf"^{re.escape(key)}\b[:\s-]*", "", a.title, flags=re.IGNORECASE)
        base = f"{key}-{slug(rest)}"
    path = unique_path(area_dir, base, created)
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
        ]
        + (
            [f"ticket: {key}", "rev: 1", f"modified: {created}", "status: new"]
            if key
            else []
        )
        + ["---"]
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
        if line.startswith(("-", "  -")):
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
    m = re.search(r"^# (.+)$", text[end:], re.MULTILINE)
    fm["title"] = [m.group(1) if m else path.stem]
    return fm


def domain_of(p):
    parts = p.relative_to(vault() / "areas").parts
    return parts[1] if len(parts) > 2 else ""


def cmd_domains(a):
    counts = {}
    for p in (vault() / "areas").rglob("*.md"):
        if p.stem == "index":
            continue
        key = (p.relative_to(vault() / "areas").parts[0], domain_of(p))
        counts[key] = counts.get(key, 0) + 1
    rows = sorted(k for k in counts if not a.area or k[0] == a.area)
    for area, dom in rows:
        print(f"{area}/{dom or '(none)'} | {counts[(area, dom)]}")
    return rows


def slot_tier():
    # the session's keychain slot holds its own token; ~/.claude.json names whichever session logged in last
    service = "Claude Code-credentials"
    slot = os.environ.get("CLAUDE_SECURESTORAGE_CONFIG_DIR")
    if slot:
        service += (
            "-"
            + hashlib.sha256(unicodedata.normalize("NFC", slot).encode()).hexdigest()[
                :8
            ]
        )
    try:
        raw = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        ).stdout
        return json.loads(raw)["claudeAiOauth"]["subscriptionType"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return ""


def claude_account():
    label = SLOT_LABELS.get(slot_tier())
    if label:
        return label
    cfg = Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~").expanduser() / ".claude.json"
    try:
        org = json.loads(cfg.read_text(encoding="utf-8"))["oauthAccount"][
            "organizationName"
        ]
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    key = org.strip().lower().rstrip(".")
    return ACCOUNT_LABELS.get(key) or ("skio" if "skio" in key else key)


def cmd_account(a):
    cur = claude_account()
    if not cur:
        sys.exit("no claude.ai login found; run /login")
    if a.note:
        owner = (parse_fm(Path(a.note).expanduser()) or {}).get("artifact_account")
        if owner and owner[0] != cur:
            sys.exit(
                f"artifact lives in {owner[0]}, this session is {cur}: open a {owner[0]} session"
                f" (~/.claude/skills/claude-artifact/scripts/from-note.sh --account {owner[0]} <note>)"
            )
    print(cur)
    return cur


def cache_file(note, rev):
    # same layout as cache() in hooks/artifact_gate.py, keyed by the page's source-note meta
    root = Path(
        os.environ.get("ARTIFACT_CACHE", "~/.local/share/claude-artifact")
    ).expanduser()
    try:
        rel = note.resolve().relative_to(vault().resolve())
    except ValueError:
        rel = Path(note.name)
    return root / rel.with_suffix("") / f"rev-{rev}.html"


def mirror_keys(account):
    key = "artifact_mirror_" + account.replace("-", "_")
    return key, key + "_rev"


def cmd_role(a):
    path = Path(a.note).expanduser()
    fm = parse_fm(path) or {}

    def first(k):
        return (fm.get(k) or [""])[0]

    me = a.account or claude_account()
    if not me:
        sys.exit("no claude.ai login found; run /login")
    rev, owner = first("artifact_rev"), first("artifact_account")
    if not first("artifact"):
        out = "new"
    elif not owner:
        out = f"unknown {rev}"
    elif owner == me:
        out = f"source {rev}"
    else:
        cached = cache_file(path, rev)
        mirrored = first(mirror_keys(me)[1]) or "0"
        out = f"mirror {mirrored} {rev} {cached if cached.exists() else '-'}"
    print(out)
    return out


def cmd_link(a):
    path = Path(a.note).expanduser()
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or text.find("\n---", 4) < 0:
        sys.exit(f"no frontmatter: {path}")
    end = text.find("\n---", 4)
    account = a.account or claude_account()
    if a.mirror:
        if not account:
            sys.exit("no claude.ai login found; run /login")
        if (parse_fm(path) or {}).get("artifact_account") == [account]:
            sys.exit(f"{account} holds the source artifact; link it without --mirror")
        keys, log = mirror_keys(account), f"mirror {account} {a.url}"
    else:
        keys, log = LINK_KEYS, a.log
    fm = [l for l in text[4:end].splitlines() if l.split(":", 1)[0].strip() not in keys]
    fm += [f"{keys[0]}: {a.url}", f"{keys[1]}: {a.rev}"]
    if account and not a.mirror:
        fm.append(f"artifact_account: {account}")
    body = text[end + 4 :].rstrip("\n")
    if log:
        head, sep, tail = body.partition("\n## Artifact revisions")
        cut = tail.find("\n## ")
        cut = len(tail) if cut < 0 else cut
        entries = tail[:cut].rstrip("\n") or "\n"
        rest = "\n" + tail[cut:] if cut < len(tail) else ""
        body = (
            head
            + (sep or "\n\n## Artifact revisions")
            + entries
            + f"\n- rev {a.rev} · {now_iso()} · {log}"
            + rest
        )
    path.write_text("---\n" + "\n".join(fm) + "\n---" + body + "\n", encoding="utf-8")
    print(path)
    return path


def split_fm(path):
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 4) if text.startswith("---\n") else -1
    if end < 0:
        sys.exit(f"no frontmatter: {path}")
    return text[4:end].splitlines(), text[end + 4 :].rstrip("\n")


def cmd_bump(a):
    path = Path(a.note).expanduser()
    fm, body = split_fm(path)
    keys = {l.split(":", 1)[0].strip(): i for i, l in enumerate(fm)}
    if "rev" not in keys:
        m = re.match(r"^([A-Za-z][A-Za-z0-9]+-\d+)-", path.stem)
        if not m:
            sys.exit(f"not a ticket note (no rev:): {path}")
        if "ticket" not in keys:
            fm.append(f"ticket: {m.group(1).upper()}")
        fm += ["rev: 1", "modified: "] + ([] if "status" in keys else ["status: new"])
        keys = {l.split(":", 1)[0].strip(): i for i, l in enumerate(fm)}
    rev = int(fm[keys["rev"]].split(":", 1)[1]) + 1
    fm[keys["rev"]] = f"rev: {rev}"
    fm[keys["modified"]] = f"modified: {now_iso()}"
    path.write_text("---\n" + "\n".join(fm) + "\n---" + body + "\n", encoding="utf-8")
    print(f"{path} rev {rev}")
    return rev


def cmd_status(a):
    path = Path(a.note).expanduser()
    fm, body = split_fm(path)
    keys = {l.split(":", 1)[0].strip(): i for i, l in enumerate(fm)}
    if "rev" not in keys:
        sys.exit(f"not a ticket note (no rev:): {path}")
    if "status" in keys:
        fm[keys["status"]] = f"status: {a.status}"
    else:
        fm.append(f"status: {a.status}")
    fm[keys["modified"]] = f"modified: {now_iso()}"
    path.write_text("---\n" + "\n".join(fm) + "\n---" + body + "\n", encoding="utf-8")
    print(f"{path} {a.status}")
    return a.status


def cmd_list(a):
    cutoff = ""
    if a.since:
        cutoff = (
            datetime.datetime.now().astimezone().date()
            - datetime.timedelta(days=a.since)
        ).isoformat()
    rows = []
    for p in sorted((vault() / "areas").rglob("*.md")):
        if p.stem == "index":
            continue
        fm = parse_fm(p)
        if not fm:
            continue

        def first(k, fm=fm):
            return (fm.get(k) or [""])[0]

        if a.area and first("area") != a.area:
            continue
        if a.domain and domain_of(p) != a.domain:
            continue
        if a.project and first("project") != a.project:
            continue
        if a.tag and a.tag not in fm.get("tags", []):
            continue
        if a.ticket and not (
            first("ticket").upper() == a.ticket.upper()
            or p.stem.lower().startswith(a.ticket.lower() + "-")
        ):
            continue
        if a.status and first("status") != a.status:
            continue
        if cutoff and first("created")[:10] < cutoff:
            continue
        rows.append(
            (
                first("created"),
                first("area"),
                domain_of(p),
                first("project"),
                str(p.relative_to(vault())),
                first("title"),
            )
            + ((first("status"),) if first("status") else ())
        )
    rows.sort(reverse=True)
    for r in rows:
        print(" | ".join(r))
    return rows


def self_test():
    with tempfile.TemporaryDirectory() as d:
        os.environ["OBSIDIAN_VAULT"] = d
        os.environ["CLAUDE_CONFIG_DIR"] = d
        os.environ["ARTIFACT_CACHE"] = str(Path(d, "cache"))

        def slot(tier):
            globals()["slot_tier"] = lambda: tier

        slot("")

        def login(org):
            Path(d, ".claude.json").write_text(
                json.dumps({"oauthAccount": {"organizationName": org}}),
                encoding="utf-8",
            )

        login("Recharge, Inc.")

        def ns(**kw):
            return argparse.Namespace(
                **{
                    "body_file": None,
                    "created": None,
                    "tags": None,
                    "project": "proj",
                    "domain": "sessions",
                    **kw,
                }
            )

        def lst(**kw):
            return cmd_list(
                argparse.Namespace(
                    **{
                        "area": None,
                        "domain": None,
                        "project": None,
                        "tag": None,
                        "since": None,
                        "ticket": None,
                        "status": None,
                        **kw,
                    }
                )
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
        assert p1 == Path(d) / "areas/auth/sessions/redis-keys-ttls.md", p1
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
        other = cmd_new(
            ns(
                title="Redis Keys & TTLs",
                area="auth",
                domain="tokens",
                created="2026-09-02T12:00:00-07:00",
            )
        )
        assert other == Path(d) / "areas/auth/tokens/redis-keys-ttls.md", other
        blk = Path(d) / "areas" / "infra" / "block.md"
        blk.parent.mkdir(parents=True)
        blk.write_text(
            encoding="utf-8",
            data='---\nid: block\naliases: []\ntags:\n  - claude\n  - es\narea: infra\nproject: ""\ncreated: 2026-09-03T00:00:00-07:00\n---\n\n# Block Form\n',
        )
        rows = lst(tag="es")
        assert [(r[2], r[5]) for r in rows] == [("", "Block Form")], rows
        rows = lst(area="auth", domain="sessions")
        assert (
            len(rows) == 3
            and rows[0][4] == "areas/auth/sessions/redis-keys-ttls-2026-09-02-2.md"
        ), rows
        rows = lst(project="proj", tag="ttl")
        assert [r[4] for r in rows] == ["areas/auth/sessions/redis-keys-ttls.md"], rows
        doms = cmd_domains(argparse.Namespace(area=None))
        assert doms == [("auth", "sessions"), ("auth", "tokens"), ("infra", "")], doms

        cmd_link(
            argparse.Namespace(
                note=str(p1),
                url="https://claude.ai/artifact/A",
                rev=1,
                log=None,
                account="rc-team",
                mirror=False,
            )
        )
        cmd_link(
            argparse.Namespace(
                note=str(p1),
                url="https://claude.ai/artifact/A",
                rev=2,
                log="split tokens out",
                account=None,
                mirror=False,
            )
        )
        text = p1.read_text()
        assert text.count("artifact: https://claude.ai/artifact/A\n") == 1, text
        assert (
            "artifact_rev: 2\nartifact_account: rc-inc\n---\n\n# Redis Keys & TTLs"
            in text
        ), text
        assert (
            text.rstrip().endswith("· split tokens out")
            and "## Artifact revisions\n\n- rev 2 · " in text
        ), text
        fm = parse_fm(p1) or {}
        assert fm["artifact_rev"] == ["2"] and fm["artifact_account"] == ["rc-inc"], fm
        assert text.count("artifact_account:") == 1, text
        assert cmd_account(argparse.Namespace(note=str(p1))) == "rc-inc"
        cmd_link(
            argparse.Namespace(
                note=str(p1),
                url="https://claude.ai/artifact/A",
                rev=2,
                log=None,
                account="skio",
                mirror=False,
            )
        )
        try:
            cmd_account(argparse.Namespace(note=str(p1)))
            raise AssertionError("account mismatch must exit")
        except SystemExit as e:
            assert "lives in skio" in str(e), e
        assert cmd_account(argparse.Namespace(note=str(p2))) == "rc-inc"
        for org, label in (
            ("Recharge, Team", "rc-team"),
            ("Skio Inc", "skio"),
            ("Acme", "acme"),
        ):
            login(org)
            assert claude_account() == label, (org, claude_account())
        for tier, label in (("team", "rc-team"), ("enterprise", "rc-inc")):
            slot(tier)
            assert claude_account() == label, (tier, claude_account())
        slot("")
        Path(d, ".claude.json").write_text("{}", encoding="utf-8")
        assert claude_account() == ""
        login("Recharge, Inc.")

        t1 = cmd_new(
            ns(
                title="PE-1526 review: mixed identity binding",
                area="security",
                domain="customcheckout",
                key="PE-1526",
                created="2026-09-04T10:00:00-07:00",
            )
        )
        assert (
            t1
            == Path(d)
            / "areas/security/customcheckout/PE-1526-review-mixed-identity-binding.md"
        ), t1
        text = t1.read_text()
        assert (
            "created: 2026-09-04T10:00:00-07:00\nticket: PE-1526\nrev: 1\nmodified: 2026-09-04T10:00:00-07:00\nstatus: new\n---"
            in text
        ), text
        assert "# PE-1526 review: mixed identity binding\n" in text, text
        legacy = Path(d) / "areas/auth/security/pe-1527-review-old.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(
            "---\nid: pe-1527-review-old\narea: auth\ncreated: 2026-09-05T00:00:00-07:00\n---\n\n# old\n",
            encoding="utf-8",
        )
        assert [r[4] for r in lst(ticket="pe-1526")] == [
            "areas/security/customcheckout/PE-1526-review-mixed-identity-binding.md"
        ]
        assert [r[4] for r in lst(ticket="PE-1527")] == [
            "areas/auth/security/pe-1527-review-old.md"
        ]
        assert cmd_bump(argparse.Namespace(note=str(t1))) == 2
        assert cmd_bump(argparse.Namespace(note=str(t1))) == 3
        text = t1.read_text()
        assert (
            "rev: 3\nmodified: 2" in text and "modified: 2026-09-04" not in text
        ), text
        assert "## Revisions" not in text and "status: new" in text, text
        assert lst(status="new")[0][6] == "new"
        assert cmd_status(argparse.Namespace(note=str(t1), status="ready")) == "ready"
        text = t1.read_text()
        assert "status: ready\n---" in text and text.count("status:") == 1, text
        assert "rev: 3\n" in text, text
        assert [r[4] for r in lst(status="ready")] == [
            "areas/security/customcheckout/PE-1526-review-mixed-identity-binding.md"
        ]
        assert lst(status="new") == []
        assert len(lst(area="auth", domain="sessions")[0]) == 6
        try:
            cmd_status(argparse.Namespace(note=str(p1), status="ready"))
            raise AssertionError("status on non-ticket note must exit")
        except SystemExit:
            pass
        try:
            cmd_bump(argparse.Namespace(note=str(p1)))
            raise AssertionError("bump on non-ticket note must exit")
        except SystemExit:
            pass
        assert cmd_bump(argparse.Namespace(note=str(legacy))) == 2
        text = legacy.read_text()
        assert (
            "created: 2026-09-05T00:00:00-07:00\nticket: PE-1527\nrev: 2\nmodified: 2"
            in text
        ), text
        assert "status: new\n---" in text and text.count("ticket:") == 1, text
        assert cmd_bump(argparse.Namespace(note=str(legacy))) == 3
        assert key_arg("pe-1526") == "PE-1526"
        try:
            key_arg("1526")
            raise AssertionError("bad key must fail")
        except argparse.ArgumentTypeError:
            pass

        login("Recharge, Inc.")
        r = cmd_new(
            ns(
                title="Mirror Me",
                area="ai-tooling",
                domain="mirrors",
                created="2026-10-30T10:00:00-04:00",
            )
        )

        def role(account=None):
            return cmd_role(argparse.Namespace(note=str(r), account=account))

        def link(url, rev, mirror=False, log=None):
            return cmd_link(
                argparse.Namespace(
                    note=str(r), url=url, rev=rev, log=log, account=None, mirror=mirror
                )
            )

        assert role() == "new"
        r.write_text(
            r.read_text().replace(
                "\n---\n\n#",
                "\nartifact: https://claude.ai/artifact/S\nartifact_rev: 2\n---\n\n#",
                1,
            )
        )
        assert role() == "unknown 2"
        link("https://claude.ai/artifact/S", 2)
        assert role() == "source 2"
        assert role("rc-team") == "mirror 0 2 -"
        cached = Path(d, "cache/areas/ai-tooling/mirrors/mirror-me/rev-2.html")
        cached.parent.mkdir(parents=True)
        cached.write_text("x", encoding="utf-8")
        assert role("rc-team") == f"mirror 0 2 {cached}"
        slot("team")
        assert role() == f"mirror 0 2 {cached}"
        link("https://claude.ai/artifact/M", 2, mirror=True)
        text = r.read_text()
        assert (
            "artifact: https://claude.ai/artifact/S\nartifact_rev: 2\nartifact_account: rc-inc\n"
            "artifact_mirror_rc_team: https://claude.ai/artifact/M\nartifact_mirror_rc_team_rev: 2\n---"
            in text
        ), text
        assert text.rstrip().endswith("· mirror rc-team https://claude.ai/artifact/M")
        assert role() == f"mirror 2 2 {cached}"
        slot("enterprise")
        link("https://claude.ai/artifact/S", 3, log="rewrote section 2")
        assert role() == "source 3"
        slot("team")
        assert role() == "mirror 2 3 -"
        link("https://claude.ai/artifact/M", 3, mirror=True)
        text = r.read_text()
        assert text.count("artifact_mirror_rc_team:") == 1, text
        assert "artifact_mirror_rc_team_rev: 3\n" in text, text
        assert "artifact_rev: 3\nartifact_account: rc-inc\n" in text, text
        assert role() == "mirror 3 3 -"
        slot("enterprise")
        try:
            link("https://claude.ai/artifact/M", 3, mirror=True)
            raise AssertionError("mirror link on the source account must exit")
        except SystemExit as e:
            assert "source" in str(e), e
        r.write_text(r.read_text() + "\n## Working notes\n\nscratch\n")
        link("https://claude.ai/artifact/S", 4, log="after a trailing section")
        text = r.read_text()
        assert text.endswith("\n\n## Working notes\n\nscratch\n"), text
        assert "· mirror rc-team https://claude.ai/artifact/M\n- rev 4 · " in text, text
        assert "· after a trailing section\n\n## Working notes" in text, text
        slot("")
    print("ok")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="note.py")
    ap.add_argument("--test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    n = sub.add_parser("new")
    n.add_argument("--title", required=True)
    n.add_argument("--area", required=True, choices=AREAS)
    n.add_argument("--domain", required=True, type=domain_arg)
    n.add_argument("--project")
    n.add_argument("--tags", help="comma separated")
    n.add_argument("--created", help="ISO 8601, default now")
    n.add_argument("--body-file", help="default stdin")
    n.add_argument(
        "--key",
        type=key_arg,
        help="ticket key; prefixes the filename, adds ticket/rev/modified",
    )
    l = sub.add_parser("list")
    l.add_argument("--area", choices=AREAS)
    l.add_argument("--domain")
    l.add_argument("--project")
    l.add_argument("--tag")
    l.add_argument("--since", type=int, help="days")
    l.add_argument(
        "--ticket", help="ticket key; matches ticket: or a key-prefixed filename"
    )
    l.add_argument("--status", choices=STATUSES)
    b = sub.add_parser("bump")
    b.add_argument("note")
    t = sub.add_parser("status")
    t.add_argument("note")
    t.add_argument("status", choices=STATUSES)
    d = sub.add_parser("domains")
    d.add_argument("--area", choices=AREAS)
    k = sub.add_parser("link")
    k.add_argument("note")
    k.add_argument("--url", required=True)
    k.add_argument("--rev", required=True, type=int)
    k.add_argument("--log", help="one line for the note's revision log")
    k.add_argument("--account", help="default: the logged-in claude.ai org label")
    k.add_argument(
        "--mirror",
        action="store_true",
        help="record a mirror of the source rev on this account; source keys untouched",
    )
    r = sub.add_parser(
        "role",
        help="new | source <rev> | unknown <rev> | mirror <mirror rev> <source rev> <cached html or ->",
    )
    r.add_argument("note")
    r.add_argument("--account", help="default: the logged-in claude.ai org label")
    c = sub.add_parser("account", help="print the logged-in claude.ai org label")
    c.add_argument(
        "note",
        nargs="?",
        help="exit non-zero when its artifact lives in another account",
    )
    a = ap.parse_args(argv)
    if a.test:
        return self_test()
    if a.cmd == "new":
        return cmd_new(a)
    if a.cmd == "list":
        return cmd_list(a)
    if a.cmd == "domains":
        return cmd_domains(a)
    if a.cmd == "link":
        return cmd_link(a)
    if a.cmd == "account":
        return cmd_account(a)
    if a.cmd == "role":
        return cmd_role(a)
    if a.cmd == "bump":
        return cmd_bump(a)
    if a.cmd == "status":
        return cmd_status(a)
    ap.print_help()


if __name__ == "__main__":
    main()
