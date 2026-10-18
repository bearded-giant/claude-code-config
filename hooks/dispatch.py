#!/usr/bin/env python3
"""Run several hook modules in one process, so an event pays one process spawn
instead of N. Spawn cost dominates hook time here; the scripts are ~50ms.

Output modes:
  no --event   plain-text hooks, stdout concatenated
  --event NAME hooks that emit hookSpecificOutput JSON; every additionalContext
               is merged into one object, since two JSON objects on one stdout
               is not parseable

A control object (decision / permissionDecision / continue) wins outright and is
printed alone: a block reason is the whole payload or it is nothing. Several
blocks merge their reasons into the first.
"""

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

HOOKS = Path(__file__).resolve().parent


def _log_exception(name):
    try:
        spec = importlib.util.spec_from_file_location(
            "_giantmem_log", HOOKS / "_giantmem_log.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.log_exception(f"dispatch:{name}")
    except Exception:  # pylint: disable=broad-exception-caught
        pass


def run(name, raw):
    buf = io.StringIO()
    saved = sys.stdin
    try:
        spec = importlib.util.spec_from_file_location(
            f"_hook_{name}", HOOKS / f"{name}.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.stdin = io.StringIO(raw)
        with redirect_stdout(buf):
            mod.main()
    except BaseException:  # pylint: disable=broad-exception-caught
        # SystemExit too: one hook must not end the run. Log it: a module that
        # raises is otherwise indistinguishable from one that chose to say
        # nothing, which hid a broken hook for weeks.
        _log_exception(name)
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
            if not isinstance(control, dict):
                control = value
            elif (
                isinstance(value, dict)
                and control.get("decision") == value.get("decision") == "block"
            ):
                # the retry stop carries stop_hook_active, which silences every gate,
                # so a dropped second reason would never be shown
                control = {
                    **control,
                    "reason": f"{control.get('reason', '')}\n\n{value.get('reason', '')}",
                }
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
