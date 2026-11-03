#!/usr/bin/env python3
import argparse
import base64
import datetime
import hashlib
import html
import importlib.util
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
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


def default_project(cwd):
    root = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not root:
        sys.exit(f"{cwd} is not in a git repo: pass --project")
    # same resolver as the handoff hooks, so a repo's notes and handoffs share one folder
    hook = Path(__file__).resolve().parents[3] / "hooks" / "doit_session_prime.py"
    spec = importlib.util.spec_from_file_location("doit_session_prime", hook)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.vault_project(root)


PROJECT_RE = re.compile(r"^[a-z0-9]+([.-][a-z0-9]+)*$")
LINK_KEYS = ("artifact", "artifact_rev", "artifact_account")
# keep in step with LABEL_OVERRIDES in hooks/usage-fetch.py so labels match the statusline
ACCOUNT_LABELS = {"recharge, inc": "rc-inc", "recharge, team": "rc-team"}
SLOT_LABELS = {"team": "rc-team", "enterprise": "rc-inc"}
STATUSES = ("new", "ready", "blocked", "in_progress", "in_review", "done", "wont_fix")
HTML_TEMPLATE = Path(__file__).resolve().parents[1] / "html-template" / "note.html"
# html notes carry the same yaml frontmatter inside a leading comment, so one parser serves both formats
HTML_FM = "<!--\n---\n"
FULL_PAGE_RE = re.compile(r"\s*<(!doctype|html)\b", re.IGNORECASE)
CONVERT_SKIP = {".git", ".obsidian", ".trash", "node_modules", "handoffs"}
MERMAID = (
    '<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"></script>\n'
    "<script>\n"
    "const cs = getComputedStyle(document.documentElement).colorScheme;\n"
    'const dark = cs === "dark" || (cs !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);\n'
    'mermaid.initialize({ startOnLoad: true, theme: dark ? "dark" : "default" });\n'
    "</script>"
)


def fm_span(text):
    start = (
        len(HTML_FM)
        if text.startswith(HTML_FM)
        else 4 if text.startswith("---\n") else -1
    )
    end = text.find("\n---", start) if start >= 0 else -1
    return (start, end) if end >= 0 else None


def project_arg(v):
    if not PROJECT_RE.match(v):
        raise argparse.ArgumentTypeError(f"project must be lowercase-hyphenated: {v!r}")
    return v


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def key_arg(v):
    v = v.upper()
    if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", v):
        raise argparse.ArgumentTypeError(f"ticket key must look like PE-1234: {v!r}")
    return v


def unique_path(area_dir, base, created, ext=".md"):
    path = area_dir / f"{base}{ext}"
    if not path.exists():
        return path
    path = area_dir / f"{base}-{created[:10]}{ext}"
    n = 2
    while path.exists():
        path = area_dir / f"{base}-{created[:10]}-{n}{ext}"
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
    project = a.project or default_project(os.getcwd())
    area_dir = vault() / "areas" / project
    area_dir.mkdir(parents=True, exist_ok=True)
    key = getattr(a, "key", None)
    base = slug(a.title)
    if key:
        rest = re.sub(rf"^{re.escape(key)}\b[:\s-]*", "", a.title, flags=re.IGNORECASE)
        base = f"{key}-{slug(rest)}"
    is_html = (a.body_file or "").lower().endswith((".html", ".htm"))
    path = unique_path(area_dir, base, created, ".html" if is_html else ".md")
    tags = ["claude"] + [t.strip() for t in (a.tags or "").split(",") if t.strip()]
    fm = "\n".join(
        [
            "---",
            f"id: {path.stem}",
            "aliases: []",
            f"tags: [{', '.join(tags)}]",
            f"area: {a.area}",
            f"project: {project}",
            f"created: {created}",
        ]
        + (
            [f"ticket: {key}", "rev: 1", f"modified: {created}", "status: new"]
            if key
            else []
        )
        + ["---"]
    )
    if is_html:
        page = body
        if not FULL_PAGE_RE.match(body):
            page = render_page(
                html.escape(a.title), f"{project} · {a.area}", created[:10], body
            )
        text = f"<!--\n{fm}\n-->\n{page.strip()}\n"
    else:
        heading = "" if body.startswith("# ") else f"# {a.title}\n\n"
        text = f"{fm}\n\n{heading}{body}\n"
    path.write_text(text, encoding="utf-8")
    print(path)
    return path


def render_page(title_html, eyebrow, created, body):
    doc_title = html.escape(html.unescape(re.sub(r"<[^>]+>", "", title_html)).strip())
    page = HTML_TEMPLATE.read_text(encoding="utf-8")
    for k, v in (
        ("{{DOCTITLE}}", doc_title),
        ("{{TITLE}}", title_html),
        ("{{EYEBROW}}", eyebrow),
        ("{{CREATED}}", created),
    ):
        page = page.replace(k, v)
    page = re.sub(r'\n\s*<p class="(eyebrow|meta)"></p>', "", page)
    return page.replace("{{BODY}}", body)


def data_uri(img, ref):
    rel = urllib.parse.unquote(html.unescape(ref))
    path = img.parent / rel
    if not path.is_file() and img.resolve().is_relative_to(vault().resolve()):
        # obsidian resolves a link that misses relatively by path suffix anywhere in the vault
        path = next(
            (p for p in vault().rglob(Path(rel).name) if p.as_posix().endswith(rel)),
            path,
        )
    if not path.is_file():
        print(f"warn {img}: image {ref} not found, left as a link", file=sys.stderr)
        return ref
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def md_to_html(src, force=False, dst=None):
    dst = dst or src.with_suffix(".html")
    if dst.exists() and not force:
        print(f"skip {dst} (exists)")
        return None
    text = src.read_text(encoding="utf-8")
    span = fm_span(text) if text.startswith("---\n") else None
    fm, body = (text[span[0] : span[1]], text[span[1] + 4 :]) if span else ("", text)
    body, sep, tail = body.partition("\n## Artifact revisions")
    cut = tail.find("\n## ")
    revs = sep + (tail if cut < 0 else tail[:cut])
    body += "" if cut < 0 else tail[cut:]
    frag = subprocess.run(
        [
            "pandoc",
            "-f",
            "gfm+wikilinks_title_after_pipe",
            "-t",
            "html5",
            "--wrap=none",
            "--syntax-highlighting=none",
        ],
        input=body,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>\n?", frag, re.DOTALL)
    title = h1.group(1) if h1 else html.escape(src.stem)
    if h1:
        frag = frag.replace(h1.group(0), "", 1)
    frag = frag.replace("<table>", '<div class="table-wrap"><table>')
    frag = frag.replace("</table>", "</table></div>")
    # mermaid parses innerHTML, so the <code> pandoc wraps around the source breaks it
    frag, diagrams = re.subn(
        r'<pre class="mermaid"><code>(.*?)</code></pre>',
        r'<pre class="mermaid">\1</pre>',
        frag,
        flags=re.DOTALL,
    )
    # obsidian renders the page from a blob url, so relative image paths never load
    frag = re.sub(
        r'(<img [^>]*src=")([^":]+)"',
        lambda m: f'{m.group(1)}{data_uri(src, m.group(2))}"',
        frag,
    )
    if src.resolve().is_relative_to(vault().resolve()):
        name = urllib.parse.quote(vault().name)
        frag = re.sub(
            r'<a href="([^"]*)" class="wikilink">',
            lambda m: f'<a href="obsidian://open?vault={name}&amp;file='
            f'{urllib.parse.quote(html.unescape(m.group(1)))}" class="wikilink">',
            frag,
        )
    if diagrams:
        frag += "\n" + MERMAID
    meta = {
        k.strip(): v.strip().strip('"')
        for k, _, v in (ln.partition(":") for ln in fm.splitlines())
        if v and not k.startswith((" ", "-"))
    }
    eyebrow = " · ".join(x for x in (meta.get("project"), meta.get("area")) if x)
    page = render_page(title, eyebrow, meta.get("created", "")[:10], frag.strip())
    if fm:
        head = f"{fm}\n---" + (f"\n{revs.rstrip()}" if revs else "")
        page = f"<!--\n---\n{head.replace('-->', '->')}\n-->\n{page}"
    dst.write_text(page.rstrip() + "\n", encoding="utf-8")
    print(f"{src} -> {dst}")
    return dst


def html_to_md(src, force=False, dst=None):
    dst = dst or src.with_suffix(".md")
    if dst.exists() and not force:
        print(f"skip {dst} (exists)")
        return None
    text = src.read_text(encoding="utf-8")
    fm, revs, page = "", "", text
    span = fm_span(text) if text.startswith(HTML_FM) else None
    if span:
        fm = text[span[0] : span[1]]
        revs, _, page = text[span[1] + 4 :].partition("\n-->")
    inner = re.search(r"<main\b[^>]*>(.*)</main>", page, re.DOTALL | re.IGNORECASE)
    body = inner.group(1) if inner else page
    head = re.search(r'<header class="masthead">.*?</header>', body, re.DOTALL)
    if head:
        body = body.replace(head.group(0), "", 1)
    body = re.sub(
        r"<(script|style)\b.*?</\1>", "", body, flags=re.DOTALL | re.IGNORECASE
    )
    if not re.search(r"<h1\b", body, re.IGNORECASE):
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", head.group(0) if head else "", re.DOTALL)
        doc = re.search(r"<title>(.*?)</title>", page, re.DOTALL | re.IGNORECASE)
        title = h1 or doc
        body = f"<h1>{title.group(1) if title else html.escape(src.stem)}</h1>\n{body}"
    # pandoc's gfm writer drops fence languages it cannot highlight, mermaid included
    diagrams = []

    def stash(m):
        diagrams.append(html.unescape(m.group(1)).strip())
        return f"<p>MERMAIDSLOT{len(diagrams) - 1}</p>"

    body = re.sub(r'<pre class="mermaid">(.*?)</pre>', stash, body, flags=re.DOTALL)
    body = re.sub(r"<summary>(.*?)</summary>", r"<p><strong>\1</strong></p>", body)
    body = body.replace(' class="wikilink"', "")
    md = subprocess.run(
        ["pandoc", "-f", "html-native_divs-native_spans", "-t", "gfm", "--wrap=none"],
        input=body,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    for i, src_text in enumerate(diagrams):
        md = md.replace(f"MERMAIDSLOT{i}", f"```mermaid\n{src_text}\n```", 1)

    def wikilink(m):
        target = urllib.parse.unquote(m.group(2))
        return f"[[{target}]]" if m.group(1) == target else f"[[{target}|{m.group(1)}]]"

    md = re.sub(
        r"\[([^\]]*)\]\(obsidian://open\?vault=[^&)]*&file=([^)\s]+)\)", wikilink, md
    )
    out = (f"---\n{fm}\n---\n\n" if fm else "") + md.strip() + "\n"
    if revs.strip():
        out += f"\n{revs.strip()}\n"
    dst.write_text(out, encoding="utf-8")
    print(f"{src} -> {dst}")
    return dst


def cmd_convert(a):
    if not shutil.which("pandoc"):
        sys.exit("pandoc not found: brew install pandoc")
    to_md = a.to == "md"
    exts = (".html", ".htm") if to_md else (".md", ".markdown")
    done, failed = [], 0
    for arg in a.paths:
        root = Path(arg).expanduser()
        if root.is_dir():
            files = sorted(
                p
                for p in root.rglob(f"*{exts[0]}")
                if not CONVERT_SKIP & set(p.relative_to(root).parts[:-1])
            )
        elif root.suffix.lower() in exts and root.is_file():
            files = [root]
        else:
            print(f"fail {root}: not a {exts[0]} file or directory", file=sys.stderr)
            failed += 1
            continue
        for f in files:
            dst = None
            if a.out_dir:
                rel = f.relative_to(root) if root.is_dir() else Path(f.name)
                dst = Path(a.out_dir).expanduser() / rel.with_suffix(f".{a.to}")
                dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                out = (html_to_md if to_md else md_to_html)(f, a.force, dst)
            except (subprocess.CalledProcessError, OSError, UnicodeDecodeError) as e:
                print(f"fail {f}: {getattr(e, 'stderr', '') or e}", file=sys.stderr)
                failed += 1
                continue
            if out:
                done.append(out)
    print(f"{len(done)} converted, {failed} failed")
    if failed:
        sys.exit(1)
    return done


def parse_fm(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    span = fm_span(text)
    if not span:
        return None
    start, end = span
    fm, cur = {}, None
    for line in text[start:end].splitlines():
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
    m = re.search(
        r"^# ([^\n]+)|<title>(.*?)</title>", text[end:], re.MULTILINE | re.DOTALL
    )
    title = m and (m.group(1) or html.unescape(" ".join(m.group(2).split())))
    fm["title"] = [title or path.stem]
    return fm


def project_of(p):
    parts = p.relative_to(vault() / "areas").parts
    return parts[0] if len(parts) > 1 else ""


def notes():
    areas = vault() / "areas"
    for p in sorted([*areas.rglob("*.md"), *areas.rglob("*.html")]):
        if p.stem != "areas-index" and "handoffs" not in p.relative_to(vault()).parts:
            yield p


def cmd_projects(_a):
    counts = {}
    for p in notes():
        counts[project_of(p)] = counts.get(project_of(p), 0) + 1
    rows = sorted(counts.items())
    for project, n in rows:
        print(f"{project} | {n}")
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


def cmd_link(a):
    path = Path(a.note).expanduser()
    text = path.read_text(encoding="utf-8")
    span = fm_span(text)
    if not span:
        sys.exit(f"no frontmatter: {path}")
    start, end = span
    account = a.account or claude_account()
    if getattr(a, "hub", False):
        keys = ("artifact_hub", "artifact_hub_rev")
        log = f"hub {a.url}" + (f" · {a.log}" if a.log else "")
    else:
        keys, log = LINK_KEYS, a.log
    fm = [
        l
        for l in text[start:end].splitlines()
        if l.split(":", 1)[0].strip() not in keys
    ]
    fm += [f"{keys[0]}: {a.url}", f"{keys[1]}: {a.rev}"]
    if account and keys == LINK_KEYS:
        fm.append(f"artifact_account: {account}")
    body, close, page = text[end + 4 :].rstrip("\n"), "", ""
    if start == len(HTML_FM):
        # html notes keep the revision log inside the metadata comment, out of the rendered page
        body, close, page = body.partition("\n-->")
        log = log and log.replace("-->", "->")
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
    path.write_text(
        text[:start] + "\n".join(fm) + "\n---" + body + close + page + "\n",
        encoding="utf-8",
    )
    print(path)
    return path


def split_fm(path):
    text = path.read_text(encoding="utf-8")
    span = fm_span(text)
    if not span:
        sys.exit(f"no frontmatter: {path}")
    start, end = span
    return text[:start], text[start:end].splitlines(), text[end + 4 :].rstrip("\n")


def cmd_bump(a):
    path = Path(a.note).expanduser()
    head, fm, body = split_fm(path)
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
    path.write_text(head + "\n".join(fm) + "\n---" + body + "\n", encoding="utf-8")
    print(f"{path} rev {rev}")
    return rev


def cmd_status(a):
    path = Path(a.note).expanduser()
    head, fm, body = split_fm(path)
    keys = {l.split(":", 1)[0].strip(): i for i, l in enumerate(fm)}
    if "rev" not in keys:
        sys.exit(f"not a ticket note (no rev:): {path}")
    if "status" in keys:
        fm[keys["status"]] = f"status: {a.status}"
    else:
        fm.append(f"status: {a.status}")
    fm[keys["modified"]] = f"modified: {now_iso()}"
    path.write_text(head + "\n".join(fm) + "\n---" + body + "\n", encoding="utf-8")
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
    for p in notes():
        fm = parse_fm(p)
        if not fm:
            continue

        def first(k, fm=fm):
            return (fm.get(k) or [""])[0]

        if a.area and first("area") != a.area:
            continue
        if a.project and project_of(p) != a.project:
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
                project_of(p),
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
                    **kw,
                }
            )

        def lst(**kw):
            return cmd_list(
                argparse.Namespace(
                    **{
                        "area": None,
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
        assert p1 == Path(d) / "areas/proj/redis-keys-ttls.md", p1
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
                project="other",
                created="2026-09-02T12:00:00-07:00",
            )
        )
        assert other == Path(d) / "areas/other/redis-keys-ttls.md", other
        handoff = Path(d) / "areas/proj/handoffs/main.md"
        handoff.parent.mkdir(parents=True)
        handoff.write_text(
            "---\ntype: handoff\nstatus: ready\ntags: [ttl]\n---\n", encoding="utf-8"
        )
        (Path(d) / "areas/areas-index.md").write_text(
            "---\nid: areas-index\ntags: [es]\n---\n\n# Areas\n", encoding="utf-8"
        )
        cwd = os.getcwd()
        os.chdir(d)
        try:
            cmd_new(ns(title="Loose", area="auth", project=None))
            raise AssertionError("no repo and no --project must exit")
        except SystemExit as e:
            assert "pass --project" in str(e), e
        finally:
            os.chdir(cwd)
        blk = Path(d) / "areas" / "infra" / "block.md"
        blk.parent.mkdir(parents=True)
        blk.write_text(
            encoding="utf-8",
            data='---\nid: block\naliases: []\ntags:\n  - claude\n  - es\narea: infra\nproject: ""\ncreated: 2026-09-03T00:00:00-07:00\n---\n\n# Block Form\n',
        )
        rows = lst(tag="es")
        assert [(r[2], r[4]) for r in rows] == [("infra", "Block Form")], rows
        rows = lst(project="proj")
        assert (
            len(rows) == 3
            and rows[0][3] == "areas/proj/redis-keys-ttls-2026-09-02-2.md"
        ), rows
        rows = lst(project="proj", tag="ttl")
        assert [r[3] for r in rows] == ["areas/proj/redis-keys-ttls.md"], rows
        projects = cmd_projects(argparse.Namespace())
        assert projects == [("infra", 1), ("other", 1), ("proj", 3)], projects

        cmd_link(
            argparse.Namespace(
                note=str(p1),
                url="https://claude.ai/artifact/A",
                rev=1,
                log=None,
                account="rc-team",
            )
        )
        cmd_link(
            argparse.Namespace(
                note=str(p1),
                url="https://claude.ai/artifact/A",
                rev=2,
                log="split tokens out",
                account=None,
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
                project="customcheckout",
                key="PE-1526",
                created="2026-09-04T10:00:00-07:00",
            )
        )
        assert (
            t1
            == Path(d) / "areas/customcheckout/PE-1526-review-mixed-identity-binding.md"
        ), t1
        text = t1.read_text()
        assert (
            "created: 2026-09-04T10:00:00-07:00\nticket: PE-1526\nrev: 1\nmodified: 2026-09-04T10:00:00-07:00\nstatus: new\n---"
            in text
        ), text
        assert "# PE-1526 review: mixed identity binding\n" in text, text
        legacy = Path(d) / "areas/recharge-auth/pe-1527-review-old.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(
            "---\nid: pe-1527-review-old\narea: auth\ncreated: 2026-09-05T00:00:00-07:00\n---\n\n# old\n",
            encoding="utf-8",
        )
        assert [r[3] for r in lst(ticket="pe-1526")] == [
            "areas/customcheckout/PE-1526-review-mixed-identity-binding.md"
        ]
        assert [r[3] for r in lst(ticket="PE-1527")] == [
            "areas/recharge-auth/pe-1527-review-old.md"
        ]
        assert cmd_bump(argparse.Namespace(note=str(t1))) == 2
        assert cmd_bump(argparse.Namespace(note=str(t1))) == 3
        text = t1.read_text()
        assert (
            "rev: 3\nmodified: 2" in text and "modified: 2026-09-04" not in text
        ), text
        assert "## Revisions" not in text and "status: new" in text, text
        assert lst(status="new")[0][5] == "new"
        assert cmd_status(argparse.Namespace(note=str(t1), status="ready")) == "ready"
        text = t1.read_text()
        assert "status: ready\n---" in text and text.count("status:") == 1, text
        assert "rev: 3\n" in text, text
        assert [r[3] for r in lst(status="ready")] == [
            "areas/customcheckout/PE-1526-review-mixed-identity-binding.md"
        ]
        assert lst(status="new") == []
        assert len(lst(project="proj")[0]) == 5
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
                title="Revs Me",
                area="ai-tooling",
                project="revs",
                created="2026-10-30T10:00:00-04:00",
            )
        )

        def link(url, rev, log=None):
            return cmd_link(
                argparse.Namespace(note=str(r), url=url, rev=rev, log=log, account=None)
            )

        link("https://claude.ai/artifact/S", 3, log="first")
        r.write_text(r.read_text() + "\n## Working notes\n\nscratch\n")
        link("https://claude.ai/artifact/S", 4, log="after a trailing section")
        text = r.read_text()
        assert text.endswith("\n\n## Working notes\n\nscratch\n"), text
        assert "· first\n- rev 4 · " in text, text
        assert "· after a trailing section\n\n## Working notes" in text, text
        before = parse_fm(r) or {}
        cmd_link(
            argparse.Namespace(
                note=str(r),
                url="https://hub.test/r/",
                rev=1,
                log="first hub",
                account=None,
                hub=True,
            )
        )
        cmd_link(
            argparse.Namespace(
                note=str(r),
                url="https://hub.test/r/",
                rev=2,
                log=None,
                account=None,
                hub=True,
            )
        )
        after = parse_fm(r) or {}
        assert after["artifact_hub"] == ["https://hub.test/r/"] and after[
            "artifact_hub_rev"
        ] == ["2"], after
        for key in (
            "artifact",
            "artifact_rev",
            "artifact_account",
        ):
            assert after[key] == before[key], key
        text = r.read_text()
        assert text.count("artifact_hub:") == 1 and text.endswith(
            "\n\n## Working notes\n\nscratch\n"
        ), text
        assert (
            "· hub https://hub.test/r/ · first hub\n- rev 2 · " in text
            and text.count("· hub https://hub.test/r/") == 2
        ), text

        frag = Path(d, "frag.html")
        frag.write_text(
            '<div class="tldr"><p>short</p></div>\n<p>{{TITLE}} stays</p>\n',
            encoding="utf-8",
        )
        h = cmd_new(
            ns(
                title="Cache <Plan> & TTLs",
                area="ai-tooling",
                project="hp",
                tags="cache",
                body_file=str(frag),
                created="2026-11-03T10:00:00-05:00",
            )
        )
        assert h == Path(d) / "areas/hp/cache-plan-ttls.html", h
        text = h.read_text()
        assert text.startswith(
            "<!--\n---\nid: cache-plan-ttls\naliases: []\ntags: [claude, cache]\narea: ai-tooling\nproject: hp\ncreated: 2026-11-03T10:00:00-05:00\n---\n-->\n<!doctype html>\n"
        ), text
        assert "<title>Cache &lt;Plan&gt; &amp; TTLs</title>" in text, text
        assert "<h1>Cache &lt;Plan&gt; &amp; TTLs</h1>" in text, text
        assert '<p class="eyebrow">hp · ai-tooling</p>' in text, text
        assert '<p class="meta">2026-11-03</p>' in text, text
        assert "<p>{{TITLE}} stays</p>" in text and "{{BODY}}" not in text, text
        assert text.endswith("</html>\n") and "toc" not in text.lower(), text
        full = Path(d, "deck.htm")
        page = "<!DOCTYPE html>\n<html><head><title>Q4\n  Deck</title></head><body>x</body></html>"
        full.write_text(page + "\n", encoding="utf-8")
        f2 = cmd_new(
            ns(
                title="Deck",
                area="ai-tooling",
                project="hp",
                body_file=str(full),
                created="2026-11-03T11:00:00-05:00",
            )
        )
        assert f2.name == "deck.html", f2
        assert f2.read_text().endswith("---\n-->\n" + page + "\n"), f2.read_text()
        assert [(r[3], r[4]) for r in lst(project="hp")] == [
            ("areas/hp/deck.html", "Q4 Deck"),
            ("areas/hp/cache-plan-ttls.html", "Cache <Plan> & TTLs"),
        ]
        for rev, log in ((1, "a --> b"), (2, "second")):
            cmd_link(
                argparse.Namespace(
                    note=str(h),
                    url="https://claude.ai/artifact/H",
                    rev=rev,
                    log=log,
                    account="rc-team",
                )
            )
        text = h.read_text()
        assert (
            "artifact: https://claude.ai/artifact/H\nartifact_rev: 2\nartifact_account: rc-team\n---\n\n## Artifact revisions\n\n- rev 1 · "
            in text
        ), text
        assert "· a -> b\n- rev 2 · " in text and text.count("-->") == 1, text
        assert "· second\n-->\n<!doctype html>\n" in text, text
        assert text.endswith("</html>\n") and text.count("artifact:") == 1, text
        assert (parse_fm(h) or {})["artifact_rev"] == ["2"]
        k = cmd_new(
            ns(
                title="PE-9 html ticket",
                area="security",
                project="hp",
                key="PE-9",
                body_file=str(frag),
                created="2026-11-03T12:00:00-05:00",
            )
        )
        assert k.name == "PE-9-html-ticket.html", k
        assert cmd_bump(argparse.Namespace(note=str(k))) == 2
        assert cmd_status(argparse.Namespace(note=str(k), status="ready")) == "ready"
        text = k.read_text()
        assert text.startswith("<!--\n---\nid: PE-9-html-ticket\n"), text
        assert (
            "rev: 2\n" in text and "status: ready\n---\n-->\n<!doctype html>\n" in text
        )
        assert [r[3] for r in lst(ticket="PE-9")] == ["areas/hp/PE-9-html-ticket.html"]

        def convert(*paths, out_dir=None, force=False, to="html"):
            return cmd_convert(
                argparse.Namespace(
                    paths=[str(p) for p in paths], out_dir=out_dir, force=force, to=to
                )
            )

        cv = Path(d) / "areas" / "cv"
        (cv / "diagrams").mkdir(parents=True)
        (cv / "diagrams" / "flow.png").write_bytes(b"\x89PNG-fake")
        moved = Path(d) / "areas" / "elsewhere-proj" / "diagrams"
        moved.mkdir(parents=True)
        (moved / "elsewhere.svg").write_text("<svg/>", encoding="utf-8")
        (cv / "a.md").write_text(
            "---\nid: a\naliases: []\ntags: [claude, x]\narea: auth\nproject: cv\n"
            "created: 2026-10-01T09:00:00-04:00\nartifact: https://claude.ai/artifact/C\n"
            "artifact_rev: 1\n---\n\n# Tokens and `ttl`\n\nSee [[redis-keys|the keys]].\n\n"
            "| k | v |\n|---|---|\n| a | 1 |\n\n```mermaid\ngraph LR\n  A-->B\n```\n\n"
            "![flow](diagrams/flow.png)\n\n![gone](diagrams/missing.png)\n\n"
            "![moved](diagrams/elsewhere.svg)\n\n"
            "## Artifact revisions\n\n- rev 1 · 2026-10-01T10:00:00-04:00 · first --> pass\n\n"
            "## Working notes\n\nscratch\n",
            encoding="utf-8",
        )
        (cv / "sub").mkdir()
        (cv / "sub" / "b.md").write_text("plain body\n", encoding="utf-8")
        for skipped in ("handoffs", ".git"):
            (cv / skipped).mkdir()
            (cv / skipped / "h.md").write_text("# h\n", encoding="utf-8")
        assert convert(cv) == [cv / "a.html", cv / "sub" / "b.html"]
        assert not (cv / "handoffs" / "h.html").exists()
        assert (cv / "a.md").exists() and (cv / "sub" / "b.md").exists()
        text = (cv / "a.html").read_text()
        assert text.startswith(
            "<!--\n---\nid: a\naliases: []\ntags: [claude, x]\narea: auth\nproject: cv\n"
            "created: 2026-10-01T09:00:00-04:00\nartifact: https://claude.ai/artifact/C\n"
            "artifact_rev: 1\n---\n\n## Artifact revisions\n\n- rev 1 · 2026-10-01T10:00:00-04:00 · first -> pass\n-->\n<!doctype html>\n"
        ), text
        assert text.count("-->") == 1, text
        assert "<title>Tokens and ttl</title>" in text, text
        assert "<h1>Tokens and <code>ttl</code></h1>" in text, text
        assert '<p class="eyebrow">cv · auth</p>' in text
        assert '<p class="meta">2026-10-01</p>' in text
        assert (
            'href="obsidian://open?vault=' + Path(d).name + '&amp;file=redis-keys"'
            in text
        ), text
        assert '<div class="table-wrap"><table>' in text, text
        assert '<pre class="mermaid">graph LR' in text and "mermaid@11.4.1" in text
        assert 'src="data:image/png;base64,' in text, text
        assert 'src="diagrams/missing.png"' in text, text
        assert 'src="data:image/svg+xml;base64,PHN2Zy8+"' in text, text
        assert '<h2 id="working-notes">Working notes</h2>' in text, text
        assert "<h1" not in text.split("</header>")[1], text
        fm = parse_fm(cv / "a.html") or {}
        assert fm["title"] == ["Tokens and ttl"] and fm["artifact_rev"] == ["1"], fm
        assert "areas/cv/a.html" in [r[3] for r in lst(project="cv")]
        cmd_link(
            argparse.Namespace(
                note=str(cv / "a.html"),
                url="https://claude.ai/artifact/C",
                rev=2,
                log="html rev",
                account="rc-team",
            )
        )
        text = (cv / "a.html").read_text()
        assert "· first -> pass\n- rev 2 · " in text and "· html rev\n-->\n" in text
        plain = (cv / "sub" / "b.html").read_text()
        assert plain.startswith("<!doctype html>\n"), plain
        assert "<title>b</title>" in plain and "<h1>b</h1>" in plain, plain
        assert 'class="eyebrow"' not in plain and 'class="meta"' not in plain, plain
        assert "<p>plain body</p>" in plain and "mermaid@" not in plain, plain
        assert convert(cv / "sub" / "b.md") == []
        assert convert(cv / "sub" / "b.md", force=True) == [cv / "sub" / "b.html"]
        out = Path(d) / "out"
        assert convert(cv, out_dir=str(out)) == [out / "a.html", out / "sub" / "b.html"]
        assert convert(cv / "a.md", out_dir=str(out / "flat")) == [
            out / "flat" / "a.html"
        ]
        try:
            convert(cv / "nope.txt")
            raise AssertionError("non-markdown arg must fail")
        except SystemExit as e:
            assert e.code == 1, e

        assert convert(cv / "a.html", to="md") == [], "existing .md must be kept"
        back = Path(d) / "back"
        assert convert(cv, to="md", out_dir=str(back)) == [
            back / "a.md",
            back / "sub" / "b.md",
        ]
        md = (back / "a.md").read_text()
        assert md.startswith(
            "---\nid: a\naliases: []\ntags: [claude, x]\narea: auth\nproject: cv\n"
            "created: 2026-10-01T09:00:00-04:00\nartifact: https://claude.ai/artifact/C\n"
            "artifact_rev: 2\nartifact_account: rc-team\n---\n\n# Tokens and `ttl`\n\n"
            "See [[redis-keys|the keys]].\n"
        ), md
        assert "| k   | v   |" in md and "```mermaid\ngraph LR\n  A-->B\n```" in md, md
        assert "![flow](data:image/png;base64," in md, md
        assert "## Working notes\n\nscratch\n" in md, md
        assert md.rstrip().endswith("· html rev") and "\n## Artifact revisions\n" in md
        assert md.index("## Working notes") < md.index("## Artifact revisions"), md
        assert "<" not in md.split("![flow]")[0].split("---\n\n", 1)[1], md
        assert (parse_fm(back / "a.md") or {})["artifact_rev"] == ["2"]
        assert (back / "sub" / "b.md").read_text() == "# b\n\nplain body\n"
        assert convert(h, to="md") == [h.with_suffix(".md")]
        md = h.with_suffix(".md").read_text()
        assert (
            "---\n\n# Cache \\<Plan\\> & TTLs\n\nshort\n\n{{TITLE}} stays\n" in md
        ), md
        assert "<script" not in md and "2026-11-03\n\n" not in md, md
        assert md.rstrip().endswith("· second") and md.count("## Artifact") == 1, md
        assert convert(f2, to="md") == [f2.with_suffix(".md")]
        assert f2.with_suffix(".md").read_text().endswith("---\n\n# Q4 Deck\n\nx\n")
        slot("")
    print("ok")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="note.py")
    ap.add_argument("--test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    n = sub.add_parser("new")
    n.add_argument("--title", required=True)
    n.add_argument("--area", required=True, choices=AREAS)
    n.add_argument(
        "--project",
        type=project_arg,
        help="vault folder; default: cwd repo's origin name",
    )
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
    sub.add_parser("projects")
    k = sub.add_parser("link")
    k.add_argument("note")
    k.add_argument("--url", required=True)
    k.add_argument("--rev", required=True, type=int)
    k.add_argument("--log", help="one line for the note's revision log")
    k.add_argument("--account", help="default: the logged-in claude.ai org label")
    k.add_argument(
        "--hub",
        action="store_true",
        help="record the artifacts hub page as artifact_hub; claude.ai keys untouched",
    )
    v = sub.add_parser(
        "convert",
        help="markdown to html note template (or back with --to md); dirs recurse, sources are kept",
    )
    v.add_argument("paths", nargs="+", help="source files and/or directories")
    v.add_argument(
        "--to",
        choices=("html", "md"),
        default="html",
        help="target format; md reads .html sources",
    )
    v.add_argument("--out-dir", help="write here, mirroring each dir's tree")
    v.add_argument("--force", action="store_true", help="overwrite existing .html")
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
    if a.cmd == "projects":
        return cmd_projects(a)
    if a.cmd == "link":
        return cmd_link(a)
    if a.cmd == "account":
        return cmd_account(a)
    if a.cmd == "convert":
        return cmd_convert(a)
    if a.cmd == "bump":
        return cmd_bump(a)
    if a.cmd == "status":
        return cmd_status(a)
    ap.print_help()


if __name__ == "__main__":
    main()
