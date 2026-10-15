#!/usr/bin/env python3
import datetime as dt
import fcntl
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

VAULT = Path(os.environ.get("OBSIDIAN_VAULT", "~/Recharge-Notes")).expanduser()
BUNDLES = (
    Path(os.environ.get("GIANTMEM_ARCHIVE_BASE", "~/giantmem_archive")).expanduser()
    / "bundles"
)
DAILY_DIR = "daily"
TEMPLATE = "templates/dailytemplate.md"
SESSIONS = "## CLAUDE SESSIONS"
LINKS = "## CLAUDE LINKS"
SKIP_DIRS = {DAILY_DIR, "templates", ".obsidian", ".trash"}
ARTIFACT_URL = re.compile(r"https://claude\.ai/[\w./-]*artifact/[\w-]+")
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
SUBST = re.compile(r"\{\{?\s*(yesterday|tomorrow|date|time|title)\s*\}?\}")


def local_now():
    return dt.datetime.now().astimezone()


def prime():
    spec = importlib.util.spec_from_file_location(
        "doit_session_prime", Path(__file__).with_name("doit_session_prime.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def note_path(day):
    return VAULT / DAILY_DIR / f"{day.isoformat()}.md"


def render_template(day):
    try:
        text = (VAULT / TEMPLATE).read_text(encoding="utf-8")
    except OSError:
        text = "---\ntags: [daily]\n---\n"
    values = {
        "yesterday": f"[[{(day - dt.timedelta(days=1)).isoformat()}]]",
        "tomorrow": f"[[{(day + dt.timedelta(days=1)).isoformat()}]]",
        "date": day.isoformat(),
        "title": day.isoformat(),
        "time": local_now().strftime("%H:%M"),
    }
    text = SUBST.sub(lambda m: values[m.group(1)], text)
    # obsidian.nvim copies the template's own id into the note; the date is the real id
    return re.sub(
        r"^id: .*$", f"id: {day.isoformat()}", text, count=1, flags=re.MULTILINE
    )


def section(text, heading):
    lines = text.split("\n")
    if heading not in lines:
        return ""
    out = []
    for ln in lines[lines.index(heading) + 1 :]:
        if ln.strip() == "---" or ln.startswith("## "):
            break
        out.append(ln)
    return "\n".join(out)


def insert_under(text, heading, line):
    lines = text.split("\n")
    if heading not in lines:
        lines += ["", heading, "", "", "---"]
    i = lines.index(heading)
    j = i + 1
    while (
        j < len(lines) and lines[j].strip() != "---" and not lines[j].startswith("## ")
    ):
        j += 1
    while j > i + 1 and not lines[j - 1].strip():
        j -= 1
    lines[j:j] = ["", line] if j == i + 1 else [line]
    return "\n".join(lines)


def append(entries, day=None):
    day = day or local_now().date()
    path = note_path(day)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 4-6 sessions append at once; the lock keeps read-modify-write whole
    with open(path, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        text = fh.read() or render_template(day)
        changed = False
        for heading, key, line in entries:
            # scoped to the section so a link the user wrote in NOTES still gets logged
            if key in section(text, heading):
                continue
            text = insert_under(text, heading, line)
            changed = True
        if changed:
            fh.seek(0)
            fh.truncate()
            fh.write(text if text.endswith("\n") else text + "\n")


def context(data):
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    mod = prime()
    root = mod.git_root(cwd)
    return {
        "sid": data.get("session_id") or "",
        "root": root,
        "list": mod.list_name(root, mod.active_feature(root)),
        "tmux": mod.tmux_session(),
        "slug": Path(data.get("transcript_path") or "").parent.name,
    }


def session_entry(ctx):
    now = local_now().strftime("%H:%M")
    resume = f"claude --resume {ctx['sid']}" if ctx["sid"] else "claude --continue"
    tmux = f" · tmux {ctx['tmux']}" if ctx["tmux"] else ""
    line = f"- {now} {ctx['list']}{tmux} · `cd {ctx['root']} && {resume}`"
    if ctx["sid"] and ctx["slug"]:
        line += f" · [bundle](file://{BUNDLES / ctx['slug'] / ctx['sid']})"
    return (SESSIONS, ctx["sid"] or line, line)


def link_entry(ctx, kind, label, target):
    now = local_now().strftime("%H:%M")
    sid = f" · s:{ctx['sid'][:8]}" if ctx["sid"] else ""
    return (LINKS, target, f"- {now} {kind} {label} · {ctx['list']}{sid}")


def in_vault(path):
    try:
        rel = Path(path).expanduser().resolve().relative_to(VAULT.resolve())
    except (OSError, ValueError):
        return None
    if rel.suffix != ".md" or rel.parts[0] in SKIP_DIRS:
        return None
    return rel


def artifact_link(data):
    ti = data.get("tool_input") or {}
    if ti.get("action", "publish") != "publish" or ti.get("asset"):
        return None
    m = ARTIFACT_URL.search(json.dumps(data.get("tool_response")))
    if not m:
        return None
    url = m.group(0)
    title = Path(ti.get("file_path") or url).stem
    try:
        found = TITLE.search(
            Path(ti["file_path"]).read_text(encoding="utf-8", errors="replace")
        )
        if found and found.group(1).strip():
            title = " ".join(found.group(1).split())
    except (KeyError, OSError):
        pass
    return ("artifact", f"[{title}]({url})", url)


def bash_vault_paths(data):
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if "note.py" not in cmd or " new" not in cmd:
        return []
    resp = data.get("tool_response")
    out = resp.get("stdout", "") if isinstance(resp, dict) else str(resp or "")
    return [ln.strip() for ln in out.splitlines() if ln.strip().endswith(".md")]


def links_for(data):
    tool = data.get("tool_name")
    if tool == "Artifact":
        found = artifact_link(data)
        return [found] if found else []
    if tool == "Bash":
        paths = bash_vault_paths(data)
    elif tool in ("Write", "Edit", "MultiEdit"):
        paths = [(data.get("tool_input") or {}).get("file_path") or ""]
    else:
        return []
    out = []
    for p in paths:
        if p.endswith("handoff.md") and "/.giantmem/" in p:
            out.append(("handoff", f"[handoff]({p})", p))
        elif in_vault(p):
            stem = Path(p).stem
            out.append(("vault", f"[[{stem}]]", f"[[{stem}]]"))
    return out


def interactive():
    return os.environ.get("CLAUDE_CODE_ENTRYPOINT", "cli") == "cli"


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    event = data.get("hook_event_name")
    if event == "SessionStart":
        if data.get("source") in ("startup", "resume") and interactive():
            append([session_entry(context(data))])
        return
    if event != "PostToolUse":
        return
    links = links_for(data)
    if not links:
        return
    ctx = context(data)
    append([session_entry(ctx)] + [link_entry(ctx, *found) for found in links])


if __name__ == "__main__":
    main()
