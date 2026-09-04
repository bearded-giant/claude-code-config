#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path(
    os.environ.get(
        "NOTION_PUBLISH_CONFIG",
        Path(__file__).resolve().parent.parent / "config" / "notion-publish.yaml",
    )
)
# ponytail: skill write-back bumps mtime after sync; grace keeps that from reading as dirty
DIRTY_GRACE_S = 120

FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)
COMMENT_LINE_RE = re.compile(r"^\s*<!--.*?-->\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
TABLE_SEP_RE = re.compile(r"^\s*\|?(\s*:?-{3,}:?\s*\|)*\s*:?-{3,}:?\s*\|?\s*$")
LIST_INDENT_RE = re.compile(r"^((?:  )+)(?=[-*+] |\d+\. )")
CODE_SPAN_RE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
QUOTE_RE = re.compile(r"^(\s*(?:>\s?)+)")
BR_RE = re.compile(r"<br\s*/?>")
BR_TOKEN = "\x00BR\x00"
PAGE_ID_RE = re.compile(r"([0-9a-f]{32})")


def load_config(path=CONFIG):
    cfg: dict = {"types": [], "exclude": []}
    key = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("- ") and key:
            cfg.setdefault(key, []).append(line.strip()[2:].strip().strip("'\""))
            continue
        k, _, v = line.partition(":")
        key = k.strip()
        v = v.strip().strip("'\"")
        cfg[key] = v if v else []
    return cfg


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if line[:1] in (" ", "\t", "-") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip().strip("'\"")
    return fm, text[m.end() :]


def giantmem_rel(path):
    p = str(Path(path).resolve())
    i = p.find("/.giantmem/")
    return None if i < 0 else p[i + len("/.giantmem/") :]


def classify_type(rel):
    parts = rel.split("/")
    last = parts[-1]
    if len(parts) >= 3 and parts[0] == "specs" and last == "spec.md":
        return "source-spec"
    if (
        len(parts) >= 5
        and parts[0] == "features"
        and parts[2] == "specs"
        and last == "spec.md"
    ):
        return "delta-spec"
    if len(parts) >= 3 and parts[0] == "features":
        feat, tail = parts[1], parts[2]
        fixed = {
            "proposal.md": "proposal",
            "spec.md": "proposal",
            "design.md": "design",
            "tasks.md": "tasks",
            "facts.md": "facts",
            f"{feat}-notes.md": "notes",
        }
        if tail in fixed:
            return fixed[tail]
        sub = {"plans": "plan", "research": "research", "reviews": "review"}
        if len(parts) >= 4 and tail in sub:
            return sub[tail]
        return "file"
    head = {
        "research": "research",
        "plans": "plan",
        "context": "pattern",
        "history": "history",
        "prompts": "prompt",
        "filebox": "filebox",
    }
    if len(parts) >= 2 and parts[0] in head:
        return head[parts[0]]
    if rel in ("WORKSPACE.md", "workspace.md"):
        return "workspace"
    if rel == "notes.md":
        return "notes"
    return "file"


def gate(path, cfg, fm=None):
    rel = giantmem_rel(path)
    if rel is None:
        return False, "outside .giantmem", "", ""
    if not rel.endswith(".md"):
        return False, "not markdown", rel, ""
    if any(seg.startswith(".") for seg in rel.split("/")):
        return False, "dot dir", rel, ""
    if rel.rsplit("/", 1)[-1] in ("_index.md", "_history.md"):
        return False, "machine index", rel, ""
    if fm is None:
        fm, _ = parse_frontmatter(
            Path(path).read_text(encoding="utf-8", errors="replace")
        )
    kind = fm.get("type") or classify_type(rel)
    publish = fm.get("publish", "").lower()
    if publish in ("false", "no"):
        return False, "publish: false", rel, kind
    if fm.get("lifecycle") == "deprecated":
        return False, "lifecycle: deprecated", rel, kind
    for rx in cfg.get("exclude", []):
        if re.search(rx, rel):
            return False, f"exclude {rx}", rel, kind
    if publish in ("true", "yes"):
        return True, "publish: true", rel, kind
    if kind in cfg.get("types", []):
        return True, f"type {kind}", rel, kind
    return False, f"type {kind} not in types", rel, kind


def is_dirty(path, fm):
    synced = fm.get("notion_synced")
    if not fm.get("notion") or not synced:
        return True
    try:
        t = datetime.fromisoformat(synced.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return True
    return os.path.getmtime(path) > t + DIRTY_GRACE_S


def _escape(s):
    s = re.sub(r"(?<!\\)[<>{}^$|]", lambda m: "\\" + m.group(0), s)
    s = re.sub(r"(?<![~\\])~(?!~)", r"\\~", s)
    return s.replace("[[", "\\[\\[").replace("]]", "\\]\\]")


def escape_prose(s):
    s = BR_RE.sub(BR_TOKEN, s)
    out, pos = [], 0
    for m in CODE_SPAN_RE.finditer(s):
        out.append(_escape(s[pos : m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(_escape(s[pos:]))
    return "".join(out).replace(BR_TOKEN, "<br>")


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    spans = []

    def stash(m):
        spans.append(m.group(0))
        return f"\x00{len(spans) - 1}\x00"

    line = CODE_SPAN_RE.sub(stash, line)
    cells = re.split(r"(?<!\\)\|", line)
    return [
        re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], c).strip()
        for c in cells
    ]


def table_xml(rows):
    width = max(len(r) for r in rows)
    out = ['<table header-row="true">']
    for r in rows:
        r = r + [""] * (width - len(r))
        out.append("\t<tr>")
        out.extend(f"\t\t<td>{escape_prose(c)}</td>" for c in r)
        out.append("\t</tr>")
    out.append("</table>")
    return out


def convert_body(body):
    out, table = [], []
    title = None
    in_fence, fence = False, ""

    def flush_table():
        nonlocal table
        if table:
            out.extend(table_xml(table))
            table = []

    for line in body.splitlines():
        if in_fence:
            out.append(line)
            if line.strip().startswith(fence):
                in_fence = False
            continue
        m = FENCE_RE.match(line)
        if m:
            flush_table()
            in_fence, fence = True, m.group(1)
            out.append(line)
            continue
        if line.lstrip().startswith("|"):
            if not TABLE_SEP_RE.match(line):
                table.append(split_row(line))
            continue
        flush_table()
        if COMMENT_LINE_RE.match(line):
            continue
        if title is None and line.startswith("# "):
            title = line[2:].strip()
            continue
        m = LIST_INDENT_RE.match(line)
        if m:
            line = "\t" * (len(m.group(1)) // 2) + line[m.end() :]
        m = QUOTE_RE.match(line)
        if m:
            out.append(m.group(1) + escape_prose(line[m.end() :]))
            continue
        out.append(escape_prose(line))
    flush_table()
    return title, "\n".join(out).strip() + "\n"


def git(cwd, *args):
    try:
        r = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return r.stdout.strip()
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


def properties(
    path, fm, rel, kind, title, now
):  # pylint: disable=too-many-positional-arguments
    d = Path(path).resolve().parent
    repo = fm.get("repo") or git(d, "rev-parse", "--show-toplevel").rsplit("/", 1)[-1]
    props = {
        "Name": title,
        "Repo": repo,
        "Branch": fm.get("branch") or git(d, "branch", "--show-current"),
        "Type": kind,
        "Source": rel,
        "Git SHA": git(d, "rev-parse", "--short", "HEAD"),
        "date:Synced:start": now,
        "date:Synced:is_datetime": 1,
    }
    for key, prop in (
        ("feature", "Feature"),
        ("status", "Status"),
        ("lifecycle", "Lifecycle"),
    ):
        if fm.get(key):
            props[prop] = fm[key]
    if "Feature" not in props and rel.startswith("features/"):
        props["Feature"] = rel.split("/")[1]
    return props


def convert(path, cfg, now):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    ok, reason, rel, kind = gate(path, cfg, fm)
    title, content = convert_body(body)
    title = title or Path(path).stem
    url = fm.get("notion", "")
    m = PAGE_ID_RE.search(url.replace("-", ""))
    return {
        "path": str(Path(path).resolve()),
        "source": rel,
        "type": kind,
        "publishable": ok,
        "reason": reason,
        "dirty": is_dirty(path, fm),
        "notion": url,
        "page_id": m.group(1) if m else "",
        "title": title,
        "properties": properties(path, fm, rel, kind, title, now),
        "content": content,
    }


def mark(path, url, now):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if m:
        fm_text = re.sub(r"(?m)^notion(_synced)?:.*\n?", "", m.group(1)).rstrip("\n")
        head = f"---\n{fm_text}\nnotion: {url}\nnotion_synced: {now}\n---\n"
        text = head + text[m.end() :]
    else:
        text = f"---\nnotion: {url}\nnotion_synced: {now}\n---\n" + text
    p.write_text(text, encoding="utf-8")


def scan(root, cfg):
    rows, seen = [], set()
    for p in sorted(Path(root).rglob("*.md")):
        if any(seg.startswith(".") for seg in p.relative_to(root).parts):
            continue
        # spec.md -> proposal.md symlinks left by the rename migration
        real = p.resolve()
        if real in seen:
            continue
        seen.add(real)
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        ok, reason, rel, kind = gate(p, cfg, fm)
        rows.append(
            {
                "path": str(p),
                "source": rel,
                "type": kind,
                "publishable": ok,
                "reason": reason,
                "dirty": is_dirty(p, fm),
                "notion": fm.get("notion", ""),
            }
        )
    return rows


def selftest():
    sample = (
        "---\ntype: research\nrepo: r\nstatus: ready\n---\n"
        "<!-- caveman:compressed -->\n\n# Title Here\n\n"
        "Prose with a < b and x -> y, see [[wiki]] and ~one~ ~~two~~ `a < b`.<br/>\n\n"
        "| Col A | Col B |\n|---|---|\n| `x\\|y` | 1 |\n| `a|b` | 2 |\n"
        "| ```` ```mermaid ```` fence | `<t>` |\n\n"
        "```python\nif a < b: pass  # {raw}\n```\n\n"
        "- top\n  - nested\n\n> quoted > text\n"
    )
    fm, body = parse_frontmatter(sample)
    assert fm["type"] == "research"
    title, content = convert_body(body)
    assert title == "Title Here"
    assert "caveman" not in content
    assert (
        "a \\< b and x -\\> y, see \\[\\[wiki\\]\\] and \\~one\\~ ~~two~~ `a < b`.<br>"
        in content
    )
    assert '<table header-row="true">' in content and "<td>`x\\|y`</td>" in content
    assert "<td>`a|b`</td>" in content and "<td></td>" not in content
    assert (
        "<td>```` ```mermaid ```` fence</td>" in content and "<td>`<t>`</td>" in content
    )
    assert "|---|" not in content
    assert "if a < b: pass  # {raw}" in content
    assert "\n\t- nested" in content
    assert "> quoted \\> text" in content
    assert classify_type("features/f/proposal.md") == "proposal"
    assert classify_type("features/f/specs/d/spec.md") == "delta-spec"
    assert classify_type("context/x.md") == "pattern"
    assert classify_type("features/f/quickstart.md") == "file"
    cfg = {"types": ["research"], "exclude": [r"\.original\.md$"]}
    assert gate("/w/.giantmem/research/a.md", cfg, {"type": "research"})[0]
    assert not gate("/w/.giantmem/research/a.original.md", cfg, {"type": "research"})[0]
    assert not gate("/w/.giantmem/plans/a.md", cfg, {})[0]
    assert gate("/w/.giantmem/plans/a.md", cfg, {"publish": "true"})[0]
    assert not gate("/w/.giantmem/features/_index.md", cfg, {"publish": "true"})[0]
    print("selftest ok")


def main(argv):
    if argv[:1] == ["--selftest"]:
        selftest()
        return 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if argv[:1] == ["--scan"]:
        root = Path(argv[1] if len(argv) > 1 else ".giantmem")
        print(json.dumps(scan(root, load_config()), indent=1))
        return 0
    if argv[:1] == ["--mark"]:
        mark(argv[2], argv[1], now)
        print(f"marked {argv[2]} -> {argv[1]}")
        return 0
    if not argv:
        print(
            "usage: md_to_notion.py <file.md> | --scan [dir] | --mark <url> <file.md> | --selftest",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(convert(argv[0], load_config(), now), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
