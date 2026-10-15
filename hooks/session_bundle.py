#!/usr/bin/env python3
import argparse
import datetime as dt
import fcntl
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ARCHIVE_BASE = Path(
    os.environ.get("GIANTMEM_ARCHIVE_BASE", os.path.expanduser("~/giantmem_archive"))
)
BUNDLES = ARCHIVE_BASE / "bundles"
PROJECTS = Path.home() / ".claude" / "projects"
TMP_GLOB = "/private/tmp/claude-*"
FULL_EVENTS = {"PreCompact", "SessionEnd"}
CLAUDE_PARTS = ("subagents", "workflows", "tool-results")
SID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_SIZE = "20m"
EXCLUDES = [
    ".venv/",
    "venv/",
    "node_modules/",
    "__pycache__/",
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    "*.pyc",
    "*.so",
    "*.dylib",
    "*.whl",
    ".DS_Store",
    ".env",
    ".env.local",
]
KINDS = {
    "script": {
        ".py",
        ".sh",
        ".bash",
        ".js",
        ".mjs",
        ".ts",
        ".sql",
        ".jq",
        ".lua",
        ".go",
    },
    "patch": {".patch", ".diff"},
    "doc": {".md", ".txt", ".html"},
    "data": {".json", ".csv", ".tsv", ".yaml", ".yml", ".parquet"},
    "log": {".log", ".output"},
}
# a dir holding one of these is a venv or a browser profile (cookies, saved logins), whatever its name
MARKERS = {"pyvenv.cfg", "Local State"}
MANIFEST = "bundle.json"
LOCK = ".bundle.lock"
PROMPT_SCAN = 400


def nonempty(path):
    return path.is_dir() and any(p.is_file() for p in path.rglob("*"))


def tmp_dirs(sid):
    return sorted(Path(p) for p in glob.glob(f"{TMP_GLOB}/*/{sid}") if Path(p).is_dir())


def kind_of(rel):
    if rel.parts[0] == "claude":
        if rel.suffix == ".jsonl":
            return "transcript"
        if rel.parts[1:2] == ("workflows",) and rel.suffix == ".js":
            return "workflow"
    for kind, exts in KINDS.items():
        if rel.suffix.lower() in exts:
            return kind
    return "other"


def marker_excludes(src):
    out = []
    for dirpath, dirnames, filenames in os.walk(src):
        if MARKERS & set(filenames):
            out.append(f"/{Path(dirpath).relative_to(src)}/")
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if f"{d}/" not in EXCLUDES]
    return out


def rsync(src, dst, exclude=True):
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = ["rsync", "-a", "--no-links", f"--max-size={MAX_SIZE}"]
    if exclude:
        args += [f"--exclude={e}" for e in EXCLUDES + marker_excludes(src)]
    src_arg = f"{src}/" if src.is_dir() else str(src)
    dst_arg = f"{dst}/" if src.is_dir() else str(dst)
    subprocess.run(
        args + [src_arg, dst_arg], capture_output=True, timeout=300, check=False
    )


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def transcript_meta(transcript):
    meta = {}
    try:
        with open(transcript, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i >= PROMPT_SCAN:
                    break
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                for key, field in (
                    ("cwd", "cwd"),
                    ("branch", "gitBranch"),
                    ("started", "timestamp"),
                ):
                    if rec.get(field) and key not in meta:
                        meta[key] = rec[field]
                if (
                    "first_prompt" in meta
                    or rec.get("type") != "user"
                    or rec.get("isMeta")
                ):
                    continue
                text = text_of((rec.get("message") or {}).get("content")).strip()
                # hook output and slash-command wrappers arrive as user turns too
                if text and not text.startswith("<"):
                    meta["first_prompt"] = " ".join(text.split())[:300]
    except OSError:
        pass
    return meta


def write_manifest(dest, slug, sid, transcript):
    files = []
    for p in sorted(dest.rglob("*")):
        if p.is_file() and p.name not in (MANIFEST, LOCK):
            rel = p.relative_to(dest)
            files.append(
                {"path": str(rel), "size": p.stat().st_size, "kind": kind_of(rel)}
            )
    meta = {"session_id": sid, "slug": slug}
    meta.update(transcript_meta(transcript) if transcript else {})
    meta["updated"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    meta["resume"] = f"claude --resume {sid}"
    meta["files"] = files
    tmp = dest / f"{MANIFEST}.tmp"
    tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    tmp.replace(dest / MANIFEST)


def capture(slug, sid, srcs, full, transcript=None):
    claude_dir = PROJECTS / slug / sid
    transcript = transcript or PROJECTS / slug / f"{sid}.jsonl"
    has_tmp = any(nonempty(s) for s in srcs)
    has_claude = full and any(nonempty(claude_dir / part) for part in CLAUDE_PARTS)
    if not (has_tmp or has_claude):
        return None
    dest = BUNDLES / slug / sid
    dest.mkdir(parents=True, exist_ok=True)
    with open(dest / LOCK, "w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return None
        for src in srcs:
            rsync(src, dest)
        if full:
            for part in CLAUDE_PARTS:
                if (claude_dir / part).is_dir():
                    rsync(claude_dir / part, dest / "claude" / part, exclude=False)
            if Path(transcript).is_file():
                rsync(
                    Path(transcript),
                    dest / "claude" / "transcript.jsonl",
                    exclude=False,
                )
        write_manifest(
            dest, slug, sid, transcript if Path(transcript).is_file() else None
        )
    return dest


def worker(sid, event, transcript):
    srcs = tmp_dirs(sid)
    slug = (
        Path(transcript).parent.name
        if transcript
        else (srcs[0].parent.name if srcs else "")
    )
    if not slug:
        return
    capture(
        slug, sid, srcs, event in FULL_EVENTS, Path(transcript) if transcript else None
    )


def backfill(roots):
    out = []
    for root in roots:
        for sess in sorted(Path(root).glob("*/*")):
            if sess.is_dir() and SID.match(sess.name):
                dest = capture(sess.parent.name, sess.name, [sess], full=True)
                if dest:
                    out.append(dest)
    return out


def spawn(args):
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *args],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if (
        not isinstance(data, dict)
        or not data.get("session_id")
        or not shutil.which("rsync")
    ):
        return
    # detached: a first sync of a big scratchpad must never hold up the turn
    spawn(
        [
            "--worker",
            data["session_id"],
            data.get("hook_event_name") or "Stop",
            data.get("transcript_path") or "",
        ]
    )


def cli():
    ap = argparse.ArgumentParser(prog="session_bundle.py")
    ap.add_argument("--worker", nargs=3, metavar=("SID", "EVENT", "TRANSCRIPT"))
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--from", dest="roots", action="append", default=[])
    a = ap.parse_args()
    if a.worker:
        worker(*a.worker)
    elif a.backfill:
        roots = a.roots or sorted(glob.glob(TMP_GLOB))
        for dest in backfill(roots):
            print(dest)
    else:
        main()


if __name__ == "__main__":
    # dispatch.py imports this module and calls main() under its own argv, so flags parse only here
    cli()
