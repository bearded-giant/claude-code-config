import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "dispatch", Path(__file__).with_name("dispatch.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

HOOKS = {
    "plain": "def main():\n    print('plain text')\n",
    "notice": (
        "import json\n"
        "def main():\n"
        "    print(json.dumps({'systemMessage': 'see /x.md', 'hookSpecificOutput':"
        " {'hookEventName': 'SessionStart', 'additionalContext': 'notice ctx'}}))\n"
    ),
    "bare_notice": (
        "import json\ndef main():\n    print(json.dumps({'systemMessage': 'only msg'}))\n"
    ),
    "block": (
        "import json\ndef main():\n"
        "    print(json.dumps({'decision': 'block', 'reason': 'no'}))\n"
    ),
    "silent": "def main():\n    pass\n",
}


def run(argv, payload):
    sys.argv = ["dispatch.py", *argv]
    sys.stdin = io.StringIO(json.dumps(payload))
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    return buf.getvalue().strip()


def main():
    with tempfile.TemporaryDirectory() as d:
        for name, src in HOOKS.items():
            (Path(d) / f"{name}.py").write_text(src)
        vars(mod).update(HOOKS=Path(d))
        start = {"hook_event_name": "SessionStart"}

        assert run(["plain", "silent"], start) == "plain text"

        out = json.loads(run(["plain", "notice"], start))
        assert out == {
            "systemMessage": "see /x.md",
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "plain text\n\nnotice ctx",
            },
        }

        assert json.loads(run(["bare_notice", "notice"], start))["systemMessage"] == (
            "only msg\nsee /x.md"
        )
        assert json.loads(run(["bare_notice"], start)) == {"systemMessage": "only msg"}

        # no event name anywhere: plain stdout, the user message has nowhere to go
        assert run(["plain", "notice"], {}) == "plain text\n\nnotice ctx"

        out = json.loads(run(["--event", "Stop", "notice", "plain"], {}))
        assert out["hookSpecificOutput"]["hookEventName"] == "Stop"

        assert json.loads(run(["notice", "block"], start)) == {
            "decision": "block",
            "reason": "no",
        }
    print("ok")


if __name__ == "__main__":
    main()
