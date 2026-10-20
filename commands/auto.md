---
description: Autonomous mode for a defined scope (reviewed plan, task list, handoff, doit list, named branches). Works the scope end to end without mid-run questions, ships every tested piece through ship-it, babysits each MR, and logs every call made without asking. `/auto off` exits. Rules of engagement live in CLAUDE.md `### Autonomous mode`.
argument-hint: "<plan | tasks | handoff path | doit list | branches> | off"
---

Autonomous mode for: $ARGUMENTS

`hooks/auto_mode.py` (UserPromptSubmit) already turned the mode on for this session, or off for `/auto off`. After `off` there is nothing else to do.

1. Load the scope. Read the plan, task list, handoff, or doit list named above. Empty argument → the plan or scope agreed earlier in this conversation; no such scope → AskUserQuestion once, the only ask of the run. Every piece of work becomes a `claude:` item on the session doit list: priority set, `ref:` first description line, `deps` where one piece waits on another. Items already on the list stay as they are.
2. Announce in 1-3 lines: the items in work order and the hard stops that apply. Do not wait for a reply.
3. Work per CLAUDE.md `### Autonomous mode`, in burn order (sequence first, then priority).
4. Exit when every item is done or BLOCKED behind a `gate`/`decision` item, and every MR is READY, BLOCKED, or has a babysit loop running: run `python3 ~/.claude/hooks/auto_mode.py --off`, then report per that section.
