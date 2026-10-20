import atexit
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any


def load(name) -> Any:
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).with_name(f"{name}.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load("auto_mode")
tmp = Path(tempfile.mkdtemp())
atexit.register(shutil.rmtree, tmp, ignore_errors=True)
mod.STATE_DIR = tmp / "state"


class Prime:
    @staticmethod
    def interactive():
        return True


real_load = mod.load
mod.load = lambda name: Prime if name == "doit_session_prime" else real_load(name)
todos: list = []
mod.session_todos = lambda _cwd: ("proj", todos)
mr_answers: dict = {}
lookups: list = []


def fake_has_mr(repo, branch):
    lookups.append((repo, branch))
    return mr_answers.get((repo, branch))


mod.has_mr = fake_has_mr


def run(payload):
    sys.stdin = io.StringIO(json.dumps(payload))
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    return buf.getvalue().strip()


def transcript(*push_outputs):
    path = tmp / f"t{time.time_ns()}.jsonl"
    ts = "2099-01-01T00:00:00Z"
    recs = []
    for i, out in enumerate(push_outputs):
        recs.append(
            {
                "type": "assistant",
                "timestamp": ts,
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": f"u{i}",
                            "name": "Bash",
                            "input": {"command": "git push"},
                        }
                    ]
                },
            }
        )
        recs.append(
            {
                "type": "user",
                "timestamp": ts,
                "message": {
                    "content": [
                        {"type": "tool_result", "tool_use_id": f"u{i}", "content": out}
                    ]
                },
            }
        )
    path.write_text("\n".join(json.dumps(r) for r in recs))
    return str(path)


GITLAB_NEW = (
    "remote: To create a merge request for feat-x, visit:\nremote: \n"
    "To gitlab.rechargeapps.net:ai-tooling/monitor.git\n"
    " * [new branch]      feat-x -> feat-x\n"
    "branch 'feat-x' set up to track 'origin/feat-x'."
)
GITHUB_MAIN = "To github.com:me/cfg.git\n   014e774..c016f8d  HEAD -> main"
REJECTED = "To gitlab.rechargeapps.net:g/p.git\n ! [rejected]        feat-y -> feat-y (fetch first)"
FORCED = "To https://gitlab.rechargeapps.net/g/p.git\n + 1a2b3c...4d5e6f  feat-z -> refs/heads/feat-z (forced update)"

# push parsing: new branch, default branch skipped, rejected skipped, url forms normalized
assert mod.parse_pushes(GITLAB_NEW) == [
    ("gitlab.rechargeapps.net/ai-tooling/monitor", "feat-x")
]
assert mod.parse_pushes(GITHUB_MAIN) == []
assert mod.parse_pushes(REJECTED) == []
assert mod.parse_pushes(FORCED) == [("gitlab.rechargeapps.net/g/p", "feat-z")]
assert mod.repo_of("ssh://git@host:2222/g/p.git") == "host/g/p"
assert mod.repo_of("git@github.com:me/r.git") == "github.com/me/r"

# ready items: claude-only, deps on open items excluded, deps on done items ready
items = [
    {"text": "claude: [bug] 1. fix parser", "done": False},
    {"text": "claude: [chore] 2. wire flag (dep on #3)", "done": False},
    {"text": "[gate] 3. pick flag name", "done": False},
    {"text": "claude: [chore] 4. docs (dep on #5)", "done": False},
    {"text": "claude: [chore] 5. old", "done": True},
    {"text": "[owe] 6. rotate key", "done": False},
]
assert mod.ready_items(items) == [
    "claude: [bug] 1. fix parser",
    "claude: [chore] 4. docs (dep on #5)",
]

# /auto on writes state and reminds; other prompts keep reminding; /auto off clears
out = run(
    {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "s1",
        "prompt": "/auto ship plan.md",
    }
)
assert "AUTO MODE on (scope: ship plan.md)" in out, out
assert mod.read_state(mod.state_path("s1"))["scope"] == "ship plan.md"
assert "AUTO MODE on" in run(
    {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "status?"}
)
assert (
    run(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s2",
            "prompt": "/autocomplete x",
        }
    )
    == ""
)
assert (
    run(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s1",
            "prompt": "/auto off",
        }
    )
    == "AUTO MODE off."
)
assert mod.read_state(mod.state_path("s1")) is None

# stop with mode off: silent
assert (
    run(
        {
            "hook_event_name": "Stop",
            "session_id": "s1",
            "transcript_path": transcript(GITLAB_NEW),
        }
    )
    == ""
)

# stop in auto mode: ready item + pushed branch with no MR -> block naming both
mod.turn_on("s3", "plan.md")
todos[:] = items
key = ("gitlab.rechargeapps.net/ai-tooling/monitor", "feat-x")
mr_answers[key] = False
out = json.loads(
    run(
        {
            "hook_event_name": "Stop",
            "session_id": "s3",
            "transcript_path": transcript(GITLAB_NEW, GITHUB_MAIN),
        }
    )
)
assert out["decision"] == "block"
assert (
    "fix parser" in out["reason"] and "ai-tooling/monitor feat-x" in out["reason"]
), out["reason"]
assert "wire flag" not in out["reason"]

# retry stop passes
assert (
    run(
        {
            "hook_event_name": "Stop",
            "session_id": "s3",
            "stop_hook_active": True,
            "transcript_path": transcript(GITLAB_NEW),
        }
    )
    == ""
)

# MR exists and nothing ready -> pass, and the branch is cached so it is not looked up again
todos[:] = [{"text": "claude: [bug] 1. fix parser", "done": True}]
mr_answers[key] = True
path = transcript(GITLAB_NEW)
assert (
    run({"hook_event_name": "Stop", "session_id": "s3", "transcript_path": path}) == ""
)
lookups.clear()
assert (
    run({"hook_event_name": "Stop", "session_id": "s3", "transcript_path": path}) == ""
)
assert lookups == [], lookups

# lookup failure (None) fails open
mr_answers[("gitlab.rechargeapps.net/g/p", "feat-z")] = None
assert (
    run(
        {
            "hook_event_name": "Stop",
            "session_id": "s3",
            "transcript_path": transcript(FORCED),
        }
    )
    == ""
)

# pushes before auto mode started are ignored
mod.turn_on("s4", "x")
state = mod.read_state(mod.state_path("s4"))
state["started"] = 4102444800 + 1  # after the fixture timestamp
mod.write_state(mod.state_path("s4"), state)
lookups.clear()
assert (
    run(
        {
            "hook_event_name": "Stop",
            "session_id": "s4",
            "transcript_path": transcript(GITLAB_NEW),
        }
    )
    == ""
)
assert lookups == []

print("ok")
