import atexit
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

spec = importlib.util.spec_from_file_location(
    "created_links_gate", Path(__file__).with_name("created_links_gate.py")
)
assert spec and spec.loader
mod: Any = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TMP = Path(tempfile.mkdtemp())
atexit.register(shutil.rmtree, TMP, ignore_errors=True)
mod.STATE_DIR = TMP / "state"
OPENED = []
mod.open_url = OPENED.append
os.environ["CLAUDE_CODE_ENTRYPOINT"] = "cli"
os.environ.pop("CREATED_LINKS_GATE", None)

MR = "https://gitlab.example.com/ai-tooling/remi/-/merge_requests/45"
MR4 = "https://gitlab.example.com/ai-tooling/remi/-/merge_requests/4"
PR = "https://github.com/someone/tools/pull/7"
SPLUNK = "https://splunk.example.com/en-US/app/search/remi_obs"
CHRONO = "https://acme.chronosphere.io/dashboards/remi"
TS = iter(f"2026-10-18T{10 + m // 60:02d}:{m % 60:02d}:00.000Z" for m in range(600))


def prompt(text):
    return {"type": "user", "timestamp": next(TS), "message": {"content": text}}


def use(uid, name, inp):
    return {
        "type": "assistant",
        "timestamp": next(TS),
        "message": {
            "content": [{"type": "tool_use", "id": uid, "name": name, "input": inp}]
        },
    }


def result(uid, text):
    return {
        "type": "user",
        "timestamp": next(TS),
        "message": {
            "content": [{"type": "tool_result", "tool_use_id": uid, "content": text}]
        },
    }


def say(text):
    return {
        "type": "assistant",
        "timestamp": next(TS),
        "message": {"content": [{"type": "text", "text": text}]},
    }


def pr_link(url):
    return {"type": "pr-link", "prUrl": url, "timestamp": next(TS)}


def write(name, recs, subagents=None):
    path = TMP / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    for sub_name, sub_recs in (subagents or {}).items():
        sub = TMP / name / "subagents" / f"agent-{sub_name}.jsonl"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.write_text("\n".join(json.dumps(r) for r in sub_recs) + "\n")
    return str(path)


def run(path, sid="s1", active=False):
    buf = io.StringIO()
    saved = sys.stdin
    sys.stdin = io.StringIO(
        json.dumps(
            {"transcript_path": path, "session_id": sid, "stop_hook_active": active}
        )
    )
    try:
        with redirect_stdout(buf):
            mod.main()
    finally:
        sys.stdin = saved
    out = buf.getvalue().strip()
    return json.loads(out) if out else None


GLAB_RESULT = f"Creating merge request for feat into main in ai-tooling/remi\n\n{MR}\n"

# glab create in the command, URL missing from the final message: block and open once
path = write(
    "glab",
    [
        prompt("ship it"),
        use("u1", "Bash", {"command": "glab mr create --fill"}),
        result("u1", GLAB_RESULT),
        say("done, docs updated"),
    ],
)
created, _ = mod.scan(path)
assert created == [("remi!45", MR)], created
out = run(path, sid="glab")
assert out and out["decision"] == "block", out
assert f"remi!45 {MR}" in out["reason"], out
assert OPENED == [MR], OPENED

# stop_hook_active: no second block, and no second browser tab
assert run(path, sid="glab", active=True) is None
assert OPENED == [MR], OPENED

# URL in the last lines: no block, and it stays delivered on a later stop in the same turn
path = write(
    "ok",
    [
        prompt("ship it"),
        use("u1", "Bash", {"command": "glab mr create --fill"}),
        result("u1", GLAB_RESULT),
        say(f"shipped\n\nremi!45 {MR}"),
    ],
)
assert run(path, sid="ok") is None

# a bare !4 link does not satisfy a created !45, and vice versa
assert not mod.in_tail(MR4, f"remi!45 {MR}")
assert mod.in_tail(MR, f"[remi!45]({MR})")

# script-run create: command hides glab, output shows it
path = write(
    "script",
    [
        prompt("ship it"),
        use("u1", "Bash", {"command": "bash ship.sh"}),
        result("u1", GLAB_RESULT),
        say("ok"),
    ],
)
assert mod.scan(path)[0] == [("remi!45", MR)]

# reading a file that quotes glab output mid-line creates nothing
path = write(
    "read",
    [
        prompt("how is it tested?"),
        use("u1", "Bash", {"command": "sed -n 150,215p tooluse_test.go"}),
        result(
            "u1",
            f'\t\tresult("c1", false, "Creating merge request for b into main\\n\\n{MR}"),\n',
        ),
        say("ok"),
    ],
)
assert mod.scan(path)[0] == [], mod.scan(path)

# GitHub PR label
path = write(
    "gh",
    [
        prompt("ship it"),
        use("u1", "Bash", {"command": "gh pr create --fill"}),
        result("u1", PR + "\n"),
        say("ok"),
    ],
)
assert mod.scan(path)[0] == [("tools#7", PR)]

# pr-link alone (MR merely viewed) creates nothing
path = write(
    "view",
    [
        prompt("status?"),
        use("u1", "Bash", {"command": "glab mr view 45"}),
        result("u1", f"open {MR}"),
        pr_link(MR),
        say("green"),
    ],
)
assert mod.scan(path)[0] == []
assert run(path, sid="view") is None

# create whose output hid the URL falls back to a pr-link first seen this turn, never an older one
path = write(
    "hidden",
    [
        prompt("earlier"),
        pr_link(MR4),
        prompt("ship it"),
        use("u1", "Bash", {"command": "glab mr create --fill > /dev/null"}),
        result("u1", "Creating merge request for feat into main"),
        pr_link(MR4),
        pr_link(MR),
        say("ok"),
    ],
)
assert mod.scan(path)[0] == [("remi!45", MR)], mod.scan(path)

# a teammate message or task notification does not start a new turn
path = write(
    "team",
    [
        prompt("ship it"),
        use("u1", "Bash", {"command": "glab mr create --fill"}),
        result("u1", GLAB_RESULT),
        prompt(
            'Another Claude session sent a message:\n<teammate-message teammate_id="x">hi</teammate-message>'
        ),
        prompt("<task-notification>\n<task-id>abc</task-id></task-notification>"),
        say("ok"),
    ],
)
assert mod.scan(path)[0] == [("remi!45", MR)]

# splunk_create_dashboard: URL from the JSON result
path = write(
    "splunk",
    [
        prompt("make a dashboard"),
        use("u1", "mcp__splunk__splunk_create_dashboard", {"name": "remi_obs"}),
        result(
            "u1",
            [{"type": "text", "text": json.dumps({"name": "remi_obs", "url": SPLUNK})}],
        ),
        say("dashboard is up"),
    ],
)
out = run(path, sid="splunk")
assert out and f"splunk dashboard {SPLUNK}" in out["reason"], out

# subagent ran chronoctl apply; its own text carries the URL after the apply
main_recs = [prompt("build the chronosphere dashboard"), say("spawned chrono agent")]
sub_recs = [
    prompt(
        "brief: dashboard for remi, see https://acme.chronosphere.io/dashboards/other"
    ),
    use("c0", "Bash", {"command": "chronoctl dashboards create -f d.json --dry-run"}),
    result("c0", "ok"),
    say(f"dry run fine, real one will be {CHRONO}-v0"),
    use(
        "c1",
        "Bash",
        {"command": "env -u TOKEN chronoctl apply -f remi.yaml 2>&1 | tail -1"},
    ),
    result("c1", "applied Dashboard remi"),
    say(f"remi dashboard created: {CHRONO}."),
]
path = write("chrono", main_recs, subagents={"chrono": sub_recs})
created, _ = mod.scan(path)
assert created == [("chronosphere dashboard", CHRONO)], created
out = run(path, sid="chrono")
assert out and f"chronosphere dashboard {CHRONO}" in out["reason"], out

# subagent records from before the turn are ignored
old = [
    use("c1", "Bash", {"command": "chronoctl apply -f remi.yaml"}),
    result("c1", "ok"),
    say(CHRONO),
]
for rec in old:
    rec["timestamp"] = "2026-10-18T09:00:00.000Z"
path = write("chrono_old", [prompt("next thing"), say("ok")], subagents={"old": old})
assert mod.scan(path)[0] == []

# bypass env and headless runs do nothing
os.environ["CREATED_LINKS_GATE"] = "off"
assert (
    run(
        write(
            "bypass",
            [
                prompt("ship it"),
                use("u1", "Bash", {"command": "glab mr create"}),
                result("u1", GLAB_RESULT),
                say("ok"),
            ],
        ),
        sid="bypass",
    )
    is None
)
os.environ.pop("CREATED_LINKS_GATE")
os.environ["CLAUDE_CODE_ENTRYPOINT"] = "sdk-cli"
assert (
    run(
        write(
            "headless",
            [
                prompt("ship it"),
                use("u1", "Bash", {"command": "glab mr create"}),
                result("u1", GLAB_RESULT),
                say("ok"),
            ],
        ),
        sid="headless",
    )
    is None
)
os.environ["CLAUDE_CODE_ENTRYPOINT"] = "cli"

print("ok")
