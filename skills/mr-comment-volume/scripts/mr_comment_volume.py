#!/usr/bin/env python3
"""Count code vs comment lines in a GitLab MR diff (added lines only)."""

import re
import subprocess
import sys

LINE_PREFIX = {
    "py": "#",
    "sh": "#",
    "bash": "#",
    "zsh": "#",
    "rb": "#",
    "pl": "#",
    "pm": "#",
    "r": "#",
    "yaml": "#",
    "yml": "#",
    "toml": "#",
    "ini": "#",
    "cfg": "#",
    "conf": "#",
    "tf": "#",
    "hcl": "#",
    "mk": "#",
    "makefile": "#",
    "dockerfile": "#",
    "gitignore": "#",
    "env": "#",
    "properties": "#",
    "gemspec": "#",
    "rake": "#",
    "ex": "#",
    "exs": "#",
    "js": "//",
    "mjs": "//",
    "cjs": "//",
    "jsx": "//",
    "ts": "//",
    "tsx": "//",
    "c": "//",
    "h": "//",
    "cpp": "//",
    "cc": "//",
    "cxx": "//",
    "hpp": "//",
    "hh": "//",
    "cs": "//",
    "java": "//",
    "go": "//",
    "rs": "//",
    "swift": "//",
    "kt": "//",
    "kts": "//",
    "scala": "//",
    "php": "//",
    "m": "//",
    "mm": "//",
    "dart": "//",
    "proto": "//",
    "json5": "//",
    "zig": "//",
    "groovy": "//",
    "gradle": "//",
    "sql": "--",
    "lua": "--",
    "hs": "--",
    "elm": "--",
    "adb": "--",
    "ads": "--",
    "clj": ";",
    "cljs": ";",
    "el": ";",
    "lisp": ";",
    "scm": ";",
    "vim": '"',
    "erl": "%",
    "tex": "%",
}
BLOCK: dict[str, tuple[str, str]] = {
    ext: ("/*", "*/")
    for ext in (
        "js mjs cjs jsx ts tsx c h cpp cc cxx hpp hh cs java go rs swift kt kts "
        "scala php dart proto css scss less styl groovy gradle zig".split()
    )
}
BLOCK.update(
    {
        ext: ("<!--", "-->")
        for ext in "html htm xml xhtml vue svelte md markdown".split()
    }
)

SPECIAL_NAMES = {"dockerfile": "dockerfile", "makefile": "makefile", "rakefile": "rake"}


def ext_of(path):
    base = path.rsplit("/", 1)[-1].lower()
    if base in SPECIAL_NAMES:
        return SPECIAL_NAMES[base]
    return base.rsplit(".", 1)[-1] if "." in base else base


def classify_file(ext, lines):
    """Return (code, comment, blank) counts for one file's added lines."""
    lp = LINE_PREFIX.get(ext)
    block = BLOCK.get(ext)
    py_doc = ext in ("py", "pyi")  # triple-quoted blocks treated as comments
    code = comment = blank = 0
    in_block = False
    in_doc = False
    doc_q = None
    for raw in lines:
        s = raw.strip()
        if in_block:
            comment += 1
            if block and block[1] in s:
                in_block = False
            continue
        if in_doc:
            comment += 1
            if doc_q in s:
                in_doc = False
            continue
        if s == "":
            blank += 1
            continue
        if py_doc and (s.startswith('"""') or s.startswith("'''")):
            comment += 1
            q = s[:3]
            # single-line docstring """x""" stays closed
            if not (len(s) > 3 and s.endswith(q)):
                in_doc = True
                doc_q = q
            continue
        if lp and s.startswith(lp):
            comment += 1
            continue
        if block and s.startswith(block[0]):
            comment += 1
            if block[1] not in s[len(block[0]) :]:
                in_block = True
            continue
        code += 1
    return code, comment, blank


def parse_diff(text):
    """Yield (ext, [added_lines]) per file block in a unified diff."""
    cur_ext = None
    added = []
    files = []
    for line in text.splitlines():
        if line.startswith("+++ "):
            if cur_ext is not None:
                files.append((cur_ext, added))
            path = line[4:].strip()
            path = re.sub(r"^b/", "", path)
            if path == "/dev/null":
                cur_ext, added = None, []
                continue
            cur_ext, added = ext_of(path), []
        elif line.startswith("+") and not line.startswith("+++"):
            if cur_ext is not None:
                added.append(line[1:])
    if cur_ext is not None:
        files.append((cur_ext, added))
    return files


def parse_url(url):
    m = re.match(r"^(https?://[^/]+)/(.+?)/-/merge_requests/(\d+)", url.strip())
    if not m:
        sys.exit(f"not a GitLab MR URL: {url}")
    base, path, iid = m.groups()
    return f"{base}/{path}", path, iid


def fetch_diff(url):
    repo_url, _, iid = parse_url(url)
    out = subprocess.run(
        ["glab", "mr", "diff", iid, "-R", repo_url, "--raw"],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        sys.exit(f"glab failed:\n{out.stderr.strip()}")
    return out.stdout


def report(url, text):
    _, path, iid = parse_url(url)
    files = parse_diff(text)
    per_lang = {}
    tc = tm = tb = 0
    for ext, lines in files:
        c, m, b = classify_file(ext, lines)
        tc += c
        tm += m
        tb += b
        pc, pm, pb = per_lang.get(ext, (0, 0, 0))
        per_lang[ext] = (pc + c, pm + m, pb + b)
    denom = tc + tm
    pct = (tm / denom * 100) if denom else 0.0
    print("MR comment volume (added lines only)")
    print(f"repo: {path}  !{iid}\n")
    print(f"code lines:    {tc:>6}")
    print(f"comment lines: {tm:>6}")
    print(f"comment %:     {pct:>5.1f}%")
    print(f"(blank lines:  {tb:>6}, excluded from %)\n")
    if per_lang:
        print("by language:")
        for ext in sorted(per_lang, key=lambda e: -(per_lang[e][0] + per_lang[e][1])):
            c, m, b = per_lang[ext]
            d = c + m
            p = (m / d * 100) if d else 0.0
            print(f"  {ext:<12} code {c:>5}  comment {m:>5}  {p:>5.1f}%")
    print(f"\nfiles changed: {len(files)}")


SAMPLE = """diff --git a/app.py b/app.py
+++ b/app.py
@@
+# top comment
+import os
+
+def f():
+    \"\"\"docstring line
+    still doc\"\"\"
+    return os.getcwd()  # trailing not a comment line
diff --git a/ui.ts b/ui.ts
+++ b/ui.ts
@@
+/* block
+   still block */
+const x = 1;
+// inline
"""


def self_check():
    files = parse_diff(SAMPLE)
    exts = {e for e, _ in files}
    assert exts == {"py", "ts"}, exts
    counts = {e: classify_file(e, ln) for e, ln in files}
    # py: comments = "# top comment" + 2 docstring lines = 3; code = import,def,return = 3; blank = 1
    assert counts["py"] == (3, 3, 1), counts["py"]
    # ts: comments = 2 block + 1 // = 3; code = const = 1
    assert counts["ts"] == (1, 3, 0), counts["ts"]
    print("self-check ok")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        sys.exit("usage: mr_comment_volume.py <gitlab-mr-url> | --self-check")
    if args[0] == "--self-check":
        self_check()
    else:
        report(args[0], fetch_diff(args[0]))
