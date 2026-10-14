import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
SOCK = f"test-request-attention-{os.getpid()}"
tmp = Path(tempfile.mkdtemp())

# fake terminal-notifier logs one line per notification
(tmp / "terminal-notifier").write_text(f'#!/bin/sh\necho "$@" >> "{tmp}/notified"\n')
(tmp / "terminal-notifier").chmod(0o755)


def tmux(*args):
    return subprocess.run(
        ["tmux", "-L", SOCK, "-f", "/dev/null", *args],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


tmux("new-session", "-d", "-s", "t", "sleep 60")
pane = tmux("display-message", "-p", "-t", "t", "#{pane_id}")
env = {
    **os.environ,
    "TMUX": tmux("display-message", "-p", "#{socket_path}") + ",0,0",
    "TMUX_PANE": pane,
    "PATH": f"{tmp}:{os.environ['PATH']}",
}


def attention(*args):
    subprocess.run(
        [sys.executable, str(HERE / "request_attention.py"), *args], env=env, check=True
    )


def state(arg):
    subprocess.run(
        ["bash", str(HERE / "claude_tmux_state.sh"), arg],
        env=env,
        input="",
        text=True,
        check=True,
    )


def opt(name):
    return tmux("show-option", "-pqv", "-t", pane, name)


def notified():
    f = tmp / "notified"
    return len(f.read_text().splitlines()) if f.exists() else 0


try:
    attention("MR !1: 1 thread(s) need your sign-off")
    assert opt("@claude_attention") == "MR !1: 1 thread(s) need your sign-off"
    assert notified() == 1

    # same reason on the next babysit run: flag stays, no second notification
    attention("MR !1: 1 thread(s) need your sign-off")
    assert notified() == 1

    # a /loop tick submits: flag drops, state busy, dedupe memory kept
    state("submit")
    assert opt("@claude_attention") == ""
    assert opt("@claude_state") == "busy"
    attention("MR !1: 1 thread(s) need your sign-off")
    assert opt("@claude_attention") != ""
    assert notified() == 1

    attention("MR !1 ready: pipeline green")
    assert notified() == 2

    # tmux's claude-ack.sh acks the reason on focus; a babysit re-raise of it keeps the ack
    tmux("set-option", "-p", "-t", pane, "@claude_attention_ack", "MR !1 ready: pipeline green")
    state("submit")
    attention("MR !1 ready: pipeline green")
    assert opt("@claude_attention_ack") == opt("@claude_attention")

    # nothing pending: clear forgets the reason, so the same reason notifies again later
    attention("--clear")
    assert opt("@claude_attention") == "" and opt("@claude_attention_sent") == ""
    assert opt("@claude_attention_ack") == ""
    attention("MR !1 ready: pipeline green")
    assert notified() == 3

    state("ask")
    assert opt("@claude_state") == "ask"
    state("off")
    assert (
        opt("@claude_state") == ""
        and opt("@claude_attention") == ""
        and opt("@claude_attention_sent") == ""
        and opt("@claude_attention_ack") == ""
    )
finally:
    tmux("kill-server")
    shutil.rmtree(tmp)

print("ok")
