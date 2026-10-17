import contextlib
import importlib.util
import io
import json
import os
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
    # worktree == feature collapses to one segment
    ("/dev/cc-wt/sec-auth0-fix", "sec-auth0-fix", "cc-sec-auth0-fix"),
    # org prefix and -wt container suffix dropped
    (
        "/dev/recharge-auth-wt/better-redis-search",
        "session-index",
        "auth-session-index",
    ),
    (
        "/dev/recharge-auth-wt/better-redis-search",
        "better-redis-search",
        "auth-better-redis-search",
    ),
    # over the cap: trailing words shed, never cut mid-word
    (
        "/dev/recharge-auth-wt/better-redis-search",
        "service-auth-decouple",
        "auth-service-auth",
    ),
    (
        "/dev/recharge-merchant-mcp-wt/legacy-oauth-connectors",
        "legacy-oauth-connectors",
        "merchant-mcp-legacy",
    ),
    # long repo names keep their first word
    ("/dev/investigator-agent-wt/admin-qol", "admin-qol", "investigator-admin-qol"),
    ("/dev/claude-code-config", "assigned-reviews", "claude-assigned-reviews"),
    # a bare "claude" list makes its daily twins read as `claude:` burn items
    ("/dev/claude-code-config", None, "claude-code"),
    # feat- prefix dropped
    (
        "/dev/frontend-wt/feat-redact-api-tokens",
        "feat-redact-api-tokens",
        "frontend-redact-api",
    ),
    # no feature: non-default worktree names the list, default worktree does not
    ("/dev/cc-wt/stage", None, "cc-stage"),
    ("/dev/remi-wt/main", None, "remi"),
    ("/dev/remi-wt/main", "monorepo", "remi-monorepo"),
    # plain repo, short enough to keep whole
    ("/dev/giant-tooling", None, "giant-tooling"),
    ("/dev/do-it.nvim", None, "do-it.nvim"),
]


def write_list(name, todos):
    with open(os.path.join(mod.LISTS_DIR, f"{name}.json"), "w") as fh:
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
    with open(os.path.join(mod.LISTS_DIR, "daily.json"), "w") as fh:
        fh.write("{bad")
    assert "drift:" not in run_main("")


def write_handoff(path, status):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(f"---\ntype: handoff\nstatus: {status}\nupdated: 2026-10-17\n---\n")


def handoff_cases(tmp):
    base = os.path.join(tmp, "proj", ".giantmem")
    assert "handoff" not in run_main("")
    # a paused feature's handoff surfaces even with no repo-level one
    write_handoff(os.path.join(base, "features", "paused", "handoff.md"), "ready")
    write_handoff(os.path.join(base, "features", "closed", "handoff.md"), "done")
    out = run_main("")
    paused = os.path.join(base, "features", "paused", "handoff.md")
    assert f"  handoff ready: {paused} (updated 2026-10-17). Read it FIRST" in out, out
    assert "closed" not in out
    # repo-level comes first, other features follow as secondary lines
    write_handoff(os.path.join(base, "handoff.md"), "ready")
    lines = run_main("").splitlines()
    i = next(n for n, line in enumerate(lines) if "handoff ready:" in line)
    assert lines[i].startswith(f"  handoff ready: {os.path.join(base, 'handoff.md')}")
    assert lines[i + 1].startswith(f"  other ready handoff: {paused}"), lines[i + 1]
    os.remove(os.path.join(base, "handoff.md"))
    os.remove(paused)


def hook_cases() -> None:
    os.environ.pop("TMUX", None)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = os.path.realpath(tmp)
        os.makedirs(os.path.join(tmp, "proj"))
        os.makedirs(os.path.join(tmp, "lists"))
        os.environ["CLAUDE_PROJECT_DIR"] = os.path.join(tmp, "proj")
        saved = mod.LISTS_DIR
        mod.LISTS_DIR = os.path.join(tmp, "lists")
        try:
            session_cases(tmp)
            handoff_cases(tmp)
            drift_cases()
        finally:
            mod.LISTS_DIR = saved


def main() -> None:
    for root, feat, expected in CASES:
        got = mod.list_name(root, feat)
        assert got == expected, f"{root} {feat}: {got!r} != {expected!r}"
        assert len(got) <= mod.MAX_LIST_NAME

    # one word longer than the cap is hard cut
    long = mod.list_name("/dev/cc-wt/x", "a" * 40)
    assert len(long) == mod.MAX_LIST_NAME and long.startswith("cc-a")
    hook_cases()
    print("ok")


if __name__ == "__main__":
    main()
