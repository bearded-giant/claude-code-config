#!/usr/bin/env python3
"""Run several hook modules in one process, so an event pays one process spawn
instead of N. Spawn cost dominates hook time here; the scripts are ~50ms.

Output modes:
  no --event   plain-text hooks, stdout concatenated
  --event NAME hooks that emit hookSpecificOutput JSON; every additionalContext
               is merged into one object, since two JSON objects on one stdout
               is not parseable

A control object (decision / permissionDecision / continue) wins outright and is
printed alone: a block reason is the whole payload or it is nothing.
"""

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

HOOKS = Path(__file__).resolve().parent


def run(name, raw):
    buf = io.StringIO()
    saved = sys.stdin
    try:
        spec = importlib.util.spec_from_file_location(
            f"_hook_{name}", HOOKS / f"{name}.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.stdin = io.StringIO(raw)
        with redirect_stdout(buf):
            mod.main()
    except BaseException:  # pylint: disable=broad-exception-caught
        # SystemExit too: one hook must not end the run
        pass
    finally:
        sys.stdin = saved
    return buf.getvalue().strip()


def classify(chunk):
    """text | context (mergeable additionalContext) | control (wins alone)."""
    try:
        obj = json.loads(chunk)
    except (json.JSONDecodeError, ValueError):
        return "text", chunk
    if not isinstance(obj, dict):
        return "text", chunk
    block = obj.get("hookSpecificOutput")
    if isinstance(block, dict) and set(obj) == {"hookSpecificOutput"}:
        context = block.get("additionalContext")
        steering = set(block) - {"hookEventName", "additionalContext"}
        if isinstance(context, str) and context.strip() and not steering:
            return "context", context.strip()
    return "control", obj


def main():
    argv = sys.argv[1:]
    event = None
    if argv[:1] == ["--event"]:
        event, argv = argv[1], argv[2:]

    raw = sys.stdin.read()
    texts, control = [], None
    for name in argv:
        chunk = run(name, raw)
        if not chunk:
            continue
        kind, value = classify(chunk)
        if kind == "control":
            if control is None:
                control = value
            continue
        texts.append(value)

    if control is not None:
        print(json.dumps(control))
        return
    if not texts:
        return
    merged = "\n\n".join(texts)
    if event:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": event,
                        "additionalContext": merged,
                    }
                }
            )
        )
        return
    print(merged)


if __name__ == "__main__":
    main()
