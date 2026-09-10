#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from functools import lru_cache
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
LIST_INDENT_RE = re.compile(r"^((?:  )+)(?=[-*+] |\d+\. )")
CODE_SPAN_RE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
QUOTE_RE = re.compile(r"^(\s*(?:>\s?)+)")
BR_RE = re.compile(r"<br\s*/?>")
BR_TOKEN = "\x00BR\x00"
# anchored: slug letters like the e in "backbone" are hex, so an unanchored match shifts the id
PAGE_ID_RE = re.compile(r"([0-9a-f]{32})$")


def load_config(path=CONFIG):
    cfg: dict = {"auto": [], "on_request": [], "exclude": []}
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


def gate(path, cfg, fm=None, ident=None):
    rel = giantmem_rel(path)
    if rel is None:
        return False, "outside .giantmem", "", "", ""
    if not rel.endswith(".md"):
        return False, "not markdown", rel, "", ""
    if any(seg.startswith(".") for seg in rel.split("/")):
        return False, "dot dir", rel, "", ""
    if rel.rsplit("/", 1)[-1] in ("_index.md", "_history.md"):
        return False, "machine index", rel, "", ""
    if ident is None:
        ident = identity(str(Path(path).resolve().parent))
    if not ident:
        return False, "not in git", rel, "", ""
    if fm is None:
        fm, _ = parse_frontmatter(
            Path(path).read_text(encoding="utf-8", errors="replace")
        )
    kind = fm.get("type") or classify_type(rel)
    publish = fm.get("publish", "").lower()
    if publish in ("false", "no"):
        return False, "publish: false", rel, kind, ""
    if fm.get("lifecycle") == "deprecated":
        return False, "lifecycle: deprecated", rel, kind, ""
    for rx in cfg.get("exclude", []):
        if re.search(rx, rel):
            return False, f"exclude {rx}", rel, kind, ""
    if publish in ("true", "yes"):
        return True, "publish: true", rel, kind, "auto"
    doc_kind = fm.get("kind", "")
    if doc_kind in cfg.get("auto", []) or kind in cfg.get("auto", []):
        return True, f"auto {doc_kind or kind}", rel, kind, "auto"
    if kind in cfg.get("on_request", []):
        return True, f"on_request {kind}", rel, kind, "on_request"
    return False, f"type {kind} not in auto or on_request", rel, kind, ""


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


def convert_body(body):
    out = []
    title = None
    in_fence, fence = False, ""

    for line in body.splitlines():
        if in_fence:
            out.append(line)
            if line.strip().startswith(fence):
                in_fence = False
            continue
        m = FENCE_RE.match(line)
        if m:
            in_fence, fence = True, m.group(1)
            out.append(line)
            continue
        # pipe tables pass through untouched; the server parses GFM tables itself
        if line.lstrip().startswith("|"):
            out.append(line)
            continue
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


def repo_from_origin(url):
    url = re.sub(r"\.git$", "", url.strip().rstrip("/"))
    return url.rsplit("/", 1)[-1].rsplit(":", 1)[-1]


@lru_cache(maxsize=None)
def identity(d):
    top = git(d, "rev-parse", "--show-toplevel")
    if not top:
        return None
    origin = git(d, "remote", "get-url", "origin")
    common = git(d, "rev-parse", "--path-format=absolute", "--git-common-dir")
    gitdir = git(d, "rev-parse", "--path-format=absolute", "--git-dir")
    if origin:
        repo = repo_from_origin(origin)
    elif common:
        repo = Path(common).parent.name
    else:
        repo = Path(top).name
    return {
        "repo": repo,
        # linked worktree: its git-dir sits under the common dir, never equals it
        "worktree": Path(top).name if gitdir and common and gitdir != common else "",
        "sha": git(d, "rev-parse", "--short", "HEAD"),
    }


def feature_of(rel):
    parts = rel.split("/")
    return parts[1] if len(parts) >= 3 and parts[0] == "features" else ""


def parent_path(ident, rel):
    return "/".join(p for p in (ident["repo"], ident["worktree"], feature_of(rel)) if p)


def source_ref(ident, rel):
    wt = f"@{ident['worktree']}" if ident["worktree"] else ""
    return f"{ident['repo']}{wt}/{rel}"


def footer(ident, rel, now):
    return (
        f"\n> [!NOTE]\n> giantmem: {source_ref(ident, rel)}"
        f" \u00b7 synced {now} \u00b7 sha {ident['sha']}\n"
    )


def convert(path, cfg, now):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    ident = identity(str(Path(path).resolve().parent))
    ok, reason, rel, kind, cls = gate(path, cfg, fm, ident)
    title, content = convert_body(body)
    title = title or Path(path).stem
    if ident and rel:
        content += footer(ident, rel, now)
    url = fm.get("notion", "")
    m = PAGE_ID_RE.search(url.split("?", 1)[0].rstrip("/").replace("-", ""))
    return {
        "path": str(Path(path).resolve()),
        "source": rel,
        "type": kind,
        "class": cls,
        "publishable": ok,
        "reason": reason,
        "dirty": is_dirty(path, fm),
        "notion": url,
        "page_id": m.group(1) if m else "",
        "title": title,
        "repo": ident["repo"] if ident else "",
        "worktree": ident["worktree"] if ident else "",
        "parent_path": parent_path(ident, rel) if ident and rel else "",
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
        ident = identity(str(real.parent))
        ok, reason, rel, kind, cls = gate(p, cfg, fm, ident)
        rows.append(
            {
                "path": str(p),
                "source": rel,
                "type": kind,
                "class": cls,
                "publishable": ok,
                "reason": reason,
                "dirty": is_dirty(p, fm),
                "notion": fm.get("notion", ""),
                "parent_path": parent_path(ident, rel) if ident and rel else "",
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
    assert "| Col A | Col B |\n|---|---|\n| `x\\|y` | 1 |\n| `a|b` | 2 |" in content
    assert "| ```` ```mermaid ```` fence | `<t>` |" in content
    assert "if a < b: pass  # {raw}" in content
    assert "\n\t- nested" in content
    assert "> quoted \\> text" in content
    assert classify_type("features/f/proposal.md") == "proposal"
    assert classify_type("features/f/specs/d/spec.md") == "delta-spec"
    assert classify_type("context/x.md") == "pattern"
    assert classify_type("features/f/quickstart.md") == "file"
    cfg = {
        "auto": ["quickstart"],
        "on_request": ["research"],
        "exclude": [r"\.original\.md$"],
    }
    wt = {"repo": "r", "worktree": "w", "sha": "abc1234"}
    plain = {"repo": "r", "worktree": "", "sha": "abc1234"}

    def g(rel, fm, ident=plain):  # pylint: disable=dangerous-default-value
        return gate(f"/x/.giantmem/{rel}", cfg, fm, ident)

    assert g("research/a.md", {"type": "research"})[4] == "on_request"
    assert not g("research/a.original.md", {"type": "research"})[0]
    assert not g("plans/a.md", {})[0]
    assert g("plans/a.md", {"publish": "true"})[4] == "auto"
    assert g("features/f/quickstart.md", {"kind": "quickstart"})[4] == "auto"
    assert not g(
        "features/f/quickstart.md", {"kind": "quickstart", "publish": "false"}
    )[0]
    assert not g("features/_index.md", {"publish": "true"})[0]
    assert g("research/a.md", {"type": "research"}, None)[1] == "not in git"
    assert (
        repo_from_origin("git@gitlab.example.net:eng/customcheckout.git")
        == "customcheckout"
    )
    assert (
        repo_from_origin("https://github.com/acme/notion-multi-mcp.git")
        == "notion-multi-mcp"
    )
    assert repo_from_origin("git@github.com:solo.git") == "solo"
    assert parent_path(wt, "features/f/research/x.md") == "r/w/f"
    assert parent_path(plain, "context/x.md") == "r"
    assert parent_path(wt, "research/x.md") == "r/w"
    assert source_ref(wt, "features/f/x.md") == "r@w/features/f/x.md"
    assert "giantmem: r/context/x.md \u00b7 synced T \u00b7 sha abc1234" in footer(
        plain, "context/x.md", "T"
    )
    assert identity("/") is None
    for url in (
        "https://app.notion.com/p/Memory-architecture-giantmem-backbone-3d76a2462659816ea2f9df3713a3c47c",
        "https://app.notion.com/p/Proposal-Local-Email-Send-3d76a24626598173810bf2efd30be5d4?pvs=4",
        "https://www.notion.so/3d76a246-2659-816e-a2f9-df3713a3c47c",
    ):
        m = PAGE_ID_RE.search(url.split("?", 1)[0].rstrip("/").replace("-", ""))
        assert m and m.group(1).startswith("3d76a2462659"), url
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
