---
name: obsidian-preview
description: >-
  Open a markdown file in Obsidian for a rendered, live-reloading view.
  Works for any path, in or out of a vault. Fires ONLY when the user asks:
  "preview", "render", "show me", "open this", "open in obsidian", or
  /obsidian-preview. Never auto-fires on size, tables, diagrams, or doc
  type; after writing a .md the model returns the file path instead.
---

# obsidian-preview

Show a file rendered in Obsidian (desktop 1.14.2+, macOS).

## When to use

Only on explicit ask: "preview", "render", "show me", "open this", "open in obsidian", `/obsidian-preview [path]`.

Never on your own. Size, table count, diagrams, doc type do not trigger it. Default after writing a `.md`: return the path.

## Workflow

1. Write the file.
2. Open it by absolute path. Plain foreground Bash; it returns at once and leaves nothing to stop:
   ```
   open -a Obsidian /abs/path/plan.md
   ```
3. Keep editing. Obsidian re-renders on every write, in place or temp-file-then-rename.

## Behavior

- The file lands in the last-focused Obsidian window, whatever vault it holds, and Obsidian takes focus.
- Each `open` replaces the active tab. For several related files, open the entry file and list the rest as paths.
- No folder view outside a vault: open files only. Files under a repo `.giantmem/` are also browsable in the `giantmem-vault` sidebar.
- Non-markdown files need a viewer plugin. json and yaml render. If the tab shows "Plugin no longer active", or nothing opens, say so and return the path.

## Mermaid diagrams

Use Mermaid diagrams when they improve clarity over plain text:

- **Flowcharts** — processes and decision trees
- **Sequence diagrams** — API and service interactions
- **Entity-relationship diagrams** — data models
- **State diagrams** — state machines

Prefer Mermaid over ASCII art when the diagram has more than a few
elements or shows relationships and flow.

## Missing app

`Unable to find application named 'Obsidian'` means Obsidian is not installed. Tell the user to install the latest installer from obsidian.md (opening files outside a vault needs 1.14.2+). Do not install it for them.
