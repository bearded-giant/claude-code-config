import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "session_label", Path(__file__).with_name("session_label.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SENT = []
vars(mod).update(send_color=lambda pane, color: SENT.append((pane, color)))


def run(payload, **env):
    saved = {
        k: os.environ.get(k)
        for k in (
            "CLAUDE_CODE_ENTRYPOINT",
            "TMUX_PANE",
            "CLAUDE_PID",
            "CLAUDE_PROJECT_DIR",
        )
    }
    for k in saved:
        os.environ.pop(k, None)
    os.environ.update(env)
    sys.stdin = io.StringIO(json.dumps(payload))
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            mod.main()
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    out = buf.getvalue().strip()
    return json.loads(out)["hookSpecificOutput"]["sessionTitle"] if out else None


def write_features(root, features):
    d = Path(root) / ".giantmem" / "features"
    d.mkdir(parents=True, exist_ok=True)
    (d / "features.json").write_text(json.dumps(features))


def add_row(transcript, row):
    with open(transcript, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def feature_shapes(root):
    assert mod.active_feature(root) is None
    write_features(
        root, {"a": {"name": "a", "status": "complete"}, "b": {"status": "in_progress"}}
    )
    assert mod.active_feature(root) == "b"
    write_features(root, {"features": [{"name": "c", "status": "in_progress"}]})
    assert mod.active_feature(root) == "c"
    write_features(root, {"features": {"d": {"name": "d", "status": "in_progress"}}})
    assert mod.active_feature(root) == "d"
    write_features(root, {"a": {"name": "a", "status": "paused"}})
    assert mod.active_feature(root) is None


def transcript_scan(d):
    t = Path(d) / "scan.jsonl"
    add_row(t, {"type": "ai-title", "aiTitle": "first"})
    # the marker quoted inside a tool result is escaped, so it must not count as a row
    add_row(t, {"type": "user", "content": '{"type":"ai-title","aiTitle":"fake"}'})
    assert mod.last_row(t.read_bytes(), "ai-title")["aiTitle"] == "first"
    add_row(t, {"type": "ai-title", "aiTitle": "second"})
    assert mod.last_row(t.read_bytes(), "ai-title")["aiTitle"] == "second"
    assert mod.last_row(b"", "ai-title") is None


def flows(d):
    root = Path(d) / "repo"
    root.mkdir()
    env = {"CLAUDE_PROJECT_DIR": str(root)}
    t = Path(d) / "s1.jsonl"
    start = {
        "hook_event_name": "SessionStart",
        "session_id": "s1",
        "source": "startup",
        "transcript_path": str(t),
    }
    ups = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "s1",
        "transcript_path": str(t),
        "prompt": "hi",
    }

    write_features(root, {"foo": {"name": "foo", "status": "in_progress"}})
    assert run(start, **env) == "foo"
    assert run(ups, **env) is None

    # a created feature names the session at once, even when it lands pending behind foo
    assert run({**ups, "prompt": "/new-feature bar --branch=x"}, **env) == "bar"
    assert run(ups, **env) is None
    write_features(root, {"baz": {"name": "baz", "status": "in_progress"}})
    assert run(ups, **env) == "baz"
    assert run(ups, **env) is None

    # no feature: wait for claude code's ai-title, promote it once
    write_features(root, {})
    t2 = Path(d) / "s2.jsonl"
    ups2 = {**ups, "session_id": "s2", "transcript_path": str(t2)}
    assert run({**start, "session_id": "s2"}, **env) is None
    assert run(ups2, **env) is None
    add_row(t2, {"type": "ai-title", "aiTitle": "Fix flaky login test"})
    assert run(ups2, **env) == "Fix flaky login test"
    add_row(t2, {"type": "ai-title", "aiTitle": "Something else"})
    assert run(ups2, **env) is None

    # a name the user gave (/rename, --name) is kept
    t3 = Path(d) / "s3.jsonl"
    add_row(t3, {"type": "custom-title", "customTitle": "mine"})
    add_row(t3, {"type": "ai-title", "aiTitle": "theirs"})
    assert run({**ups, "session_id": "s3", "transcript_path": str(t3)}, **env) is None

    # resume does not rename over whatever the session already carries
    write_features(root, {"foo": {"name": "foo", "status": "in_progress"}})
    t4 = Path(d) / "s4.jsonl"
    add_row(t4, {"type": "custom-title", "customTitle": "old name"})
    resume = {
        **start,
        "session_id": "s4",
        "source": "resume",
        "transcript_path": str(t4),
    }
    assert run(resume, **env) is None
    assert run({**ups, "session_id": "s4", "transcript_path": str(t4)}, **env) is None

    assert (
        run({**start, "session_id": "s5"}, CLAUDE_CODE_ENTRYPOINT="sdk-cli", **env)
        is None
    )


def colors(d):
    root = Path(d) / "repo2"
    root.mkdir()
    env = {"CLAUDE_PROJECT_DIR": str(root), "TMUX_PANE": "%7", "CLAUDE_PID": "4242"}
    ups = {"hook_event_name": "UserPromptSubmit", "prompt": "hi"}

    SENT.clear()
    run(
        {**ups, "session_id": "c1", "transcript_path": str(Path(d) / "c1.jsonl")}, **env
    )
    run(
        {**ups, "session_id": "c1", "transcript_path": str(Path(d) / "c1.jsonl")}, **env
    )
    assert len(SENT) == 1 and SENT[0][0] == "%7" and SENT[0][1] in mod.COLORS, SENT

    # after /clear the same claude process re-sends the same color
    run(
        {**ups, "session_id": "c2", "transcript_path": str(Path(d) / "c2.jsonl")}, **env
    )
    assert len(SENT) == 2 and SENT[1] == SENT[0], SENT

    colored = Path(d) / "c3.jsonl"
    add_row(colored, {"type": "agent-color", "agentColor": "red"})
    run({**ups, "session_id": "c3", "transcript_path": str(colored)}, **env)
    run(
        {"hook_event_name": "SessionStart", "session_id": "c4", "source": "startup"},
        **env
    )
    run({**ups, "session_id": "c5"}, CLAUDE_PROJECT_DIR=str(root))
    assert len(SENT) == 2, SENT


def main():
    with tempfile.TemporaryDirectory() as d:
        vars(mod).update(STATE_DIR=Path(d) / "state")
        feature_shapes(Path(d) / "shapes")
        transcript_scan(d)
        flows(d)
        colors(d)
    print("ok")


if __name__ == "__main__":
    main()
