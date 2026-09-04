#!/usr/bin/env python3
import json
import os
import subprocess

LISTS_DIR = os.path.expanduser("~/.local/share/nvim/doit/lists")
PRIORITY_RANK = {"critical": 0, "urgent": 1, "important": 2}
MAX_ITEMS = 15


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


def load_pending(path: str):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        return None, []
    todos = data.get("todos") if isinstance(data, dict) else None
    if not isinstance(todos, list):
        return None, []
    pending = [t for t in todos if isinstance(t, dict) and not t.get("done")]
    pending.sort(
        key=lambda t: (
            PRIORITY_RANK.get(t.get("priorities") or "", 3),
            t.get("order_index") or 0,
        )
    )
    return len(todos), pending


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


def main() -> None:
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    root = git_root(cwd)
    leaf = os.path.basename(root)
    parent = os.path.basename(os.path.dirname(root))
    # parent ending -wt is the worktree container; fold it into the name so
    # parallel worktrees of the same repo don't collide on one list
    base = f"{parent}-{leaf}" if parent.endswith("-wt") else leaf
    feat = active_feature(root)
    name = f"{base}-{feat}" if feat else base

    path = os.path.join(LISTS_DIR, f"{name}.json")
    exists = os.path.isfile(path)

    feat_note = f"feature: {feat}" if feat else "(no active feature)"
    lines = [
        "<system-reminder>",
        "doit session list (repo-qualified, worktree-aware):",
        f"  list: {name}   {feat_note}",
        f'  pass list="{name}" on EVERY doit call — the MCP default (active '
        "list) follows the tmux link / DOIT_ACTIVE_LIST env, not this derivation",
    ]

    if not exists:
        lines += [
            f'  exists: no — create_list name="{name}" on first todo for this '
            "repo/feature",
            "Assign model work: prefix a doit todo `claude:`. Drain it: /burn.",
            "</system-reminder>",
        ]
        print("\n".join(lines))
        return

    total, pending = load_pending(path)
    claude_n = sum(1 for t in pending if t.get("text", "").startswith("claude:"))
    lines.append(
        f"  exists: yes — {len(pending)} pending of {total} ({claude_n} claude:)"
    )
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
        "  - new user-actionable follow-ups this session -> batch ONE "
        "AskUserQuestion to add them to this list",
        "  - `claude:` items are model-assigned; /burn drains them. Do not "
        "auto-burn and do not quiz the user about the list at startup",
        "</system-reminder>",
    ]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
