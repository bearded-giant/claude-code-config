---
name: mdlive
description: >-
  Preview markdown with mdlive in a live-reloading browser. Auto-fires
  after writing any .md to .giantmem/ that is >40 lines OR contains a
  Mermaid diagram OR contains 2+ tables OR is likely to iterate with
  the user (plans, designs, kaizen docs, reports). Also triggers when
  user says "preview", "render", "show me in browser", "open this".
  Skip for short conversational replies, single snippets, or markdown
  that fits in the terminal.
---

# mdlive

Serve markdown files as live-reloading HTML previews in the browser
using `mdlive`.

## When to use

Trigger if ANY of:
- file is >40 lines
- file contains a Mermaid diagram
- file contains 2+ tables
- file is a plan, design, kaizen doc, or report (likely to iterate with user)
- user says "preview", "render", "show me in browser", "open this"

Do NOT trigger for:
- short conversational replies
- single code snippets
- markdown that fits in the terminal
- chat-only output (not written to disk)

## Workflow

1. Write the markdown file (e.g. `plan.md`).
2. Start mdlive using the Bash tool with `run_in_background: true`:
   ```
   command: mdlive plan.md
   run_in_background: true
   ```
   The browser opens automatically. mdlive auto-cycles to the next
   available port if 3000 is in use — no port checking needed.
3. Continue editing the file — changes reload automatically.
4. When the task is finished and the preview is no longer needed, stop
   the background task using `TaskStop` with the task ID.

## Directory mode

When producing multiple related markdown files, serve the parent
directory instead:

```
command: mdlive docs/
run_in_background: true
```

This gives the user a collapsible tree sidebar to navigate between files,
including any nested subdirectories.

## Mermaid diagrams

Use Mermaid diagrams when they improve clarity over plain text:

- **Flowcharts** — processes and decision trees
- **Sequence diagrams** — API and service interactions
- **Entity-relationship diagrams** — data models
- **State diagrams** — state machines

Prefer Mermaid over ASCII art when the diagram has more than a few
elements or shows relationships and flow.

## Installation

mdlive must be installed on the user's system. If the `mdlive`
command is not found, ask the user how they would like to install it
using `AskUserQuestion` with these options:

1. **Cargo** — `cargo install mdlive`
2. **Build from source** — `git clone https://github.com/bearded-giant/mdlive && cd mdlive && cargo build --release`

Then run the corresponding install command for them.
