#!/bin/bash
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
LOG_DIR="${EOD_STATUS_HOME:-$HOME/.config/eod-status}/logs"
mkdir -p "$LOG_DIR"
cd "$(dirname "$0")" || exit 1
echo "=== run $(date '+%Y-%m-%d %H:%M:%S') $* ===" >> "$LOG_DIR/cron.log"

MAX_SECONDS=2400
/opt/homebrew/bin/python3 eod.py "$@" >> "$LOG_DIR/cron.log" 2>&1 &
PID=$!
( sleep "$MAX_SECONDS"; kill -0 "$PID" 2>/dev/null && \
    { echo "WATCHDOG: killed run after ${MAX_SECONDS}s" >> "$LOG_DIR/cron.log"; \
      kill -9 "$PID" 2>/dev/null; \
      terminal-notifier -title "EOD status FAILED" -message "Timed out after ${MAX_SECONDS}s" -open "file://$LOG_DIR/cron.log"; } ) &
WATCHDOG=$!
wait "$PID"
STATUS=$?
kill "$WATCHDOG" 2>/dev/null
exit "$STATUS"
