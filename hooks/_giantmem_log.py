"""Tiny shared logger for giantmem hooks.

Append-only log at ~/.cache/giantmem/hook.log. Rotates when over 1 MB
(keeps one .old). Stdlib only.
"""

import time
import traceback
from pathlib import Path

LOG_DIR = Path.home() / ".cache" / "giantmem"
LOG_PATH = LOG_DIR / "hook.log"
MAX_SIZE = 1 * 1024 * 1024


def _rotate_if_needed() -> None:
    try:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > MAX_SIZE:
            old = LOG_PATH.with_suffix(".log.old")
            if old.exists():
                old.unlink()
            LOG_PATH.rename(old)
    except OSError:
        pass


def log(hook: str, msg: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed()
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{ts} [{hook}] {msg}\n")
    except OSError:
        pass


def log_exception(hook: str) -> None:
    try:
        log(hook, "exception:\n" + traceback.format_exc().rstrip())
    except Exception:
        pass
