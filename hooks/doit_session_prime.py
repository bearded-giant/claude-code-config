#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys

LISTS_DIR = os.path.expanduser("~/.local/share/nvim/doit/lists")
PRIORITY_RANK = {"critical": 0, "urgent": 1, "important": 2}
MAX_ITEMS = 15
MAX_DRIFT = 10
# do-it.nvim's create_list / rename_list reject longer names
MAX_LIST_NAME = 24
REPO_MAX = 14
ORG_PREFIX = "recharge-"
DEFAULT_LEAVES = {"main", "master", "develop"}
SEG_PREFIXES = ("feat-", "fix-", "chore-")


def git_root(cwd: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return cwd


def tmux_window():
    if not os.environ.get("TMUX"):
        return None
    pane = os.environ.get("TMUX_PANE")
    target = ["-t", pane] if pane else []
    try:
        out = subprocess.run(
            ["tmux", "display-message", "-p", *target, "#S:#W"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return None


def hook_input():
    try:
        data = json.loads(sys.stdin.read() or "null")
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def current_branch(root: str):
    try:
        out = subprocess.run(
            ["git", "-C", root, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return None


def active_feature(root: str):
    path = os.path.join(root, ".giantmem", "features", "features.json")
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    active = [
        (name, meta)
        for name, meta in data.items()
        if isinstance(meta, dict) and meta.get("status") == "in_progress"
    ]
    if not active:
        return None
    # several features can be in_progress at once; the one on this branch wins
    branch = current_branch(root)
    for name, meta in active:
        if branch and meta.get("branch") == branch:
            return name
    return active[0][0]


def load_todos(path: str):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        return None
    todos = data.get("todos") if isinstance(data, dict) else None
    return todos if isinstance(todos, list) else None


def load_pending(path: str):
    todos = load_todos(path)
    if todos is None:
        return None, []
    pending = [t for t in todos if isinstance(t, dict) and not t.get("done")]
    pending.sort(
        key=lambda t: (
            PRIORITY_RANK.get(t.get("priorities") or "", 3),
            t.get("order_index") or 0,
        )
    )
    return len(todos), pending


def twin_of(todo: dict):
    twin = todo.get("twin")
    if isinstance(twin, dict) and twin.get("list") and twin.get("id"):
        return twin
    return None


def load_index(list_name: str, cache: dict):
    if list_name not in cache:
        path = os.path.join(LISTS_DIR, f"{list_name}.json")
        # a deleted list means its twins are gone; an unreadable one proves nothing
        todos = load_todos(path) if os.path.isfile(path) else []
        cache[list_name] = (
            None
            if todos is None
            else {t.get("id"): t for t in todos if isinstance(t, dict)}
        )
    return cache[list_name]


def twin_drift(name: str) -> list:
    cache = {}
    own = load_index(name, cache)
    if own is None:
        return []
    found = []
    for todo in own.values():
        twin = twin_of(todo)
        if todo.get("done") or not twin:
            continue
        other = load_index(twin["list"], cache)
        if other is None:
            continue
        text = todo.get("text", "").strip()[:70]
        match = other.get(twin["id"])
        if match is None:
            found.append(
                f"drift: {text} -> twin gone from {twin['list']}; "
                f"delete_todo id={todo.get('id')} or re-owe it"
            )
        elif match.get("done"):
            found.append(
                f"drift: {text} -> done in {twin['list']}; "
                f"complete_todo id={todo.get('id')}"
            )
    for todo in (load_index("daily", cache) or {}).values():
        twin = twin_of(todo)
        if todo.get("done") or not twin or twin["list"] != name:
            continue
        text = todo.get("text", "").strip()[:70]
        match = own.get(twin["id"])
        if match is None:
            found.append(
                f'drift: daily "{text}" -> its {name} item is gone; '
                f"delete_todo id={todo.get('id')}"
            )
        elif match.get("done"):
            found.append(
                f'drift: daily "{text}" -> done in {name}; '
                f"complete_todo id={todo.get('id')}"
            )
    return found


def note_line(todo: dict) -> str:
    desc = (todo.get("description") or "").strip()
    if not desc:
        return ""
    # descriptions accumulate DONE records and a "last modified" footer; the
    # first line is the part that carries the link/command/identifier
    first = desc.split("\n", 1)[0].strip()
    if not first or first.startswith("---") or first.startswith("DONE "):
        return ""
    return first[:160]


def render_items(pending) -> list:
    lines = []
    for todo in pending[:MAX_ITEMS]:
        prio = todo.get("priorities") or "-"
        mark = " <claimed in_progress>" if todo.get("in_progress") else ""
        lines.append(f"  [{prio}] {todo.get('text', '').strip()}{mark}")
        note = note_line(todo)
        if note:
            lines.append(f"      note: {note}")
    extra = len(pending) - MAX_ITEMS
    if extra > 0:
        lines.append(f"  ... {extra} more pending — list_todos for full set")
    return lines


def read_ready(path: str):
    try:
        with open(path) as fh:
            head = fh.read(4096)
    except Exception:
        return None
    if not head.startswith("---"):
        return None
    meta = {}
    for line in head.split("\n")[1:]:
        if line.strip() == "---":
            break
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip().strip("'\"")
    if meta.get("status") != "ready":
        return None
    return path, meta.get("updated") or "?"


def ready_handoff(root: str, feat):
    base = os.path.join(root, ".giantmem")
    # repo-level fallback: work unrelated to the in_progress feature still hands off
    paths = [os.path.join(base, "features", feat, "handoff.md")] if feat else []
    paths.append(os.path.join(base, "handoff.md"))
    for path in paths:
        found = read_ready(path)
        if found:
            return found
    return None


def list_name(root: str, feat) -> str:
    leaf = os.path.basename(root)
    parent = os.path.basename(os.path.dirname(root))
    # parent ending -wt is the worktree container: it names the repo, the leaf names the worktree
    in_wt = parent.endswith("-wt")
    repo = (parent[:-3] if in_wt else leaf).removeprefix(ORG_PREFIX)
    if len(repo) > REPO_MAX:
        repo = repo.split("-")[0]
    seg = feat or (leaf if in_wt and leaf not in DEFAULT_LEAVES else "")
    for prefix in SEG_PREFIXES:
        seg = seg.removeprefix(prefix)
    words = seg.split("-") if seg else []
    # the tmux chip shows the whole name, so shed trailing words rather than cut mid-word
    while len(words) > 1 and len(repo) + 1 + len("-".join(words)) > MAX_LIST_NAME:
        words.pop()
    name = f"{repo}-{'-'.join(words)}" if words else repo
    # daily twins are labeled "<list>: ...", so a list named claude reads as a `claude:` burn item
    if name == "claude":
        name = "-".join(
            (parent[:-3] if in_wt else leaf).removeprefix(ORG_PREFIX).split("-")[:2]
        )
    return name[:MAX_LIST_NAME].rstrip("-")


def main() -> None:
    hook = hook_input()
    session_id = hook.get("session_id") if hook else None
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    root = git_root(cwd)
    feat = active_feature(root)
    name = list_name(root, feat)

    path = os.path.join(LISTS_DIR, f"{name}.json")
    exists = os.path.isfile(path)

    feat_note = f"feature: {feat}" if feat else "(no active feature)"
    resume = f"claude --resume {session_id}" if session_id else "claude --continue"
    lines = [
        "<system-reminder>",
        "doit session list (repo-qualified, worktree-aware):",
        f"  list: {name}   {feat_note}",
        f"  session: {session_id or '?'}  tmux: {tmux_window() or 'none'}",
        f"  resume line for owed items: cd {root} && {resume}",
        (
            f"  giantmem link: giantmem://session/{session_id}"
            if session_id
            else "  giantmem link: (no session id)"
        ),
        f'  pass list="{name}" on EVERY doit call — the MCP default (active '
        "list) is `daily` (or a DOIT_ACTIVE_LIST export), not this derivation",
    ]
    handoff = ready_handoff(root, feat)
    if handoff:
        lines.append(
            f"  handoff ready: {handoff[0]} (updated {handoff[1]}). Read it FIRST, "
            "verify its state against git, act on Start here, then set status: done"
        )

    if not exists:
        lines += [
            f'  exists: no — create_list name="{name}" on first todo for this '
            "repo/feature",
            "Assign model work: prefix a doit todo `claude:`. Drain it: /burn.",
            (
                "Owe the user an action (run/confirm, review/merge, ping, settings, "
                f'resume): create_list name="{name}" first, then add_todo '
                "owe=true on it; the twin lands in `daily`."
            ),
            "</system-reminder>",
        ]
        print("\n".join(lines))
        return

    total, pending = load_pending(path)
    claude_n = sum(1 for t in pending if t.get("text", "").startswith("claude:"))
    owed_n = sum(1 for t in pending if (twin_of(t) or {}).get("list") == "daily")
    lines.append(
        f"  exists: yes — {len(pending)} pending of {total} "
        f"({claude_n} claude:, {owed_n} owed in daily)"
    )
    drift = twin_drift(name) if name != "daily" else []
    if drift:
        lines.append("DRIFT (twins out of sync, fix with the doit MCP first):")
        lines += [f"  {d}" for d in drift[:MAX_DRIFT]]
        if len(drift) > MAX_DRIFT:
            lines.append(f"  ... {len(drift) - MAX_DRIFT} more")
    if pending:
        lines.append("PENDING TODOS (priority bucket, then do-order):")
        lines += render_items(pending)
    else:
        lines.append("  nothing pending")

    lines += [
        "This list is the running todo for this repo/feature — treat it as "
        "first-class session state, not a sidecar. Rules:",
        "  - factor these items into any work you plan or resume this session; "
        "if the user's ask matches one, say so and work it as that item",
        "  - work in this session that lands a listed item -> start_todo when "
        "you pick it up, complete_todo + DONE note when it lands",
        (
            "  - follow-ups found during the work get done this session: no "
            "item, no ask. New items only for work blocked on the user "
            "(operator detail, or a dangerous change: one-way door, data "
            "corruption/loss, security, outward-facing): code work (`ref:` "
            "first description line, `claude:` if model work) deps on its "
            "owed or `decision` item; a `decision` mirrors one doc Open "
            "Question 1:1 (decisions stay on this list: no owe, no daily twin)"
        ),
        (
            "  - anything the USER must do (run/confirm/verify, review/merge an MR, "
            "ping, console/settings, resume) -> add_todo owe=true on this "
            "list; it twins into `daily`. No ask. search_todos first to dedupe. "
            "Name it `daily #N` in your report"
        ),
        (
            "  - complete or revert either twin through the MCP and both follow; "
            "fix DRIFT lines first"
        ),
        "  - stale or non-code items here -> /doit-prune",
        "  - `claude:` items are model-assigned; /burn drains them. Do not "
        "auto-burn and do not quiz the user about the list at startup",
        "</system-reminder>",
    ]
    print("\n".join(lines))


def cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name-only", action="store_true")
    parser.add_argument("--feature")
    parser.add_argument("--cwd")
    args = parser.parse_args()
    if not args.name_only:
        main()
        return
    root = git_root(args.cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    print(list_name(root, args.feature or active_feature(root)))


if __name__ == "__main__":
    # dispatch.py imports this module and calls main() under its own argv, so flags parse only here
    cli()
