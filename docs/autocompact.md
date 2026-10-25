# Auto-compact

`autoCompactWindow` sets how many tokens of conversation a session holds before Claude Code summarizes it. The model's context window doesn't change. Compaction fires a little under the window (about 30k below it), replaces the older part of the conversation with a model-written summary, and keeps the most recent messages word for word.

This repo leaves it unset, so each model uses its own tuned window (`"auto"`). On a 1M-context model that means sessions run a long way before they compact.

## Why there's no forced low window

Every request re-sends the whole context, so a lower window looks like an easy cut. It isn't free. A compaction doesn't drop the session to a few thousand tokens: the summary itself is about 4k to 5k tokens, but the context right after one sits around 100k to 130k, because the system prompt, tools, and CLAUDE.md files come back along with the recent messages kept word for word. Each compaction also rewrites that whole prefix into the prompt cache, generates the summary, and stalls the session for one to three minutes.

So the payoff depends on how many calls run before the next compaction. With the window at `300000`, and pricing cache reads at a tenth of input and one-hour cache writes at double, a long Opus session that ran 170 calls past its first compaction came out about 40% cheaper. A heavy-output Fable session filled the window again after 28 calls, saved about 4%, and spent over four minutes compacting. A lower window shrinks the room between that post-compact floor and the trigger, so it compacts more often for less.

## Compacting on purpose

The better lever is compacting at a task boundary yourself with `/compact next: <task>`. Context shrinks right away like it does with `/clear`, but the next task starts from a summary instead of from nothing, and the compaction lands where the work actually changes instead of in the middle of a task.

## What the summary keeps

The PreCompact hook in `settings.json` prints `config/compact-instructions.md`. Claude Code takes the stdout of PreCompact hooks as the compaction's custom instructions and merges it with any `/compact <args>`. The instructions ask the summary to keep every file touched, findings marked verified or inferred, commits and MRs and doit items, decisions and the user's corrections, the open state with the next step, and identifiers word for word. It runs on every compaction, manual or auto. It doesn't run on `/clear`.

That only works while every other PreCompact hook keeps its stdout empty. Anything a PreCompact hook prints ends up in the compaction prompt.

## Knobs

| Want | Do |
|---|---|
| See the current window and where it comes from | `/autocompact` |
| One session with a different window | `CLAUDE_CODE_AUTO_COMPACT_WINDOW=<tokens> claude` (the env var beats settings) |
| Change the window for a model, on this machine only | `/autocompact <tokens>`. It saves under `modelSettings` in the home `settings.json`, which `sync_settings.py` leaves alone, and a per-model value beats the top-level one |
| Set a repo default | Add `autoCompactWindow` to `settings.json` and commit, since `sync_settings.py` reads the committed blob |
| Compact right now | `/compact [what to focus on]` |

Valid values are `100000` to `1000000`, or `"auto"`.

## Picking the right reset

| Situation | Do |
|---|---|
| Next task builds on this one | `/compact next: <task>` at the boundary, so context shrinks now and the summary points at what comes next |
| Next task is unrelated | `/clear`. The `clear_capsule.py` hook carries over a small capsule of the cleared session (its last few asks, the files it edited, an excerpt of the last reply) and the `claude --resume <id>` line |
| Picking the same work back up later | `claude --continue` (latest session in the directory) or `claude --resume <id>` |
| Handing off to someone else, or to a session started much later | `/wrap` writes the full handoff |
