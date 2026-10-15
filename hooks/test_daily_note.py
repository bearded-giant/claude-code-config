import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "daily_note", Path(__file__).with_name("daily_note.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

DAY = dt.date(2026, 10, 15)
TEMPLATE = """---
id: dailytemplate
aliases: []
tags: [daily]
area: ""
project: ""
---


{yesterday} - {tomorrow}

---

## TODO

- [ ] -

---

## NOTES




---

## CLAUDE SESSIONS


---

## CLAUDE LINKS


---
"""


def run(data, entry="cli"):
    os.environ["CLAUDE_CODE_ENTRYPOINT"] = entry
    sys.stdin = io.StringIO(json.dumps(data))
    with contextlib.redirect_stdout(io.StringIO()) as out:
        mod.main()
    sys.stdin = sys.__stdin__
    return out.getvalue()


def today_text():
    return mod.note_path(mod.local_now().date()).read_text(encoding="utf-8")


def main() -> None:
    os.environ.pop("TMUX", None)
    with tempfile.TemporaryDirectory() as d:
        vault = Path(d) / "vault"
        (vault / "templates").mkdir(parents=True)
        (vault / "templates" / "dailytemplate.md").write_text(TEMPLATE)
        vars(mod)["VAULT"] = vault
        repo = Path(d) / "proj"
        repo.mkdir()

        # template renders with linked neighbours and the date as id
        text = mod.render_template(DAY)
        assert "[[2026-10-14]] - [[2026-10-16]]" in text, text
        assert "id: 2026-10-15" in text and "dailytemplate" not in text

        # lines land inside their section, in order, before the closing rule
        text = mod.insert_under(text, mod.LINKS, "- a")
        text = mod.insert_under(text, mod.LINKS, "- b")
        links = text.split(mod.LINKS, 1)[1]
        assert links.startswith("\n\n- a\n- b\n"), repr(links[:40])
        assert "- a" not in mod.section(text, mod.SESSIONS)

        # a note from the old template grows both sections at the end
        old = "## NOTES\n\nmine [[x]]\n\n---\n"
        grown = mod.insert_under(old, mod.SESSIONS, "- s")
        assert grown.index("mine") < grown.index(mod.SESSIONS)

        base = {
            "cwd": str(repo),
            "session_id": "abcdef1234567890",
            "transcript_path": "/x/projects/-slug-proj/abcdef1234567890.jsonl",
        }

        # interactive session start writes one session line; headless does not
        run(
            {**base, "hook_event_name": "SessionStart", "source": "startup"},
            entry="sdk-cli",
        )
        assert not mod.note_path(mod.local_now().date()).exists()
        run({**base, "hook_event_name": "SessionStart", "source": "startup"})
        run({**base, "hook_event_name": "SessionStart", "source": "resume"})
        text = today_text()
        assert text.count("claude --resume abcdef1234567890") == 1
        assert f"cd {repo} &&" in text and "proj" in mod.section(text, mod.SESSIONS)
        assert f"[bundle](file://{mod.BUNDLES}/-slug-proj/abcdef1234567890)" in text

        # artifact publish logs title + url once
        html = Path(d) / "page.html"
        html.write_text("<html><head><title>Daily Inbox</title></head></html>")
        art = {
            **base,
            "hook_event_name": "PostToolUse",
            "tool_name": "Artifact",
            "tool_input": {"file_path": str(html)},
            "tool_response": "Published https://claude.ai/code/artifact/1234-abcd (private)",
        }
        run(art)
        run(art)
        links = mod.section(today_text(), mod.LINKS)
        assert (
            links.count("[Daily Inbox](https://claude.ai/code/artifact/1234-abcd)") == 1
        )
        assert "s:abcdef12" in links

        # reads, asset uploads, and failed publishes log nothing
        run({**art, "tool_input": {"action": "read", "url": "x"}})
        run(
            {
                **art,
                "tool_input": {"file_path": str(html), "asset": True},
                "tool_response": "https://claude.ai/code/artifact/zz",
            }
        )
        run({**art, "tool_response": "refused"})
        assert "artifact/zz" not in today_text()

        # vault writes log a wiki link; daily notes and non-vault files do not
        note = vault / "areas" / "auth" / "sessions" / "redis-keys.md"
        note.parent.mkdir(parents=True)
        note.write_text("x")
        write = {**base, "hook_event_name": "PostToolUse", "tool_name": "Write"}
        run({**write, "tool_input": {"file_path": str(note)}})
        run({**write, "tool_input": {"file_path": str(mod.note_path(DAY))}})
        run({**write, "tool_input": {"file_path": str(repo / "x.md")}})
        links = mod.section(today_text(), mod.LINKS)
        assert "vault [[redis-keys]]" in links
        assert "[[2026-10-15]]" not in links and "x.md" not in links

        # note.py new via Bash: path read from stdout
        bash = {
            **base,
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {
                "command": "python3 ~/.claude/skills/obsidian-note/scripts/note.py new --title T"
            },
            "tool_response": {
                "stdout": str(vault / "areas" / "infra" / "k8s.md") + "\n"
            },
        }
        (vault / "areas" / "infra").mkdir()
        run(bash)
        assert "vault [[k8s]]" in today_text()

        # handoff writes link the file
        handoff = repo / ".giantmem" / "handoff.md"
        run({**write, "tool_input": {"file_path": str(handoff)}})
        assert f"handoff [handoff]({handoff})" in today_text()

        # garbage stdin never raises
        sys.stdin = io.StringIO("nope")
        mod.main()
        sys.stdin = sys.__stdin__
    print("ok")


if __name__ == "__main__":
    main()
