import importlib.util
import json
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "session_bundle", Path(__file__).with_name("session_bundle.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SID = "11111111-2222-3333-4444-555555555555"
SLUG = "-Users-me-dev-proj"


def write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        tmp_root = root / "tmp" / "claude-502"
        vars(mod).update(
            TMP_GLOB=str(root / "tmp" / "claude-*"),
            PROJECTS=root / "projects",
            BUNDLES=root / "archive" / "bundles",
        )
        sess = tmp_root / SLUG / SID
        write(sess / "scratchpad" / "query.py", "print(1)")
        write(sess / "scratchpad" / "fix.patch")
        write(sess / "scratchpad" / ".venv" / "lib" / "big.py")
        write(sess / "scratchpad" / "pkg" / "__pycache__" / "m.pyc")
        write(sess / "tasks" / "b123.output", "bash out")
        write(sess / "scratchpad" / "zd-venv" / "pyvenv.cfg")
        write(sess / "scratchpad" / "zd-venv" / "lib" / "site.py")
        write(sess / "scratchpad" / "chrome-ud5" / "Local State")
        write(sess / "scratchpad" / "chrome-ud5" / "Default" / "Cookies")
        write(sess / "scratchpad" / "notes" / "keep.md")
        write(sess / "scratchpad" / "snap" / ".env", "TOKEN=x")
        write(sess / "scratchpad" / "snap" / ".env.example")
        claude = mod.PROJECTS / SLUG / SID
        write(claude / "subagents" / "agent-a1.jsonl", "{}")
        write(claude / "workflows" / "scripts" / "wf-x.js", "export const meta = {}")
        (sess / "tasks" / "a1.output").symlink_to(
            claude / "subagents" / "agent-a1.jsonl"
        )
        transcript = mod.PROJECTS / SLUG / f"{SID}.jsonl"
        write(
            transcript,
            "\n".join(
                json.dumps(r)
                for r in [
                    {"type": "mode"},
                    {
                        "type": "user",
                        "cwd": "/Users/me/dev/proj",
                        "gitBranch": "main",
                        "timestamp": "2026-10-15T08:00:00Z",
                        "message": {"content": "<command-name>/x</command-name>"},
                    },
                    {
                        "type": "user",
                        "message": {
                            "content": [{"type": "text", "text": "find the  churn bug"}]
                        },
                    },
                ]
            ),
        )
        with open(sess / "scratchpad" / "huge.bin", "wb") as fh:
            fh.truncate(21 * 1024 * 1024)

        # a Stop sync copies the tmp side only, minus junk, oversize files, and symlinks
        dest = mod.capture(
            SLUG, SID, mod.tmp_dirs(SID), full=False, transcript=transcript
        )
        assert dest == mod.BUNDLES / SLUG / SID
        assert (dest / "scratchpad" / "query.py").read_text() == "print(1)"
        assert (dest / "tasks" / "b123.output").exists()
        assert not (dest / "scratchpad" / ".venv").exists()
        assert not (dest / "scratchpad" / "pkg" / "__pycache__").exists()
        assert not (dest / "scratchpad" / "zd-venv").exists()
        assert not (dest / "scratchpad" / "chrome-ud5").exists()
        assert (dest / "scratchpad" / "notes" / "keep.md").exists()
        assert not (dest / "scratchpad" / "snap" / ".env").exists()
        assert (dest / "scratchpad" / "snap" / ".env.example").exists()
        assert not (dest / "scratchpad" / "huge.bin").exists()
        assert not (dest / "tasks" / "a1.output").exists()
        assert not (dest / "claude").exists()

        # a full sync adds subagents, workflow scripts, and the transcript
        mod.capture(SLUG, SID, mod.tmp_dirs(SID), full=True, transcript=transcript)
        assert (dest / "claude" / "subagents" / "agent-a1.jsonl").exists()
        assert (dest / "claude" / "workflows" / "scripts" / "wf-x.js").exists()
        assert (dest / "claude" / "transcript.jsonl").exists()

        man = json.loads((dest / "bundle.json").read_text())
        kinds = {f["path"]: f["kind"] for f in man["files"]}
        assert kinds["scratchpad/query.py"] == "script"
        assert kinds["scratchpad/fix.patch"] == "patch"
        assert kinds["tasks/b123.output"] == "log"
        assert kinds["claude/workflows/scripts/wf-x.js"] == "workflow"
        assert kinds["claude/transcript.jsonl"] == "transcript"
        assert man["cwd"] == "/Users/me/dev/proj" and man["branch"] == "main"
        assert man["first_prompt"] == "find the churn bug", man.get("first_prompt")
        assert man["resume"] == f"claude --resume {SID}"

        # the archive keeps files the session later deleted
        (sess / "scratchpad" / "query.py").unlink()
        write(sess / "scratchpad" / "later.sh")
        mod.capture(SLUG, SID, mod.tmp_dirs(SID), full=False, transcript=transcript)
        assert (dest / "scratchpad" / "query.py").exists() and (
            dest / "scratchpad" / "later.sh"
        ).exists()

        # an empty session makes no bundle
        other = "99999999-2222-3333-4444-555555555555"
        (tmp_root / SLUG / other / "scratchpad").mkdir(parents=True)
        assert mod.capture(SLUG, other, mod.tmp_dirs(other), full=True) is None
        assert not (mod.BUNDLES / SLUG / other).exists()

        # a held lock means another worker is mid-sync: skip, don't block
        import fcntl

        with open(dest / mod.LOCK, "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            assert mod.capture(SLUG, SID, mod.tmp_dirs(SID), full=False) is None

        # a full sync waits for the lock instead of skipping
        import threading

        with open(dest / mod.LOCK, "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            threading.Timer(0.3, fcntl.flock, (held, fcntl.LOCK_UN)).start()
            assert mod.capture(SLUG, SID, mod.tmp_dirs(SID), full=True) == dest

        # only the SessionEnd sync re-runs the bundle ingest that session_end_ingest may have raced
        calls = []
        vars(mod).update(reingest=lambda: calls.append(1))
        mod.worker(SID, "Stop", str(transcript))
        mod.worker(SID, "PreCompact", str(transcript))
        assert calls == [], calls
        mod.worker(SID, "SessionEnd", str(transcript))
        assert calls == [1], calls

        # backfill walks <root>/<slug>/<sid> and skips non-session dirs
        desk = root / "desktop" / SLUG
        write(desk / "aaaaaaaa-2222-3333-4444-555555555555" / "scratchpad" / "saved.py")
        write(desk / "not-a-session" / "scratchpad" / "x.py")
        made = mod.backfill([str(root / "desktop")])
        assert [p.name for p in made] == ["aaaaaaaa-2222-3333-4444-555555555555"], made

    print("ok")


if __name__ == "__main__":
    main()
