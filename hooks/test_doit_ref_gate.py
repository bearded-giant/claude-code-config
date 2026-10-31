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


mod = load("doit_ref_gate")
prime = load("doit_session_prime")
real_load = mod.load
mod.load = lambda name: prime if name == "doit_session_prime" else real_load(name)


def write_list(name, todos):
    with open(
        os.path.join(prime.LISTS_DIR, f"{name}.json"), "w", encoding="utf-8"
    ) as fh:
        json.dump({"todos": todos}, fh)


def run_hook(tmp, text, **extra):
    transcript = os.path.join(tmp, "t.jsonl")
    with open(transcript, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": "go"}}) + "\n")
        msg = {"content": [{"type": "text", "text": text}]}
        fh.write(json.dumps({"type": "assistant", "message": msg}) + "\n")
    sys.stdin = io.StringIO(json.dumps({"transcript_path": transcript, **extra}))
    buf = io.StringIO()
    with redirect_stdout(buf):
        mod.main()
    out = buf.getvalue().strip()
    return json.loads(out) if out else None


def cases(tmp):
    proj = os.path.join(tmp, "refrepo")
    os.makedirs(proj)
    os.environ["CLAUDE_PROJECT_DIR"] = proj
    write_list(
        "refrepo",
        [
            {"id": "a", "text": "[gate] 10. enable shopper SMS flag", "done": False},
            {
                "id": "b",
                "text": "claude: [chore] 11. rotate webhook secret (dep on #10)",
                "done": True,
            },
            {"id": "c", "text": "unnumbered user note", "done": False},
        ],
    )
    write_list(
        "daily", [{"id": "d", "text": "[owe] 3. approve IdP app", "done": False}]
    )
    write_list(
        "investigator-bulk-run-3",
        [{"id": "e", "text": "[bug] 10. fix date reader", "done": False}],
    )

    # the reported case: bare numbers with a verb nobody can decode
    out = run_hook(tmp, "Next: flip #10 / #11 before launch.")
    assert out and out["decision"] == "block", out
    assert "refrepo #10 (enable shopper SMS flag)" in out["reason"], out
    # a done item still needs its label, and the dep suffix is not part of it
    assert "refrepo #11 (rotate webhook secret)" in out["reason"], out

    # an unlabeled ref on a named list resolves against that list
    out = run_hook(tmp, "daily #3 is waiting on you.")
    assert out and "daily #3 (approve IdP app)" in out["reason"], out

    # an alias resolves by suffix, and a named list carries to later bare refs on its line
    out = run_hook(tmp, "doit: bulk-run-3 #10 closed; daily #3 waits, and #10 too")
    assert out, out
    assert "investigator-bulk-run-3 #10 (fix date reader)" in out["reason"], out
    assert "daily #3 (approve IdP app)" in out["reason"], out
    assert "refrepo #10" not in out["reason"], out

    # labeled forms pass: parens, backticked ref with parens, label words on the line
    assert (
        run_hook(tmp, "refrepo #10 (shopper SMS flag): turn it on before launch")
        is None
    )
    assert run_hook(tmp, "owed: `daily #3` (approve IdP app)") is None
    assert run_hook(tmp, "#10 enables the shopper SMS flag at launch") is None

    # dep lists, other ref kinds, unknown numbers, and code blocks are not doit refs to label
    assert run_hook(tmp, "new item 12 (dep on #10, #11)") is None
    assert run_hook(tmp, "see RechargePayments/ai-investigator#10 and PR #11") is None
    assert (
        run_hook(tmp, "your [Pasted text #10 +12 lines] and [Image #11] never arrived")
        is None
    )
    assert run_hook(tmp, "PR 28 (#10) merged; PRs #11-#10 wait") is None
    assert run_hook(tmp, "auto-merge off on ai-investigator #10, #11") is None
    assert run_hook(tmp, "color #333 and step #99") is None
    assert run_hook(tmp, "```\nflip #10\n```\ndone") is None

    # the retry stop never blocks again, and the bypass env silences it
    assert run_hook(tmp, "flip #10", stop_hook_active=True) is None
    os.environ[mod.BYPASS_ENV] = "off"
    try:
        assert run_hook(tmp, "flip #10") is None
    finally:
        del os.environ[mod.BYPASS_ENV]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = os.path.realpath(tmp)
        os.makedirs(os.path.join(tmp, "lists"))
        saved = prime.LISTS_DIR
        prime.LISTS_DIR = os.path.join(tmp, "lists")
        try:
            cases(tmp)
        finally:
            prime.LISTS_DIR = saved
    print("ok")


if __name__ == "__main__":
    main()
