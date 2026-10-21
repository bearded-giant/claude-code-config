---
name: browser-capture
description: >-
  Record what the user's logged-in Chrome shows while one page action runs (a chat turn, a form submit, a live-updating panel): attach over CDP to a Chrome the user launched with --remote-debugging-port, log fetch and SSE chunk arrival from inside the page, poll the DOM, screencast the tab to turn.mp4 plus a contact sheet, and print a STREAMING LIVE verdict. No password, no browser download. Auto-fires when the user says "screen capture of", "record the browser", "capture the turn", "show me what the page does", "video of the conversation", "headless through my chrome", "drive my chrome", "is it streaming in the browser", or invokes /browser-capture. Skip for curl-level checks (no browser) and for sites the user is not logged into.
---
<!-- caveman:compressed -->

# browser-capture

Evidence of what a real browser received and rendered, through the user's own logged-in Chrome. Works where a password would be needed (merchant portals, staff admin) and where a fresh profile must rule out a cached bundle. Output is a folder the user can open and a verdict you can quote.

Scripts: `scripts/setup.sh`, `scripts/capture.py`. Profiles: `profiles/<name>.json` (+ optional `<name>.pre.js`). Skill dir = `$(dirname <this file>)`; call scripts by absolute path.

## Procedure (follow in order; every step has a check)

1. **Chrome with CDP, logged in. User does this; never ask for a password.** If `curl -s --max-time 3 http://localhost:9222/json/version` fails, send the user exactly:
   ```
   open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/.chrome-capture"
   ```
   and ask them to log in there as the right user (a fresh `--user-data-dir` means a fresh profile and no stale bundle). Stop the turn there; resume when they say go. Check: `curl -s http://localhost:9222/json` lists a `page` on the target host.
2. **Setup** (idempotent, ~20 s first time): `bash <skill>/scripts/setup.sh`. Prints the venv python. Exit 2 = CDP down (back to step 1). A missing ffmpeg is a warning: frames still land, no mp4 (`brew install ffmpeg` fixes it).
3. **Pick or write a profile.** `profiles/remi-stage.json` drives the remi merchant chat on stage (creates a fresh conversation, sends one question, watches the Activity panel). New target: copy it, set `url`, `action.fill_placeholder` (composer placeholder text), `log_url_regex` / `tee_url_regex` (the fetch URLs to log / to tee as SSE), `done_event` (SSE event that ends the capture), `watch.panel_marker` (a line of body text whose block grows live), `watch.waiting_phrases`. Optional `pre` = JS run on `pre.url` first; its returned JSON fills `{placeholders}` in `url` (see `remi-stage.pre.js`). Drop `pre` when the page already exists.
4. **Run**:
   ```
   OUT=$HOME/.cache/browser-capture/runs/$(date +%Y%m%d-%H%M%S)
   ~/.cache/browser-capture/pw/bin/python <skill>/scripts/capture.py --profile <skill>/profiles/<name>.json --out "$OUT" [--message "..."] [--url ...] [--no-video] [--max-seconds N]
   ```
   `--no-video` = verdict and logs only (faster, no frames). The tab stays open at the end so the user can look.
5. **Read `summary.txt`** (also printed). Lines: `frames in browser` (first SSE chunk times by event), `render` (first DOM change of the watched panel, first provisional text), `STREAMING LIVE: yes|NO`, `panel rows over time`, `video`, `console errors`. Then:
   - frames arrive but render never changes → FE render path (where the panel mounts, schema drops, gating); read the component before claiming a bug.
   - no frames at all, server says it streamed → identity or route: the FE chose the JSON path (admin session, flag off), a proxy buffered, or the fetch wrapper missed the URL (`log_url_regex`).
   - frames arrive only at the end → something buffers the body (compression, proxy); check `content-encoding` with curl using the browser's `Accept-Encoding`.
6. **Deliver**: `SendUserFile` the `turn.mp4` (display `render`) with a one-line caption of what it shows; name `$OUT` in the report. Put the verdict lines in the report; never paraphrase numbers you did not measure.

## What the run writes

| file | what |
|---|---|
| `turn.mp4` | the tab from just before the action to `tail_seconds` after `done_event`, variable frame rate |
| `sheet.png` | 4x3 contact sheet, one frame per second |
| `frames/` | the raw screencast JPEGs |
| `console.log` | page console: `[net] <ms> <status> <url>`, `[sse-chunk] <ms> n=<k> bytes=<b> event: ...`, `[sse-end]`, errors; seconds relative to the send |
| `timeline.json` | DOM snapshots: panel row count, waiting phrases on screen, text after the sent message |
| `summary.txt` | the verdict block |

## Rules

- Never ask for or store credentials; the session cookie stays in the user's Chrome. Never log in for them.
- Never install a browser; `connect_over_cdp` uses theirs. Never close their tabs; the script opens one tab and leaves it.
- `window.fetch` is wrapped by an init script; it logs only URLs matching the profile regexes and tees only the SSE one. Bodies are not written anywhere; console lines carry sizes and event names.
- A `page.evaluate` inside the poll loop drives the event dispatch; keep the loop (do not replace it with `sleep`), or console and screencast events stall.
- Screencast frames must be acked; the loop acks after each poll. A stalled video = acks stopped.
- One action per run. Sequences = several runs, one folder each.
- `--max-seconds` bounds the wait; `done_event` ends it early. A run that hits the bound with no `done_event` is a finding (timeout, error frame, wrong `tee_url_regex`), not a retry target.

## Failure modes

| symptom | cause | do |
|---|---|---|
| `connect_over_cdp` refused | no Chrome on :9222 | step 1 |
| page redirects to a login | not logged in in that profile | user logs in in that Chrome window, rerun |
| `pre step failed: ...` | the pre JS returned `{error}` (API status, CSRF, wrong host) | fix the pre JS or drop `pre` and pass `--url` |
| `get_by_placeholder` timeout | composer placeholder text differs | set `action.fill_placeholder` to the exact placeholder |
| `video: none (no ffmpeg on PATH)` | Homebrew ffmpeg missing | `brew install ffmpeg`; frames are already on disk |
| `Unrecognized option` from ffmpeg | the playwright-bundled ffmpeg got picked | the script uses PATH ffmpeg only; install it |
| frames 0 with `--no-video` absent | screencast never started (CDP session on the wrong target) | rerun; if it persists, use `--no-video` for the verdict and screenshots from `timeline.json` times |
