import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "voice_gate", Path(__file__).with_name("voice_gate.py")
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(tool, cwd, **tool_input):
    sys.stdin = io.StringIO(
        json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": cwd})
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    out = buf.getvalue().strip()
    return json.loads(out)["reason"] if out else ""


def bash(cwd, command):
    return run("Bash", cwd, command=command)


def main():
    with tempfile.TemporaryDirectory() as d:
        good, bad = Path(d, "good.md"), Path(d, "bad.md")
        good.write_text(
            "`skip` fetches the upstream remote first now", encoding="utf-8"
        )
        bad.write_text(
            "Fixed: I added a guard — see config_change.py:486 for details.",
            encoding="utf-8",
        )
        notes = '"projects/x/merge_requests/1/discussions/abc/notes"'

        # clean babysit reply via -F body=@file passes
        assert bash(d, f"glab api -X POST {notes} -F body=@{good}") == ""

        # drift caught: capitalized start, first person, dash, unbackticked file
        reason = bash(d, f"glab api -X POST {notes} -F body=@{bad}")
        for want in ("capitalized", "first person", "dash", "config_change.py:486"):
            assert want in reason, (want, reason)
        assert "config_change," not in reason, reason

        # body written by heredoc in the same command, posted via $(cat file)
        cmd = (
            "cd " + d + " && cat > note.md <<'EOF'\nThe fix looks good, I think.\nEOF\n"
            'glab mr note create 7 -R g/p -m "$(cat note.md)"'
        )
        assert "first person" in bash(d, cmd)

        # heredoc to md, then python builds the json the post reads (seen in real sessions)
        cmd = (
            "cat > n.md <<'EOF'\nPossibly material.\nEOF\n"
            "python3 -c 'import json' > n.json && glab api -X POST \"projects/x/merge_requests/1/discussions\" --input n.json"
        )
        assert "capitalized" in bash(d, cmd)

        # reads, approvals, resolves, and non-posting commands pass untouched
        assert (
            bash(d, f"glab api {notes[:-7]}?per_page=100\" | python3 -c 'print(1)'")
            == ""
        )
        assert (
            bash(
                d,
                f'glab api -X PUT "projects/x/merge_requests/1/discussions/abc" -f resolved=true',
            )
            == ""
        )
        assert bash(d, "gh pr review 5 --approve") == ""
        assert bash(d, "ls -la && git status") == ""
        assert (
            bash(d, 'gh pr create --title x --body "Big Formal Description — here"')
            == ""
        )

        # unreadable body blocks with instructions
        assert "can't read" in bash(d, f'glab api -X POST {notes} -f body="$REPLY"')

        # verbatim bypass
        assert bash(d, f"VOICE_GATE=off glab api -X POST {notes} -F body=@{bad}") == ""

        # literal -m and gh body flags
        assert "capitalized" in bash(
            d, 'glab mr note create 3 -m "Thanks, this is fine."'
        )
        assert bash(d, 'gh pr comment 4 --body "`foo` handled in tests now"') == ""

        # slack allows first person, still wants backticks and lowercase
        slack = "mcp__plugin_slack_slack__slack_send_message_draft"
        assert (
            run(slack, d, channel_id="C1", message="I'll wire google auth tonight")
            == ""
        )
        assert "backticks" in run(
            slack, d, channel_id="C1", message="churn_excess_attribution fails at 20s"
        )
        jira = "mcp__plugin_kai_atlassian__addCommentToJiraIssue"
        assert "first person" in run(
            jira, d, cloudId="c", issueIdOrKey="PE-1", commentBody="my take: ship it"
        )

        # length cap per surface
        long_reply = " ".join(["word"] * 90)
        good.write_text(long_reply, encoding="utf-8")
        assert "cap is 80" in bash(d, f"glab api -X POST {notes} -F body=@{good}")
    print("ok")


if __name__ == "__main__":
    main()
