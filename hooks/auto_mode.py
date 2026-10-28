#!/usr/bin/env python3
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BYPASS_ENV = "AUTO_MODE_GATE"
STATE_DIR = Path("/tmp/claude-auto-mode")
DEFAULT_BRANCHES = {"main", "master", "stage", "develop", "HEAD"}
AUTO_PROMPT = re.compile(r"^/auto(?:\s+(.*))?$", re.DOTALL)
TO_LINE = re.compile(r"^To (\S+)\s*$")
# git push porcelain-ish summary: " <flag> <summary> <src> -> <dst>"; ! is rejected
REF_LINE = re.compile(r"^ ([ +*=]) .*?\S+ -> (\S+)")
RANK = re.compile(r"^(?:claude:\s*)?(?:\[[^\]]+\]\s*)?(\d+[a-z]*)\.\s")
DEPS = re.compile(r"\(dep on ([^)]*)\)\s*$", re.IGNORECASE)


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(f"{name}.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def state_path(session_id):
    return (
        STATE_DIR
        / f"{re.sub(r'[^A-Za-z0-9_-]', '', session_id or '') or 'global'}.json"
    )


def read_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_state(path, state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def turn_on(session_id, scope):
    write_state(
        state_path(session_id),
        {
            "started": time.time(),
            "scope": scope or "(from conversation)",
            "shipped": [],
        },
    )


def turn_off(session_id):
    try:
        state_path(session_id).unlink()
    except OSError:
        pass


def reminder(session_id, state):
    return (
        f"AUTO MODE on (scope: {state.get('scope')}). Rules of engagement: `commands/auto.md`; hard stops: CLAUDE.md `### Autonomous mode`. "
        f"Exit when the scope is done: `python3 ~/.claude/hooks/auto_mode.py --off` (session {session_id})."
    )


def on_prompt(data):
    sid = data.get("session_id") or ""
    m = AUTO_PROMPT.match((data.get("prompt") or "").strip())
    if m:
        arg = (m.group(1) or "").strip()
        if arg.lower() == "off":
            turn_off(sid)
            print("AUTO MODE off.")
            return
        turn_on(sid, arg)
    state = read_state(state_path(sid))
    if state:
        print(reminder(sid, state))


def repo_of(remote):
    r = re.sub(r"^[a-z+]+://", "", remote)
    r = re.sub(r"^[^@/]+@", "", r)
    # glab -R rejects the scp form host:group/repo.git
    r = re.sub(r"^([^/:]+):(?:\d+/)?", r"\1/", r)
    return r.removesuffix(".git").rstrip("/")


def parse_pushes(text):
    remote, found = None, []
    for line in text.splitlines():
        to = TO_LINE.match(line)
        if to:
            remote = repo_of(to.group(1))
            continue
        ref = REF_LINE.match(line)
        if remote and ref:
            branch = ref.group(2).removeprefix("refs/heads/")
            if branch not in DEFAULT_BRANCHES:
                found.append((remote, branch))
    return found


def pushes_since(transcript, started):
    links = load("created_links_gate")
    uses, found = {}, []
    for rec in links.records_of(os.path.expanduser(transcript)):
        if links.epoch(rec.get("timestamp") or "") < started:
            continue
        content = (rec.get("message") or {}).get("content")
        for b in content if isinstance(content, list) else []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                uses[b.get("id")] = b.get("name")
            elif (
                b.get("type") == "tool_result"
                and not b.get("is_error")
                and uses.get(b.get("tool_use_id")) == "Bash"
            ):
                found.extend(parse_pushes(links.result_text(b.get("content"))))
    return list(dict.fromkeys(found))


def has_mr(repo, branch):
    if repo.startswith("github.com/"):
        args = [
            "gh",
            "pr",
            "list",
            "-R",
            repo,
            "--head",
            branch,
            "--state",
            "all",
            "--json",
            "number",
        ]
    else:
        args = [
            "glab",
            "mr",
            "list",
            "-R",
            repo,
            "--source-branch",
            branch,
            "--all",
            "-F",
            "json",
        ]
    try:
        out = subprocess.run(
            args, capture_output=True, text=True, timeout=15, check=False
        )
        return bool(json.loads(out.stdout)) if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def ready_items(todos):
    open_ranks = {
        m.group(1)
        for t in todos
        if isinstance(t, dict)
        and not t.get("done")
        and (m := RANK.match(t.get("text", "")))
    }
    ready = []
    for t in todos:
        if (
            not isinstance(t, dict)
            or t.get("done")
            or not t.get("text", "").startswith("claude:")
        ):
            continue
        text = t["text"]
        deps = DEPS.search(text)
        if deps and set(re.findall(r"#(\d+[a-z]*)", deps.group(1))) & open_ranks:
            continue
        ready.append(text)
    return ready


def session_todos(cwd):
    p = load("doit_session_prime")
    root = p.git_root(cwd)
    name = p.list_name(root, p.active_feature(root))
    return name, p.load_todos(os.path.join(p.LISTS_DIR, f"{name}.json")) or []


def on_stop(data):
    # one block per stop, so a model that cannot comply never loops
    if data.get("stop_hook_active") or os.environ.get(BYPASS_ENV, "").lower() == "off":
        return
    sid = data.get("session_id") or ""
    spath = state_path(sid)
    state = read_state(spath)
    if not state or not load("doit_session_prime").interactive():
        return
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    name, todos = session_todos(cwd)
    ready = ready_items(todos)
    shipped = {tuple(s) for s in state.get("shipped", [])}
    unshipped = []
    for repo, branch in pushes_since(
        data.get("transcript_path") or "", float(state.get("started", 0))
    ):
        if (repo, branch) in shipped:
            continue
        found = has_mr(repo, branch)
        if found:
            shipped.add((repo, branch))
        elif found is False:
            unshipped.append((repo, branch))
    state["shipped"] = sorted(shipped)
    write_state(spath, state)
    if not ready and not unshipped:
        return
    lines = [
        f"auto_mode gate: autonomous mode is on (scope: {state.get('scope')}) and work is left."
    ]
    if ready:
        lines.append(f'Ready `claude:` items on "{name}" (no open deps):')
        lines += [f"  {t}" for t in ready]
        lines.append(
            "Work them. One that only the user can unblock: add a `gate` item naming the ask and dep the item on it."
        )
    if unshipped:
        lines.append("Pushed since auto mode started, no MR/PR:")
        lines += [f"  {repo} {branch}" for repo, branch in unshipped]
        lines.append("Run the ship-it chain on each; a pushed branch is not shipped.")
    lines.append(
        "Out of scope: end with one line saying which and why. "
        "Scope done: `python3 ~/.claude/hooks/auto_mode.py --off`, then report."
    )
    print(json.dumps({"decision": "block", "reason": "\n".join(lines)}))


def cli(argv):
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not sid:
        sys.exit(
            "auto_mode: CLAUDE_CODE_SESSION_ID unset; run from a Claude Code Bash call"
        )
    if argv[0] == "--on":
        turn_on(sid, " ".join(argv[1:]))
        print(reminder(sid, read_state(state_path(sid)) or {}))
    elif argv[0] == "--off":
        turn_off(sid)
        print("AUTO MODE off.")
    else:
        sys.exit("usage: auto_mode.py --on [scope] | --off")


def main():
    try:
        data = json.load(sys.stdin) or {}
    except ValueError:
        return
    if data.get("hook_event_name") == "Stop":
        on_stop(data)
    elif data.get("hook_event_name") == "UserPromptSubmit":
        on_prompt(data)


if __name__ == "__main__":
    if sys.argv[1:]:
        cli(sys.argv[1:])
    else:
        main()
