# Auto-compact

`autoCompactWindow` sets how many tokens of conversation a session holds before Claude Code summarizes it. The model's context window doesn't change. The effective threshold is the smaller of this setting and the model's maximum window. Once a session crosses it, the older part of the conversation is replaced by a model-written summary, and the most recent messages are kept word for word.

This repo sets it to `300000` in `settings.json`. On a 1M-context model, that means a session holds about 30% of the window as raw conversation, and everything older lives on as a summary of a few thousand tokens.

## Why not use the whole window

Every request re-sends the entire context, so a turn at 700k tokens costs 700k tokens. With the default window on a 1M model, sessions grow to 500k to 900k before they ever compact, and most never do. Here's a simulation against a week of real session transcripts (it ignores the summary's own output cost):

| `autoCompactWindow` | Context read | Compactions |
|---|---|---|
| auto (model default) | 3.43B | 0 |
| 400000 | 2.47B (−28%) | 55 |
| 300000 | 2.12B (−38%) | 102, about one per session |
| 200000 | 1.68B (−51%) | 267 |

The cost of a lower window is that each compaction is a summary step, and some detail can drop at each one. You also lose word-for-word access to old material, like a file read or a log viewed long ago in the session. Re-reading the file is cheaper than carrying it on every turn. One more thing, which is general experience rather than something measured here: models tend to recall less reliably across a huge context than across a focused one.

## What the summary keeps

The PreCompact hook in `settings.json` prints `config/compact-instructions.md`. Claude Code takes the stdout of PreCompact hooks as the compaction's custom instructions and merges it with any `/compact <args>`. The instructions ask the summary to keep every file touched, findings marked verified or inferred, commits and MRs and doit items, decisions and the user's corrections, the open state with the next step, and identifiers word for word.

That only works while every other PreCompact hook keeps its stdout empty. Anything a PreCompact hook prints ends up in the compaction prompt.

## Knobs

| Want | Do |
|---|---|
| See the current window and where it comes from | `/autocompact` |
| One session with the full window | `CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000 claude` (the env var beats settings) |
| Change the default for a model, on this machine only | `/autocompact <tokens>`. It saves under `modelSettings` in the home `settings.json`, which `sync_settings.py` leaves alone, and a per-model value beats the top-level one |
| Change the repo default | Edit `autoCompactWindow` in `settings.json` and commit, since `sync_settings.py` reads the committed blob |
| Compact right now | `/compact [what to focus on]` |

Valid values are `100000` to `1000000`, or `"auto"`. Passing `--settings '{"autoCompactWindow":"auto"}'` does not override the value from `settings.json`. Use the env var instead.

## Picking the right reset

| Situation | Do |
|---|---|
| Next task builds on this one | Keep going, or run `/compact next: <task>` at the boundary to shrink context now and point the summary at what comes next |
| Next task is unrelated | `/clear`. The `clear_capsule.py` hook leaves a short pointer and the `claude --resume <id>` line for the cleared session |
| Picking the same work back up later | `claude --continue` (latest session in the directory) or `claude --resume <id>`. Resuming stays cheap because the session compacts at the window |
| Handing off to someone else, or to a session started much later | `/wrap` writes the full handoff |
