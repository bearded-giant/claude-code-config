---
description: Toggle Claude Code statusline settings (style, line2, tools, agents) via wizard-style menu. Auto-fires when user invokes /statusline or says "configure statusline", "change statusline", "toggle statusline".
---

Toggle statusline settings via wizard-style menu.

## Steps

1. Read `hooks/statusline-config.json` (relative to `~/.claude/`).

2. Show the current config as a numbered menu:

```
Statusline config:

1. style: compact        (compact | minimal)
2. line2: on
3. tools: last           (last | feed | off)
4. agents: on
5. messages: off
6. lines: on
7. duration: on
8. gmdocs: off          (giantmem docs/day counter)
9. models: on           (per-model usage gauge, e.g. fable)
10. preflight: on       (red ✗gcloud/adc/glab/gh/vault when auth lapses, ~ when unreachable)
11. mr: on              (current branch MR or PR: pipeline, conflicts, threads, approval)
12. mcp: on             (mcp ✓N connected servers, yellow !auth:K when K need login)

Enter number to toggle, or "q" to quit:
```

3. When user picks a number:
   - Boolean fields (line2, agents, messages, lines, duration, gmdocs, models, preflight, mr, mcp): flip true/false
   - `style`: cycle compact -> minimal -> compact
   - `tools`: cycle last -> feed -> off -> last

4. Write the updated config back to `hooks/statusline-config.json`.

5. Show the updated menu again so user can make more changes or quit.

6. On "q" or "done", confirm: "Statusline config updated. Changes take effect on next tick."
