#!/usr/bin/env python3
import argparse
import contextlib
import csv
import json
import os
import re
import subprocess
import sys
import time

LISTS_DIR = os.path.expanduser("~/.local/share/nvim/doit/lists")
SESSION_FILE = os.path.expanduser("~/.local/share/nvim/doit/session.json")
# outside the repo so a worktree can be removed without stranding its handoff
AREAS = os.path.join(
    os.path.expanduser(os.environ.get("OBSIDIAN_VAULT", "~/Recharge-Notes")),
    "areas",
)
VAULT_NAMES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    "config",
    "vault-names.csv",
)
# tmux format separator; window names can hold tabs and spaces
TMUX_SEP = "\x1f"
PRIORITY_RANK = {"critical": 0, "urgent": 1, "important": 2}
MAX_ITEMS = 15
MAX_DRIFT = 10
MAX_HANDOFFS = 6
# do-it.nvim's create_list / rename_list reject longer names
MAX_LIST_NAME = 24
ORG_PREFIX = "recharge-"


def git_root(cwd: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
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
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return None


def read_session_file() -> dict:
    try:
        with open(SESSION_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def interactive() -> bool:
    # claude -p sets sdk-cli even when its parent session is cli
    return not os.environ.get("CLAUDE_CODE_ENTRYPOINT", "cli").startswith("sdk")


def link_window(name: str, follow=("", "daily")):
    pane = os.environ.get("TMUX_PANE")
    # untargeted display-message resolves to the last-used client's window, not this pane's
    if not os.environ.get("TMUX") or not pane:
        return None
    fmt = f"#{{window_id}}{TMUX_SEP}#{{@doit-window-list}}{TMUX_SEP}#S:#W"
    try:
        out = subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane, fmt],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        # tmux 3.5 prints the separator as the literal text \037
        fields = out.stdout.rstrip("\n").replace("\\037", TMUX_SEP)
        win_id, live, key = fields.split(TMUX_SEP, 2)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    session = read_session_file()
    links = session.get("sessions")
    if not isinstance(links, dict):
        links = {}
    current = live or links.get(key) or ""
    # a window the user linked to a project list keeps it; only an unlinked or daily window follows the session
    if current not in follow:
        return key, current, False
    for opt, val in (("@doit-window-list", name), ("@doit-window-key", key)):
        subprocess.run(
            ["tmux", "set-option", "-wq", "-t", win_id, opt, val],
            capture_output=True,
            timeout=2,
            check=False,
        )
    session["sessions"] = {**links, key: name}
    session["timestamp"] = int(time.time())
    tmp = f"{SESSION_FILE}.tmp"
    with contextlib.suppress(OSError):
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(session, fh, indent=2)
        os.replace(tmp, SESSION_FILE)
    return key, name, True


def stamp_pane(name: str, session_id=None) -> None:
    pane = os.environ.get("TMUX_PANE")
    if not os.environ.get("TMUX") or not pane:
        return
    # every pane in a window shares its link, so the board needs each claude pane's own list
    cmd = ["tmux", "set-option", "-pq", "-t", pane, "@doit-pane-list", name]
    # the devbox daemon's restart resumes the pane's transcript by this id
    if session_id:
        cmd += [";", "set-option", "-pq", "-t", pane, "@claude_session_id", session_id]
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.run(cmd, capture_output=True, timeout=2, check=False)


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
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return None


def active_feature(root: str):
    path = os.path.join(root, ".giantmem", "features", "features.json")
    try:
        with open(path, encoding="utf-8") as fh:
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
        with open(path, encoding="utf-8") as fh:
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


def scope_label(todo: dict) -> str:
    wt, feat = todo.get("worktree"), todo.get("feature")
    return (f" [wt:{wt}]" if wt else "") + (f" [feat:{feat}]" if feat else "")


def render_items(pending, limit=MAX_ITEMS) -> list:
    lines = []
    for todo in pending[:limit]:
        prio = todo.get("priorities") or "-"
        mark = " <in_progress: active>" if todo.get("in_progress") else ""
        lines.append(
            f"  [{prio}] {todo.get('text', '').strip()}{scope_label(todo)}{mark}"
        )
        note = note_line(todo)
        if note:
            lines.append(f"      note: {note}")
    extra = len(pending) - limit
    if extra > 0:
        lines.append(f"  ... {extra} more pending — list_todos for full set")
    return lines


def split_scope(pending, wt, feat):
    mine, loose, others = [], [], {}
    for todo in pending:
        own = todo.get("worktree")
        if own == wt or (feat and todo.get("feature") == feat):
            mine.append(todo)
        elif not own:
            loose.append(todo)
        else:
            others[own] = others.get(own, 0) + 1
    return mine, loose, others


def read_ready(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
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


def common_dir(root: str) -> str:
    common = ""
    with contextlib.suppress(Exception):
        out = subprocess.run(
            [
                "git",
                "-C",
                root,
                "rev-parse",
                "--path-format=absolute",
                "--git-common-dir",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if out.returncode == 0:
            common = out.stdout.strip()
    return common


def project(root: str) -> str:
    common = common_dir(root)
    # every worktree of cc-wt/.bare shares one common dir, so they share one project
    if common:
        name = os.path.basename(os.path.dirname(common))
    else:
        parent = os.path.basename(os.path.dirname(root))
        name = parent if parent.endswith("-wt") else os.path.basename(root)
    return name.removesuffix("--bare").removesuffix("-wt")


def worktree_name(root: str):
    common = common_dir(root)
    if common:
        main = os.path.realpath(os.path.dirname(common))
        return None if main == os.path.realpath(root) else os.path.basename(root)
    parent = os.path.basename(os.path.dirname(root))
    return os.path.basename(root) if parent.endswith("-wt") else None


def vault_names() -> dict:
    with (
        contextlib.suppress(OSError, KeyError),
        open(VAULT_NAMES, encoding="utf-8") as fh,
    ):
        return {r["remote"]: r["folder"] for r in csv.DictReader(fh)}
    return {}


def vault_project(root: str) -> str:
    url = ""
    with contextlib.suppress(Exception):
        out = subprocess.run(
            ["git", "-C", root, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if out.returncode == 0:
            url = out.stdout.strip()
    # the remote names a repo the same in every clone and worktree; checkout dirs drift (cc-wt, recharge-sidekick-wt)
    name = url.rstrip("/").removesuffix(".git")
    name = (re.split(r"[/:]", name)[-1] if name else project(root)).lower()
    return vault_names().get(name, name)


def handoffs_dir(root: str) -> str:
    return os.path.join(AREAS, vault_project(root), "handoffs")


def handoff_path(root: str, feat=None) -> str:
    base = handoffs_dir(root)
    if feat:
        return os.path.join(base, "features", f"{feat}.md")
    branch = current_branch(root) or os.path.basename(root)
    return os.path.join(base, f"{branch.replace('/', '-')}.md")


def ready_handoffs(root: str, feat):
    base = handoffs_dir(root)
    # branch-level fallback: work unrelated to the in_progress feature still hands off
    own = [handoff_path(root, feat)] if feat else []
    own.append(handoff_path(root))
    # other branches and features too, incl. ones whose worktree is gone
    entries = []
    for d in (base, os.path.join(base, "features")):
        with contextlib.suppress(OSError):
            entries += [
                (e.stat().st_mtime, e.path)
                for e in os.scandir(d)
                if e.name.endswith(".md") and e.path not in own
            ]
    others = [p for _, p in sorted(entries, reverse=True)]
    primary = next(filter(None, map(read_ready, own)), None)
    rest = [found for found in map(read_ready, others) if found][:MAX_HANDOFFS]
    return primary, rest


def list_name(root: str) -> str:
    words = project(root).removeprefix(ORG_PREFIX).split("-")
    # the tmux chip shows the whole name, so shed trailing words rather than cut mid-word
    while len(words) > 1 and len("-".join(words)) > MAX_LIST_NAME:
        words.pop()
    name = "-".join(words)[:MAX_LIST_NAME].rstrip("-")
    # daily twins are labeled "<list>: ...", so a list named claude reads as a `claude:` burn item
    return "claude-repo" if name == "claude" else name


def add_params(name: str, wt, feat) -> str:
    parts = [f'list="{name}"']
    if wt:
        parts.append(f'worktree="{wt}"')
    if feat:
        parts.append(f'feature="{feat}"')
    return " ".join(parts)


def main() -> None:
    hook = hook_input()
    session_id = hook.get("session_id") if hook else None
    cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    root = git_root(cwd)
    feat = active_feature(root)
    wt = worktree_name(root)
    name = list_name(root)

    path = os.path.join(LISTS_DIR, f"{name}.json")
    exists = os.path.isfile(path)

    resume = f"claude --resume {session_id}" if session_id else "claude --continue"
    window = tmux_window() or "none"
    if interactive():
        stamp_pane(name, session_id)
    link = link_window(name) if exists and interactive() else None
    if link:
        key, linked, changed = link
        window = f"{key} -> {linked}" + (
            " (linked now)"
            if changed
            else (
                f" (user link kept; its chip shows {linked}, not {name})"
                if linked != name
                else ""
            )
        )
    lines = [
        "<system-reminder>",
        "doit session list (one list per repo, items carry worktree + feature):",
        f"  list: {name}   worktree: {wt or '-'}   feature: {feat or '-'}",
        f"  session: {session_id or '?'}  tmux: {window}",
        f"  resume line for owed items: cd {root} && {resume}",
        (
            f"  giantmem link: giantmem://session/{session_id}"
            if session_id
            else "  giantmem link: (no session id)"
        ),
        f'  pass list="{name}" on EVERY doit call — the MCP default (active '
        "list) is `daily` (or a DOIT_ACTIVE_LIST export), not this derivation",
        f"  add_todo params on every new item: {add_params(name, wt, feat)}",
    ]
    primary, rest = ready_handoffs(root, feat)
    if primary:
        lines.append(
            f"  handoff ready: {primary[0]} (updated {primary[1]}). Read it FIRST, "
            "verify its state against git, act on Start here, then set status: done"
        )
    lines += [
        f"  other ready handoff: {p} (updated {u}); read it when resuming that work"
        for p, u in rest
    ]

    if not exists:
        lines += [
            f'  exists: no — create_list name="{name}" on first todo for this repo',
            "Assign model work: prefix a doit todo `claude:`. Drain it: /burn.",
            (
                "Owe the user an action only when it passes the daily bar (only "
                "they can do it, actionable now, something waits on it, not "
                f'routine merge/deploy/resume): create_list name="{name}" first, '
                "then add_todo owe=true on it; the twin lands in `daily`."
            ),
            "</system-reminder>",
        ]
        print("\n".join(lines))
        return

    total, pending = load_pending(path)
    claude_n = sum(1 for t in pending if t.get("text", "").startswith("claude:"))
    owed_n = sum(1 for t in pending if (twin_of(t) or {}).get("list") == "daily")
    mine, loose, others = split_scope(pending, wt, feat)
    lines.append(
        f"  exists: yes — {len(pending)} pending of {total} "
        f"({claude_n} claude:, {owed_n} owed in daily); {len(mine)} for this "
        "worktree/feature"
    )
    drift = twin_drift(name) if name != "daily" else []
    if drift:
        lines.append("DRIFT (twins out of sync, fix with the doit MCP first):")
        lines += [f"  {d}" for d in drift[:MAX_DRIFT]]
        if len(drift) > MAX_DRIFT:
            lines.append(f"  ... {len(drift) - MAX_DRIFT} more")
    if mine:
        lines.append(
            "PENDING TODOS, this worktree/feature (priority bucket, then do-order):"
        )
        lines += render_items(mine)
    if loose:
        lines.append("UNASSIGNED (no worktree):")
        lines += render_items(loose, max(MAX_ITEMS - len(mine), 3))
    if others:
        counts = ", ".join(f"{k} {v}" for k, v in sorted(others.items()))
        lines.append(
            f"OTHER WORKTREES (list_todos worktree=<name> to see them): {counts}"
        )
    if not pending:
        lines.append("  nothing pending")

    lines += [
        "This list is the running todo for this repo (every worktree and "
        "feature) — treat it as first-class session state, not a sidecar. Rules:",
        "  - factor these items into any work you plan or resume this session; "
        "if the user's ask matches one, say so and work it as that item",
        (
            "  - one item for this worktree is always in_progress (start_todo stops "
            "only the same worktree's active item, so parallel sessions keep "
            "theirs). start_todo an item FIRST, as its own call, before you "
            "read or edit for it, whether or not it lands this session; "
            "complete_todo + DONE note when it lands. Ending a turn (done, "
            "blocked, or waiting on the user) -> leave the next item "
            "in_progress: the one you are on, else the one waiting on the user, "
            "else the top pending one. Waiting on the user for obvious "
            "follow-through no item covers (review, merge, tag or deploy after "
            "a merge) -> create no item; the report and handoff carry it "
            "(never a new gate item for it). doit_active_gate (Stop) "
            "blocks once while this worktree has pending items and none is "
            "in_progress"
        ),
        (
            "  - owed: only past the CLAUDE.md `### What I owe` bar; "
            "search_todos first, then add_todo owe=true on this list"
        ),
        "  - every new item gets the add_todo params above; work for another "
        "feature passes that feature's name, same list",
        "  - stale or non-code items here -> /doit-prune",
        "  - `claude:` items are model-assigned; /burn drains them. Do not "
        "auto-burn and do not quiz the user about the list at startup",
        "</system-reminder>",
    ]
    print("\n".join(lines))


def cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name-only", action="store_true")
    parser.add_argument("--meta", action="store_true")
    parser.add_argument("--handoff-path", action="store_true")
    parser.add_argument("--feature")
    parser.add_argument("--cwd")
    args = parser.parse_args()
    if not (args.name_only or args.meta or args.handoff_path):
        main()
        return
    root = git_root(args.cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    if args.handoff_path:
        print(handoff_path(root, args.feature))
        return
    if args.meta:
        print(f"list: {list_name(root)}")
        print(f"worktree: {worktree_name(root) or '-'}")
        print(f"feature: {active_feature(root) or '-'}")
        return
    print(list_name(root))


if __name__ == "__main__":
    # dispatch.py imports this module and calls main() under its own argv, so flags parse only here
    cli()
