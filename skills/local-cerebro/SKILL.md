---
name: local-cerebro
description: Ask the local cerebro raw CLI code-level questions about repos indexed there (frost, customcheckout, the dapr services) WITHOUT checking them out in this session. Formats the call, preflights readiness, and returns a status report if cerebro is not ready. Auto-fires when user says "ask cerebro", "ask local cerebro", "query the frost/customcheckout repo", "delta a repo I don't have checked out", "what does <repo> do for X", or invokes /local-cerebro. Skip when the file is already in this session's tree (read it directly).
---
<!-- caveman:compressed -->

Local cerebro = read-only Claude over its own indexed repos (`~/dev/ai/cerebro/projects/`). This session delegates a code-level question, gets the answer on stdout, stays uncluttered. One-shot: no daemon, stateless per call.

## Call (always via the script)

```bash
~/.claude/skills/local-cerebro/scripts/cerebro-ask.sh "PROMPT naming the repo" [haiku|sonnet|opus]
```
- model defaults to `opus`. stdout = answer only (ends `*References*`). stderr = warnings/status.
- script preflights first. if cerebro not ready it prints a status report to stderr and exits 3 — do NOT hand-roll the `uv run` call, let the script gate it.
- `CEREBRO_DIR` env overrides the cerebro location (default `~/dev/ai/cerebro`).

## Status / not-running check

```bash
~/.claude/skills/local-cerebro/scripts/cerebro-ask.sh status
```
Reports: cerebro dir found, `uv` present, `.env` present, `ANTHROPIC_API_KEY` set (billing), indexed repo count. exit 0 = READY, 3 = NOT READY. Run this first if a call fails, or to confirm cerebro can serve.

## Exit codes
| code | meaning |
|---|---|
| 0 | answer on stdout |
| 1 | cerebro ran but the request failed |
| 2 | build/write attempt rejected (one-shot is read-only) |
| 3 | not ready — status printed to stderr |

## Prompt rules
- NAME the repo (frost, customcheckout, event-bus, recharge-foundations, ...). cerebro's project map picks the checkout.
- ask code-level questions; request file citations ("cite files").
- ONE question per call — stateless, no memory between calls.
- list repos: `cerebro-ask.sh "!projects"`.

## Boundaries
- read-only. cerebro never edits/commits. THIS session owns all commits (it has the context).
- repos cerebro reads = its `projects/` symlinks, on whatever branch each checkout is — NOT this session's tree.
- platform billing needs `ANTHROPIC_API_KEY` exported in this session's shell; else it bills the logged-in claude subscription (script warns).

## Pointers
- cerebro setup / add-a-repo / add-localhost-mcp: `~/dev/ai/cerebro/projects/LOCAL_SETUP.md`.
- one-shot impl: `broker/cli.py` `ask_once()` + `--ask`/`--model`.
