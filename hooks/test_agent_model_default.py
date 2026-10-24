import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "agent_model_default", Path(__file__).with_name("agent_model_default.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(tool_input):
    sys.stdin = io.StringIO(json.dumps({"tool_input": tool_input}))
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    out = buf.getvalue().strip()
    return json.loads(out)["hookSpecificOutput"]["updatedInput"] if out else None


def main():
    assert run({"subagent_type": "Explore", "prompt": "p"}) == {
        "subagent_type": "Explore",
        "prompt": "p",
        "model": "sonnet",
    }
    # omitted subagent_type spawns general-purpose
    assert (run({"prompt": "p"}) or {}).get("model") == "sonnet"
    # an explicit model is the caller's call, never overridden
    assert run({"subagent_type": "Explore", "model": "opus"}) is None
    # agents outside the table keep their own frontmatter model
    assert run({"subagent_type": "debugger"}) is None
    assert run({"subagent_type": "fork"}) is None
    print("ok")


if __name__ == "__main__":
    main()
