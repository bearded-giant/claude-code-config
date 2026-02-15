---
name: mdlive
description: >-
  Preview markdown with mdlive when content is long or likely to be
  iterated with the user (tables, diagrams, multi-section docs). Skip
  preview for short markdown that is easy to read directly in the
  terminal.
---

# mdlive

Serve markdown files as live-reloading HTML previews in the browser
using `mdlive`.

## When to use

Use mdlive whenever you produce markdown that benefits from rendered
presentation:

- Plans and proposals
- Architecture or design documents
- Reports, comparisons, or summaries with tables
- Anything containing Mermaid diagrams
- Multi-file documentation sets
- Any time the user asks to "preview" or "render" markdown

Use mdlive when markdown is more than about 40 to 60 lines, has
complex formatting, or is likely to go through multiple edit/review
iterations with the user.

Do **not** use mdlive for short conversational answers, single code
snippets, trivial one-paragraph responses, or any markdown that fits
comfortably within a terminal window.

## Workflow

1. Write the markdown file (e.g. `plan.md`).
2. Start mdlive using the Bash tool with `run_in_background: true` and
   the `--open` flag to launch the browser automatically:
   ```
   command: mdlive --open plan.md
   run_in_background: true
   ```
3. Tell the user the URL (default: http://127.0.0.1:3000).
4. Continue editing the file - changes reload automatically.
5. When the task is finished and the preview is no longer needed, stop
   the background task using `TaskStop` with the task ID.

## Port conflicts

Before starting mdlive, check if the default port is in use:

```bash
ss -tlnp | grep :3000
```

If port 3000 is occupied, pick another port:

```
command: mdlive --open plan.md --port 3001
run_in_background: true
```

Always tell the user the actual URL including the port you used.

## Directory mode

When producing multiple related markdown files, serve the parent
directory instead:

```
command: mdlive --open docs/
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
