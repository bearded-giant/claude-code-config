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
5. thinking: off
6. messages: off
7. lines: on
8. duration: on
9. gmdocs: off          (giantmem docs/day counter)

Enter number to toggle, or "q" to quit:
```

3. When user picks a number:
   - Boolean fields (line2, agents, thinking, messages, lines, duration, gmdocs): flip true/false
   - `style`: cycle compact -> minimal -> compact
   - `tools`: cycle last -> feed -> off -> last

4. Write the updated config back to `hooks/statusline-config.json`.

5. Show the updated menu again so user can make more changes or quit.

6. On "q" or "done", confirm: "Statusline config updated. Changes take effect on next tick."
