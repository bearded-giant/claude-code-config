import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "clear_capsule", Path(__file__).with_name("clear_capsule.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def write_transcript(path):
    rows = [
        {"type": "user", "message": {"content": "fix the login redirect"}},
        {"type": "user", "isMeta": True, "message": {"content": "meta noise"}},
        {"type": "user", "message": {"content": "<command-name>/model</command-name>"}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "editing auth"},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/r/auth.py"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/r/read.py"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "ok"}]},
        },
        {
            "type": "assistant",
            "isSidechain": True,
            "message": {"content": [{"type": "text", "text": "subagent chatter"}]},
        },
        {
            "type": "user",
            "message": {"content": [{"type": "text", "text": "now add a test"}]},
        },
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "x" * 800 + "DONE"}]},
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")


def run(payload):
    sys.stdin = io.StringIO(json.dumps(payload))
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    return buf.getvalue()


def main():
    with tempfile.TemporaryDirectory() as d:
        tp = Path(d) / "old.jsonl"
        write_transcript(tp)

        text = mod.capsule("old-sid", str(tp))
        assert "claude --resume old-sid" in text
        assert "- fix the login redirect" in text and "- now add a test" in text
        assert "meta noise" not in text and "/model" not in text
        assert "subagent chatter" not in text
        assert "edited: /r/auth.py" in text and "read.py" not in text
        assert "(tail):" in text and text.endswith("DONE\n</system-reminder>")
        assert mod.capsule("x", str(Path(d) / "missing.jsonl")) == ""

        vars(mod).update(
            MARKER_DIR=Path(d), claude_proc=lambda: (42, "Mon Oct 20 09:00:00 2026")
        )
        # startup records the session and says nothing
        assert (
            run(
                {
                    "source": "startup",
                    "session_id": "old-sid",
                    "transcript_path": str(tp),
                }
            )
            == ""
        )
        out = run(
            {
                "source": "clear",
                "session_id": "new-sid",
                "transcript_path": str(Path(d) / "new.jsonl"),
            }
        )
        assert "cleared session old-sid" in out
        # the clear re-keyed the marker, so a second clear points at new-sid (empty transcript: silent)
        assert run({"source": "clear", "session_id": "newer-sid"}) == ""

        # a marker left by a dead process with the same pid is ignored
        (Path(d) / "claude-clear-capsule-42.json").write_text(
            json.dumps(
                {"session_id": "old-sid", "transcript_path": str(tp), "lstart": "other"}
            )
        )
        assert run({"source": "clear", "session_id": "new-sid"}) == ""
    print("ok")


if __name__ == "__main__":
    main()
