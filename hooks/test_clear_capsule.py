import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "clear_capsule", Path(__file__).with_name("clear_capsule.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def write_transcript(path):
    rows = [
        {"type": "user", "message": {"content": "old ask before compact"}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "pre-compact reply"},
                    {
                        "type": "tool_use",
                        "name": "Write",
                        "input": {"file_path": "/r/early.py"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "isCompactSummary": True,
            "message": {"content": "SUMMARY of earlier work"},
        },
        {"type": "user", "message": {"content": "fix the login redirect"}},
        {"type": "user", "isMeta": True, "message": {"content": "meta noise"}},
        {"type": "user", "message": {"content": "<command-name>/model</command-name>"}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "thinking", "thinking": ""},
                    {"type": "thinking", "thinking": "auth bug confirmed"},
                    {"type": "text", "text": "editing auth"},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {"file_path": "/r/auth.py"},
                    },
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "git   commit -m 'fix: redirect'"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "TOOL OUTPUT"}]},
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
            "message": {"content": [{"type": "text", "text": "DONE"}]},
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")


def run(payload):
    sys.stdin = io.StringIO(json.dumps(payload))
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    return buf.getvalue()


def check_extract(tp):
    text = mod.extract(mod.load(str(tp)))
    assert text.startswith("COMPACTED EARLIER PART:\nSUMMARY of earlier work")
    assert "old ask before compact" not in text and "pre-compact reply" not in text
    assert "USER: fix the login redirect" in text and "USER: now add a test" in text
    assert "ASSISTANT: editing auth" in text and "ASSISTANT: DONE" in text
    assert "ASSISTANT (thinking): auth bug confirmed" in text
    assert "ASSISTANT (thinking): \n" not in text
    assert "TOOL Bash: git commit -m 'fix: redirect'" in text
    assert "TOOL OUTPUT" not in text and "subagent chatter" not in text
    assert "meta noise" not in text and "/model" not in text
    assert text.endswith("EDITED FILES:\n/r/early.py\n/r/auth.py")
    assert mod.extract(mod.load("/nonexistent.jsonl")) == ""

    vars(mod).update(EXTRACT_MAX=150, EXTRACT_HEAD=50)
    capped = mod.extract(mod.load(str(tp)))
    assert len(capped) < len(text) and "[... middle dropped ...]" in capped
    assert capped.startswith("COMPACTED") and capped.endswith("/r/auth.py")
    vars(mod).update(EXTRACT_MAX=240_000, EXTRACT_HEAD=20_000)


def check_paths(d):
    now = datetime(2026, 10, 24, 9, 30, 5, tzinfo=timezone.utc)
    repo = Path(d) / "repo"
    (repo / "sub").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    # the repo, not the subdir the session started in, names the project
    got = mod.handoff_path(str(repo / "sub"), "abcdef123456", now)
    assert got == Path(d) / "vault/handoffs/repo/clear/20261024_093005_abcdef12.md"
    (Path(d) / "loose").mkdir()
    assert mod.handoff_path(str(Path(d) / "loose"), "abcdef123456", now) == (
        Path(d) / "vault/handoffs/loose/clear/20261024_093005_abcdef12.md"
    )


def check_writer(d, tp):
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return "## Start here\nship it"

    out = Path(d) / "vault/handoffs/repo/clear/h.md"
    vars(mod).update(summarize=fake)
    mod.write_handoff("abcdef123456", str(tp), out)
    note = out.read_text()
    assert note.startswith("---\ntype: handoff\nstatus: ready\nrepo: repo\n")
    assert "lifecycle: candidate\nsession: abcdef123456\n" in note
    assert "`claude --resume abcdef123456`" in note and "## Start here\nship it" in note
    assert "Drop tool output that was read once" in seen["prompt"]
    assert "never copy a secret" in seen["prompt"]
    assert "<session>\nCOMPACTED EARLIER PART" in seen["prompt"]
    assert not list(out.parent.glob("*.tmp"))

    vars(mod).update(summarize=lambda _prompt: "")
    fallback = out.with_name("f.md")
    mod.write_handoff("abcdef123456", str(tp), fallback)
    note = fallback.read_text()
    assert "Summarizer failed" in note
    assert "USER: now add a test" in note


def check_main(d, tp):
    spawned = []
    vars(mod).update(
        MARKER_DIR=Path(d),
        claude_proc=lambda: (42, "Mon Oct 20 09:00:00 2026"),
        spawn=lambda *a: spawned.append(a),
    )
    # startup records the session and says nothing
    assert (
        run({"source": "startup", "session_id": "old-sid", "transcript_path": str(tp)})
        == ""
    )
    out = json.loads(
        run(
            {
                "source": "clear",
                "session_id": "new-sid",
                "cwd": str(Path(d) / "repo"),
                "transcript_path": str(Path(d) / "new.jsonl"),
            }
        )
    )
    path = str(Path(d) / "vault/handoffs/repo/clear")
    assert out["systemMessage"].startswith(
        f"handoff for cleared session old-sid: {path}/"
    )
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "cleared session old-sid" in ctx and "claude --resume old-sid" in ctx
    assert ctx.endswith(
        "last asks:\n- old ask before compact\n- fix the login redirect\n"
        "- now add a test\n</system-reminder>"
    )
    assert "SUMMARY" not in ctx
    assert spawned == [
        ("old-sid", str(tp), Path(out["systemMessage"].split(": ", 1)[1]))
    ]

    # the clear re-keyed the marker, so a second clear points at new-sid (empty transcript: silent)
    assert run({"source": "clear", "session_id": "newer-sid"}) == ""
    assert len(spawned) == 1

    # a marker left by a dead process with the same pid is ignored
    (Path(d) / "claude-clear-capsule-42.json").write_text(
        json.dumps(
            {"session_id": "old-sid", "transcript_path": str(tp), "lstart": "other"}
        )
    )
    assert run({"source": "clear", "session_id": "new-sid"}) == ""
    assert len(spawned) == 1


def main():
    with tempfile.TemporaryDirectory() as d:
        os.environ["OBSIDIAN_VAULT"] = str(Path(d) / "vault")
        tp = Path(d) / "old.jsonl"
        write_transcript(tp)
        check_extract(tp)
        check_paths(d)
        check_writer(d, tp)
        check_main(d, tp)
    print("ok")


if __name__ == "__main__":
    main()
