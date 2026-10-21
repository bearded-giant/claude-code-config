#!/bin/bash
# Idempotent: venv with playwright (no browser download), ffmpeg check, CDP check.
set -uo pipefail
VENV=${VENV:-$HOME/.cache/browser-capture/pw}
CDP=${CDP:-http://localhost:9222}
[ -x "$VENV/bin/python" ] || { python3 -m venv "$VENV" && "$VENV/bin/pip" -q install playwright; }
"$VENV/bin/python" -c "import playwright" 2>/dev/null || { echo "playwright missing in $VENV"; exit 1; }
command -v ffmpeg >/dev/null || echo "warn: no ffmpeg on PATH (brew install ffmpeg); frames are kept, no mp4"
if curl -s --max-time 3 "$CDP/json/version" >/dev/null; then
  echo "cdp: up at $CDP"
  curl -s --max-time 3 "$CDP/json" | python3 -c "import json,sys; [print('  page', t['url'][:100]) for t in json.load(sys.stdin) if t['type']=='page']"
else
  echo "cdp: DOWN. ask the user to run, then log in there:"
  echo '  open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/.chrome-capture"'
  exit 2
fi
echo "python: $VENV/bin/python"
