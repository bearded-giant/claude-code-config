---
name: local-cerebro
description: Ask the local cerebro raw CLI code-level questions about repos indexed there (frost, customcheckout, the dapr services) WITHOUT checking them out in this session. Formats the call, preflights readiness, and returns a status report if cerebro is not ready. Also adds/removes/lists the repos local cerebro reads. Auto-fires when user says "ask cerebro", "ask local cerebro", "query the frost/customcheckout repo", "delta a repo I don't have checked out", "what does <repo> do for X", "add <repo> to cerebro", "remove <repo> from cerebro", "what repos does cerebro have", or invokes /local-cerebro. Skip when the file is already in this session's tree (read it directly).
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

## Manage repos (no Claude call)

```bash
~/.claude/skills/local-cerebro/scripts/cerebro-ask.sh repos                  # name, branch, -> target | (clone) | BROKEN
~/.claude/skills/local-cerebro/scripts/cerebro-ask.sh add <repo-path> [name] # symlink + mechanical re-index
~/.claude/skills/local-cerebro/scripts/cerebro-ask.sh remove <name>          # unlink + re-index (prunes entry)
```
- `add`: path must be a git checkout; links its toplevel. name defaults to origin remote's repo name (so `…-wt/main` -> real repo name), else dir basename. existing symlink -> repointed (fixes BROKEN). real clone dir -> refused.
- `remove`: symlinks only; checkout untouched. clone dir -> refused, prints the manual `rm -rf` for the user to run. never run that `rm -rf` yourself without confirm.
- name must be one safe segment (`[A-Za-z0-9][A-Za-z0-9._-]*`): anything linked into `projects/` becomes readable by cerebro.

## Exit codes
| code | meaning |
|---|---|
| 0 | answer on stdout / repo op done |
| 1 | cerebro ran but the request failed, or add/remove refused |
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
- cerebro setup + one-shot flags: `~/dev/ai/cerebro/docs/CLI.md`. add/remove a repo: `~/dev/ai/cerebro/projects/README.md`. localhost MCP: `~/dev/ai/cerebro/docs/DEVELOPMENT.md` "Adding Local MCP Tools".
- one-shot impl: `broker/cli.py` `ask_once()` + `--ask`/`--model`.
