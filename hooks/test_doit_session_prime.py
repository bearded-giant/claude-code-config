import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "doit_session_prime", Path(__file__).with_name("doit_session_prime.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CASES = [
    # one list per repo: worktree and feature never add a segment
    ("/dev/cc-wt/sec-auth0-fix", "cc"),
    ("/dev/recharge-auth-wt/better-redis-search", "auth"),
    ("/dev/recharge-merchant-mcp-wt/legacy-oauth-connectors", "merchant-mcp"),
    ("/dev/investigator-v2-wt/golden-runs-tooling", "investigator-v2"),
    ("/dev/remi-wt/main", "remi"),
    # plain repos keep their whole name up to the cap
    ("/dev/claude-code-config", "claude-code-config"),
    ("/dev/dapr/auth-session-sync", "auth-session-sync"),
    ("/dev/giant-tooling", "giant-tooling"),
    ("/dev/do-it.nvim", "do-it.nvim"),
    # over the cap: trailing words shed, never cut mid-word
    ("/dev/recharge-really-long-repository-name-here-wt/x", "really-long-repository"),
    # a bare "claude" list makes its daily twins read as `claude:` burn items
    ("/dev/claude", "claude-repo"),
]

WORKTREES = [
    ("/dev/cc-wt/sec-auth0-fix", "sec-auth0-fix"),
    ("/dev/remi-wt/main", "main"),
    ("/dev/do-it.nvim", None),
]


def write_list(name, todos):
    with open(os.path.join(mod.LISTS_DIR, f"{name}.json"), "w", encoding="utf-8") as fh:
        json.dump({"todos": todos}, fh)


def todo(id_, text, done=False, twin=None):
    item = {"id": id_, "text": text, "done": done}
    if twin:
        item["twin"] = {"list": twin[0], "id": twin[1]}
    return item


def run_main(stdin_text):
    saved = sys.stdin
    sys.stdin = io.StringIO(stdin_text)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            mod.main()
    finally:
        sys.stdin = saved
    return buf.getvalue()


def session_cases(tmp):
    root = os.path.join(tmp, "proj")
    out = run_main(json.dumps({"session_id": "abc"}))
    assert "  session: abc  tmux: none" in out, out
    assert f"  resume line for owed items: cd {root} && claude --resume abc" in out
    assert "exists: no" in out and "add_todo owe=true" in out
    # session lines sit right after the list line
    lines = out.splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith("  list: proj"))
    assert lines[i + 1].startswith("  session:") and lines[i + 2].startswith("  resume")

    for stdin_text in ("", "not json", "[1, 2]"):
        out = run_main(stdin_text)
        assert "  session: ?  tmux: none" in out, out
        assert f"cd {root} && claude --continue" in out


def scope_cases(tmp):
    wt = os.path.join(tmp, "inv-wt", "golden")
    os.makedirs(wt)
    os.environ["CLAUDE_PROJECT_DIR"] = wt
    try:
        out = run_main("{}")
        assert (
            '  add_todo params on every new item: list="inv" worktree="golden"' in out
        ), out
        assert "  list: inv   worktree: golden   feature: -" in out, out
        write_list(
            "inv",
            [
                {**todo("a", "claude: [bug] 1. mine"), "worktree": "golden"},
                {**todo("b", "claude: [bug] 2. theirs"), "worktree": "close"},
                {**todo("c", "claude: [bug] 3. theirs too"), "worktree": "close"},
                todo("d", "[decision] 4. unassigned"),
                {**todo("e", "claude: [bug] 5. other wt"), "worktree": "admin"},
                {
                    **todo("f", "claude: [bug] 6. done mine", done=True),
                    "worktree": "golden",
                },
            ],
        )
        out = run_main("{}")
        lines = out.splitlines()
        mine = lines.index(
            "PENDING TODOS, this worktree/feature (priority bucket, then do-order):"
        )
        assert lines[mine + 1] == "  [-] claude: [bug] 1. mine [wt:golden]", lines[
            mine + 1
        ]
        loose = lines.index("UNASSIGNED (no worktree):")
        assert loose > mine and lines[loose + 1] == "  [-] [decision] 4. unassigned"
        assert (
            "OTHER WORKTREES (list_todos worktree=<name> to see them): admin 1, close 2"
            in out
        ), out
        assert "2. theirs" not in out and "6. done mine" not in out
        assert (
            "4 pending of 6" not in out
            and "5 pending of 6" in out
            and "1 for this worktree/feature" in out
        )
    finally:
        os.environ["CLAUDE_PROJECT_DIR"] = os.path.join(tmp, "proj")


def drift_cases():
    write_list(
        "proj",
        [
            todo("p1", "[gate] 1. owed in daily #1: agree", twin=("daily", "d1")),
            todo("p2", "[gate] 2. owed in daily #2: done there", twin=("daily", "d2")),
            todo("p3", "[gate] 3. owed in daily #9: gone there", twin=("daily", "d9")),
            todo("p4", "claude: [bug] 4. model work"),
            todo("p5", "[gate] 5. owed in daily #3: done here", True, ("daily", "d3")),
        ],
    )
    write_list(
        "daily",
        [
            todo("d1", "[gate] 1. proj: agree", twin=("proj", "p1")),
            todo("d2", "[gate] 2. proj: done there", True, ("proj", "p2")),
            todo("d3", "[gate] 3. proj: done here", twin=("proj", "p5")),
            todo("d4", "[gate] 4. proj: counterpart gone", twin=("proj", "p404")),
            todo("d6", "[gate] 6. other: not ours", twin=("other", "x1")),
        ],
    )
    out = run_main(json.dumps({"session_id": "abc"}))
    assert "exists: yes — 4 pending of 5 (1 claude:, 3 owed in daily)" in out, out
    # session start carries only rules no other always-loaded source holds
    assert "start_todo an item FIRST" in out and "never a new gate item" in out, out
    assert "add_todo type=gate" not in out, out
    assert "CLAUDE.md `### What I owe`" in out and "search_todos first" in out, out
    for dup in (
        "Never owe: resume",
        "item text is a short label",
        "complete or revert either twin",
        "follow-ups found during the work",
    ):
        assert dup not in out, dup
    expected = [
        (
            "  drift: [gate] 2. owed in daily #2: done there -> done in daily; "
            "complete_todo id=p2"
        ),
        (
            "  drift: [gate] 3. owed in daily #9: gone there -> twin gone from daily; "
            "delete_todo id=p3 or re-owe it"
        ),
        (
            '  drift: daily "[gate] 3. proj: done here" -> done in proj; '
            "complete_todo id=d3"
        ),
        (
            '  drift: daily "[gate] 4. proj: counterpart gone" -> its proj item is gone; '
            "delete_todo id=d4"
        ),
    ]
    lines = out.splitlines()
    head = lines.index("DRIFT (twins out of sync, fix with the doit MCP first):")
    assert lines[head + 1 : head + 5] == expected, lines[head : head + 6]
    assert lines[head + 5].startswith("PENDING TODOS"), lines[head + 5]
    assert "agree" not in "\n".join(lines[head : head + 5])
    assert "not ours" not in out

    write_list("proj", [todo("p1", "[gate] 1. owed: agree", twin=("daily", "d1"))])
    write_list("daily", [todo("d1", "[gate] 1. proj: agree", twin=("proj", "p1"))])
    out = run_main("")
    assert "DRIFT (twins" not in out and "drift:" not in out, out
    assert "(0 claude:, 1 owed in daily)" in out

    write_list(
        "proj", [todo(f"p{n}", f"t{n}", twin=("daily", "gone")) for n in range(12)]
    )
    out = run_main("")
    assert out.count("  drift: ") == mod.MAX_DRIFT and "  ... 2 more" in out, out

    # unreadable twin list proves nothing, so no drift is claimed
    with open(os.path.join(mod.LISTS_DIR, "daily.json"), "w", encoding="utf-8") as fh:
        fh.write("{bad")
    assert "drift:" not in run_main("")


def write_handoff(path, status):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            f"---\ntype: handoff\nstatus: {status}\nupdated: 2026-10-17T09:30:00-04:00\n---\n"
        )


def handoff_cases(tmp):
    # proj is no git repo: project and branch both fall back to its dir name
    base = os.path.join(mod.AREAS, "proj", "handoffs")
    assert "handoff" not in run_main("")
    # a paused feature's handoff surfaces, but never as the one to act on first
    paused = os.path.join(base, "features", "paused.md")
    write_handoff(paused, "ready")
    write_handoff(os.path.join(base, "features", "closed.md"), "done")
    out = run_main("")
    assert (
        f"  other ready handoff: {paused} (updated 2026-10-17T09:30:00-04:00)" in out
    ), out
    assert "handoff ready:" not in out and "closed" not in out, out
    # a branch whose worktree is gone still surfaces, newest first
    gone = os.path.join(base, "old-branch.md")
    write_handoff(gone, "ready")
    os.utime(paused, (1, 1))
    # branch-level comes first, the rest follow as secondary lines
    own = os.path.join(base, "proj.md")
    write_handoff(own, "ready")
    lines = run_main("").splitlines()
    i = next(n for n, line in enumerate(lines) if "handoff ready:" in line)
    assert lines[i].startswith(f"  handoff ready: {own}"), lines[i]
    assert lines[i + 1].startswith(f"  other ready handoff: {gone}"), lines[i + 1]
    assert lines[i + 2].startswith(f"  other ready handoff: {paused}"), lines[i + 2]
    # another repo's handoffs never show
    write_handoff(os.path.join(mod.AREAS, "other", "handoffs", "main.md"), "ready")
    assert "other/handoffs/main.md" not in run_main("")
    shutil.rmtree(mod.AREAS)
    path_cases(tmp)


def git(*args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


def path_cases(tmp):
    # the -wt container names the project; a slash in the branch flattens
    repo = os.path.join(tmp, "cc-wt")
    git("init", "-q", repo)
    git("-C", repo, "commit", "-q", "--allow-empty", "-m", "x")
    git("-C", repo, "checkout", "-q", "-b", "feat/x")
    assert mod.project(repo) == "cc"
    # the main checkout is no worktree; a linked one is named by its dir, same repo list
    assert mod.worktree_name(repo) is None
    linked = os.path.join(tmp, "elsewhere", "golden-runs")
    git("-C", repo, "worktree", "add", "-q", "-b", "golden", linked)
    assert mod.worktree_name(linked) == "golden-runs"
    assert mod.list_name(linked) == "cc"
    meta = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("doit_session_prime.py")),
            "--meta",
            "--cwd",
            linked,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert meta == "list: cc\nworktree: golden-runs\nfeature: -\n", meta
    git("-C", repo, "worktree", "remove", "--force", linked)
    assert mod.handoff_path(repo) == os.path.join(
        mod.AREAS, "cc", "handoffs", "feat-x.md"
    )
    assert mod.handoff_path(repo, "auth") == os.path.join(
        mod.AREAS, "cc", "handoffs", "features", "auth.md"
    )
    out = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("doit_session_prime.py")),
            "--handoff-path",
            "--feature",
            "auth",
            "--cwd",
            repo,
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "OBSIDIAN_VAULT": os.path.dirname(mod.AREAS)},
    ).stdout.strip()
    assert out == os.path.join(mod.AREAS, "cc", "handoffs", "features", "auth.md"), out
    # no origin: the checkout dir names the vault folder
    assert mod.vault_project(repo) == "cc"
    # origin names it, lowercased, whatever the checkout dir is called
    git("-C", repo, "remote", "add", "origin", "git@host:grp/sub/Custom-Checkout.git")
    assert mod.vault_project(repo) == "custom-checkout"
    git("-C", repo, "remote", "set-url", "origin", "https://host/grp/mirror")
    names = os.path.join(tmp, "vault-names.csv")
    with open(names, "w", encoding="utf-8") as fh:
        fh.write("remote,folder\nmirror,ai-mirror\n")
    saved = mod.VAULT_NAMES
    vars(mod).update(VAULT_NAMES=names)
    try:
        assert mod.vault_project(repo) == "ai-mirror"
    finally:
        vars(mod).update(VAULT_NAMES=saved)
    assert mod.vault_project(repo) == "mirror"
    shutil.rmtree(repo)


def sync_cases(tmp):
    os.makedirs(os.path.join(tmp, "state", "sync"), exist_ok=True)
    state = os.path.join(tmp, "state", "sync", "state.json")
    with open(state, "w", encoding="utf-8") as fh:
        json.dump({"mode": "local", "online": None, "queue": 0, "conflicts": 0}, fh)
    assert "doit sync:" not in run_main("{}"), "local mode shows no badge"
    with open(state, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "mode": "sync",
                "online": False,
                "queue": 2,
                "conflicts": 1,
                "error": None,
            },
            fh,
        )
    out = run_main("{}")
    assert "doit sync: offline, queued 2, conflicts 1" in out, out
    with open(state, "w", encoding="utf-8") as fh:
        json.dump({"mode": "sync", "online": True, "queue": 0, "conflicts": 0}, fh)
    assert "doit sync:" not in run_main("{}"), "all quiet shows no badge"
    os.remove(state)


def hook_cases() -> None:
    os.environ.pop("TMUX", None)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = os.path.realpath(tmp)
        os.makedirs(os.path.join(tmp, "proj"))
        os.makedirs(os.path.join(tmp, "lists"))
        os.environ["CLAUDE_PROJECT_DIR"] = os.path.join(tmp, "proj")
        saved = {
            "LISTS_DIR": mod.LISTS_DIR,
            "AREAS": mod.AREAS,
            "STATE_DIR": mod.STATE_DIR,
        }
        vars(mod).update(
            LISTS_DIR=os.path.join(tmp, "lists"),
            AREAS=os.path.join(tmp, "vault", "areas"),
            STATE_DIR=os.path.join(tmp, "state"),
        )
        try:
            session_cases(tmp)
            scope_cases(tmp)
            handoff_cases(tmp)
            drift_cases()
            sync_cases(tmp)
        finally:
            vars(mod).update(saved)


def link_cases() -> None:
    if not shutil.which("tmux"):
        print("skip link_cases: no tmux")
        return
    saved_env = {k: os.environ.get(k) for k in ("TMUX", "TMUX_PANE")}
    saved_file = mod.SESSION_FILE
    with tempfile.TemporaryDirectory() as tmp:
        sock = os.path.join(tmp, "t.sock")

        def T(*args):
            return subprocess.run(
                ["tmux", "-S", sock, *args], capture_output=True, text=True, check=True
            ).stdout.strip()

        def opt(name):
            return T("display-message", "-p", "-t", "s:a b", f"#{{{name}}}")

        def persisted():
            with open(mod.SESSION_FILE, encoding="utf-8") as fh:
                return json.load(fh).get("sessions", {})

        T("-f", "/dev/null", "new-session", "-d", "-s", "s", "-n", "a b")
        try:
            os.environ["TMUX"] = f"{sock},0,0"
            os.environ["TMUX_PANE"] = T(
                "display-message", "-p", "-t", "s:a b", "#{pane_id}"
            )
            vars(mod).update(SESSION_FILE=os.path.join(tmp, "session.json"))

            # unlinked window follows the session list; key survives the space in the name
            assert mod.link_window("proj") == ("s:a b", "proj", True)
            assert opt("@doit-window-list") == "proj"
            assert opt("@doit-window-key") == "s:a b"
            assert persisted() == {"s:a b": "proj"}

            # daily is the default view, not a choice: it follows too
            T("set-option", "-wq", "-t", "s:a b", "@doit-window-list", "daily")
            assert mod.link_window("other") == ("s:a b", "other", True)
            assert opt("@doit-window-list") == "other"

            # a project list the user linked is kept
            T("set-option", "-wq", "-t", "s:a b", "@doit-window-list", "mine")
            assert mod.link_window("proj") == ("s:a b", "mine", False)
            assert opt("@doit-window-list") == "mine"

            # live option gone (tmux restart) but session.json still holds the link
            T("set-option", "-wqu", "-t", "s:a b", "@doit-window-list")
            with open(mod.SESSION_FILE, "w", encoding="utf-8") as fh:
                json.dump({"active_list": "x", "sessions": {"s:a b": "kept"}}, fh)
            assert mod.link_window("proj") == ("s:a b", "kept", False)
            assert opt("@doit-window-list") == ""

            # the stop gate follows only unlinked windows: daily was the user's switch
            T("set-option", "-wq", "-t", "s:a b", "@doit-window-list", "daily")
            assert mod.link_window("proj", follow=("",)) == ("s:a b", "daily", False)
            assert opt("@doit-window-list") == "daily"

            # each claude pane names its own list; the window link stays shared
            mod.stamp_pane("solo", "sid-123")
            pane_list = T(
                "display-message",
                "-p",
                "-t",
                os.environ["TMUX_PANE"],
                "#{@doit-pane-list}|#{@claude_session_id}",
            )
            assert pane_list == "solo|sid-123", pane_list
            assert opt("@doit-window-list") == "daily"

            # tmux 3.5 prints the separator as the text \037
            T("set-option", "-wqu", "-t", "s:a b", "@doit-window-list")
            with open(mod.SESSION_FILE, "w", encoding="utf-8") as fh:
                json.dump({"sessions": {}}, fh)
            real_run = subprocess.run

            def escaping_run(*a, **kw):
                out = real_run(*a, **kw)
                if isinstance(out.stdout, str):
                    out.stdout = out.stdout.replace(mod.TMUX_SEP, "\\037")
                return out

            subprocess.run = escaping_run
            try:
                linked = mod.link_window("esc")
            finally:
                subprocess.run = real_run
            assert linked == ("s:a b", "esc", True), linked
            assert opt("@doit-window-list") == "esc"

            # no pane id: an untargeted query would answer for another window
            pane = os.environ.pop("TMUX_PANE")
            assert mod.link_window("proj") is None
            mod.stamp_pane("other")
            os.environ["TMUX_PANE"] = pane
            assert (
                T("display-message", "-p", "-t", pane, "#{@doit-pane-list}") == "solo"
            )

            os.environ.pop("TMUX")
            assert mod.link_window("proj") is None
        finally:
            subprocess.run(
                ["tmux", "-S", sock, "kill-server"], capture_output=True, check=False
            )
            vars(mod).update(SESSION_FILE=saved_file)
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def main() -> None:
    for root, expected in CASES:
        got = mod.list_name(root)
        assert got == expected, f"{root}: {got!r} != {expected!r}"
        assert len(got) <= mod.MAX_LIST_NAME
    for root, expected in WORKTREES:
        assert mod.worktree_name(root) == expected, root

    # one word longer than the cap is hard cut
    long = mod.list_name("/dev/" + "a" * 40)
    assert long == "a" * mod.MAX_LIST_NAME
    hook_cases()
    link_cases()
    print("ok")


if __name__ == "__main__":
    main()
