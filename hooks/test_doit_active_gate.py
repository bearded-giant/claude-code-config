import importlib.util
import io
import json
import os
import sys
import tempfile
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


mod = load("doit_active_gate")
prime = load("doit_session_prime")
mod.prime = lambda: prime
links = []
prime.link_window = lambda name, follow=("", "daily"): links.append((name, follow))


def run_hook(payload):
    sys.stdin = io.StringIO(json.dumps(payload))
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    out = buf.getvalue().strip()
    return json.loads(out) if out else None


def write_list(name, todos):
    with open(
        os.path.join(prime.LISTS_DIR, f"{name}.json"), "w", encoding="utf-8"
    ) as fh:
        json.dump({"todos": todos}, fh)


def gate_cases(tmp):
    proj = os.path.join(tmp, "gaterepo")
    os.makedirs(proj)
    os.environ["CLAUDE_PROJECT_DIR"] = proj

    # no list for this repo: nothing to point at, no window to link
    assert run_hook({}) is None
    assert not links

    # only done items: the chip has nothing to show and nothing is next
    write_list("gaterepo", [{"id": "a", "text": "old", "done": True}])
    assert run_hook({}) is None

    # pending with nothing active: block, naming the list
    write_list(
        "gaterepo",
        [
            {"id": "a", "text": "claude: [bug] 1. fix it", "done": False},
            {"id": "b", "text": "[gate] 2. review", "done": False},
        ],
    )
    out = run_hook({})
    assert out and out["decision"] == "block", out
    assert 'list="gaterepo"' in out["reason"] and "(2 pending)" in out["reason"]
    # a list made mid-session gets linked at stop, but a window on daily stays there
    assert links[-1] == ("gaterepo", ("",)), links

    # claude -p children (the session summarizer) have no user and no chip
    os.environ["CLAUDE_CODE_ENTRYPOINT"] = "sdk-cli"
    try:
        assert run_hook({}) is None
    finally:
        os.environ["CLAUDE_CODE_ENTRYPOINT"] = "cli"

    # the retry stop never blocks again
    assert run_hook({"stop_hook_active": True}) is None

    # bypass env silences it
    os.environ[mod.BYPASS_ENV] = "off"
    try:
        assert run_hook({}) is None
    finally:
        del os.environ[mod.BYPASS_ENV]

    # one active item satisfies the gate
    write_list(
        "gaterepo",
        [
            {"id": "a", "text": "claude: [bug] 1. fix it", "done": False},
            {"id": "b", "text": "[gate] 2. review", "done": False, "in_progress": True},
        ],
    )
    assert run_hook({}) is None

    # a done item still flagged in_progress is not an active one
    write_list(
        "gaterepo",
        [
            {"id": "a", "text": "claude: [bug] 1. fix it", "done": False},
            {"id": "b", "text": "old", "done": True, "in_progress": True},
        ],
    )
    out = run_hook({})
    assert out and "(1 pending)" in out["reason"], out


def dispatch_cases(tmp):
    dispatch = load("dispatch")
    hooks = Path(tmp, "hooks")
    hooks.mkdir()
    for name, reason in (("gate_a", "first"), ("gate_b", "second")):
        Path(hooks, f"{name}.py").write_text(
            "import json\n"
            "def main():\n"
            f"    print(json.dumps({{'decision': 'block', 'reason': {reason!r}}}))\n",
            encoding="utf-8",
        )
    Path(hooks, "ctx.py").write_text(
        "def main():\n    print('note')\n", encoding="utf-8"
    )
    dispatch.HOOKS = hooks
    saved = sys.argv
    sys.argv = ["dispatch.py", "--event", "Stop", "gate_a", "ctx", "gate_b"]
    sys.stdin = io.StringIO("{}")
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            dispatch.main()
    finally:
        sys.argv = saved
    out = json.loads(buf.getvalue())
    # both blocks reach the model, the plain context does not ride along
    assert out == {"decision": "block", "reason": "first\n\nsecond"}, out


def main():
    os.environ.pop("TMUX", None)
    os.environ["CLAUDE_CODE_ENTRYPOINT"] = "cli"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = os.path.realpath(tmp)
        os.makedirs(os.path.join(tmp, "lists"))
        saved = prime.LISTS_DIR
        prime.LISTS_DIR = os.path.join(tmp, "lists")
        try:
            gate_cases(tmp)
            dispatch_cases(tmp)
        finally:
            prime.LISTS_DIR = saved
    print("ok")


if __name__ == "__main__":
    main()
