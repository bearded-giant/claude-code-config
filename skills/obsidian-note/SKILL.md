---
name: obsidian-note
description: Write Claude-authored docs into the Obsidian vault (~/Recharge-Notes/areas/<project>/, one folder per repo), HTML by default and markdown on ask, with the vault frontmatter contract plus a creation timestamp; list vault notes by project/area/tag to pull prior context, and link a note to its claude.ai artifact. Default target of "publish". Auto-fires when the user says "create vault doc", "vault doc", "create html doc", "create vault md", "vault md", "publish", "publish this", "note this", "write this up", "save to obsidian", "runbook for", "write me a doc/reference/summary", or asks for any doc deliverable that is not feature state (.giantmem/). Also fires on "convert to html", "md to html", "md2html", "convert these notes". Never writes to ~/Desktop. Skip for feature artifacts (proposal, plan, tasks, specs, reviews) which stay under .giantmem/, and for handoffs (workspace-rules `## Handoff` owns `areas/<project>/handoffs/`).
---
<!-- caveman:compressed -->

Vault = `~/Recharge-Notes`, the only vault Claude writes; "the vault", "write to vault", "publish" always mean it. `~/giantmem-vault` is a read-only Obsidian view of repo `.giantmem` dirs, never a target. Vault = source of truth, default target of "publish". Team sharing = claude.ai artifact via `claude-artifact` skill, distilled from the note, linked both ways. Desktop = never.

## Format

| Ask | Format |
|---|---|
| "create vault doc", "vault doc", "create html doc", "publish", "write this up", any doc ask naming no format | HTML |
| "create vault md", "vault md", "as markdown", "md note" | markdown |
| ticket notes (`sec-ticket`), handoffs | markdown, always |

`--body-file` extension picks it: `.html`/`.htm` writes `<slug>.html`, anything else or stdin writes `<slug>.md`.

## Convert md and html

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py convert <file.md|dir>... [--out-dir DIR] [--force]
python3 ~/.claude/skills/obsidian-note/scripts/note.py convert --to md <file.html|dir>... [--out-dir DIR] [--force]
```

User's shell aliases: `md2html`, `html2md` (dotfiles `shell/.bash_aliases`). Dirs recurse over `*.md` (`*.html` with `--to md`), skipping `.git`, `.obsidian`, `.trash`, `node_modules`, `handoffs`. Writes `<stem>.html` (or `.md`) beside each source (`--out-dir` mirrors each dir's tree). An existing target is skipped unless `--force`, so `--to md` beside an html note converted from md never clobbers the original. Sources are never deleted. Needs `pandoc`; prints `src -> dst` per file, then `N converted, M failed`, exit 1 on any failure.

- Frontmatter and `## Artifact revisions` move into the leading metadata comment, so `list`, `link`, `bump`, `status` keep working; any later `##` section stays in the page. No frontmatter: plain page, no comment, no eyebrow or date.
- First H1 becomes the template title (inline code kept); none = filename.
- Tables get `.table-wrap`; local images inline as data URIs (a relative path that misses falls back to a vault-wide path-suffix match, as Obsidian does; still missing: warning, link kept); mermaid blocks render via a pinned CDN loader; `[[wiki links]]` in vault files become `obsidian://open` links.
- Mechanical: single column, no TL;DR, no layout. Claude converting on request: run it, then Edit the result where the doc earns more (`.tldr`, `.grid` for compared options, SVG where a mermaid diagram matters) per `## HTML notes`.
- `--to md` reverses it: frontmatter back on top, artifact log back as the last `## Artifact revisions`, masthead H1 (else `<title>`, else filename) as `# title`, mermaid back to fenced blocks, `obsidian://open` links back to `[[wiki links]]`, scripts and styles dropped. Layout is lossy: cards, callouts, tags flatten to text; tab labels become plain lines; inline SVG and images stay as data-URI images. Use it when md is required (a tool, a repo doc, a diff to review); HTML stays the vault default.
- Deleting the source afterwards is a deletion: confirm first. Inbound `[[stem]]` links from other md notes resolve to `.md` only and break once the `.md` goes.

## Write

Body to a scratchpad file, then:

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py new \
  --title "recharge-auth Redis keys and TTLs" \
  --area auth \
  --tags redis,ttl,sessions \
  --body-file "$SCRATCH/body.html"
```

Prints abs path. Report that path to the user, nothing else.

- `--project` = the folder under `areas/`, and the frontmatter `project:`. Default: the cwd repo's folder, the same one its handoffs use (`origin` remote repo name, lowercased; `cc-wt/stage` gives `customcheckout`). Outside a repo the script exits; pass `--project`. Pass it when the subject is another repo than cwd (a note about `recharge-auth` written from `claude-code-config`). A subject with no repo gets a topic folder at the same level (`skio-migration`, `sdlc`, `infra`); run `note.py projects` and reuse one that fits. Lowercase, hyphens and dots only. Never a worktree, branch, or ticket.
- `--area` required, closed list below: a frontmatter category for cross-project views, not a folder. Pick one; tags carry overlap.
- Topic within a project goes in `--tags` (`sessions`, `tokens`, `mcp-oauth`), not a subfolder. A project folder holds notes flat, plus `diagrams/` and `handoffs/`.
- `--tags` comma list, lowercase, hyphenated. `claude` prepended always.
- `--created` ISO 8601, only for imports (birthtime). Default now with tz.
- `--key PE-1234` for ticket notes (`sec-ticket` skill): filename becomes `PE-1234-<slug>.md` (key kept uppercase, stripped from the slug when the title starts with it), frontmatter gains `ticket`, `rev: 1`, `modified`, `status: new`.
- md body starting with `# ` keeps its own H1; otherwise `# <title>` is inserted.
- Filename = slug of title. Collision appends `-YYYY-MM-DD`, then `-N`. Never overwrite.

## HTML notes

HTML reads denser than markdown (real tables, SVG diagrams, tabs, side-by-side layouts), so the user reads instead of skims. Basis: Thariq (Claude Code team), "The Unreasonable Effectiveness of HTML"; examples at https://thariqs.github.io/html-effectiveness/.

- Body = fragment for inside `<main>`, under the template header (eyebrow `project · area`, `<h1>` title, created date). No `<h1>`, `<html>`, or `<head>`. `note.py` wraps it in `html-template/note.html`.
- Body starting `<!doctype` or `<html>` = full page, written as-is: decks, editors, dashboards, anything the column fights. Copy the template's `<style>` so it matches; keep a `<title>` (`list` reads it).
- Template = design system, not layout. No TOC sidebar. Pick layout per doc from:

| class / element | use |
|---|---|
| `.tldr` | answer first, 2-4 lines, top of page |
| `.callout`, `.callout.warn`, `.callout.bad` | note, risk, blocker |
| `.grid` > `.card` | options or parts side by side |
| `.tag`, `.tag.ok` / `.warn` / `.bad` | status, severity |
| `.table-wrap` > `table` | every table (scrolls on phones) |
| `details` > `summary` | depth a reader may skip |
| `div[data-tabs]` > `[role=tablist]` > `button[role=tab]`, then `section[role=tabpanel]` per tab | parallel views of one thing; template script wires them |
| `figure` > inline `svg` + `figcaption`; `.d-box` `.d-key` `.d-line` `.d-arrow` `.d-text` `.d-label` | diagrams, theme-aware |
| `pre > code`, `code`, `.muted` | code, ids, asides |

Doc-specific layout: a `<style>` block in the body on template tokens (`--blue`, `--teal`, `--surface`, `--rule-strong`, `--ok`/`--warn`/`--bad`).

Authoring:
1. Optimize for someone reading it once. Answer first (`.tldr`), detail after, depth in `details`.
2. Tables as `<table>`; diagrams as inline SVG with `width` = viewBox width so it never upscales. Never ASCII art, unicode color blocks, or mermaid source in a `<pre>`.
3. Long reference doc needing navigation: inline jump list under the TL;DR. Sticky sidebar only when asked.
4. Interactive piece (slider, toggle, mini editor) ends with an export: a button copying the state as a prompt, markdown, or JSON.
5. Self-contained: inline CSS/JS; CDN scripts only at pinned versions (cdnjs, jsdelivr, unpkg). No `localStorage`, no fetch: the viewer is a sandboxed iframe.
6. Every color from a token. Tokens use `light-dark()`; Obsidian's `html-docs` plugin sets `color-scheme` from the app theme, so both themes come free if no literal colors sneak in.

Cost: HTML takes longer to write and diffs noisily in the vault's git; md stays right for notes that churn line by line.

Edit later with Edit on the `.html` file. View: Obsidian renders `.html` through the `html-docs` plugin; `open <path>` for a browser. Dataview, obsidian.nvim, and `[[wiki links]]` inside the page do not see html notes; `note.py list` does, and other notes link one as `[[<stem>.html]]`.

## Areas

| area | covers |
|---|---|
| auth | recharge-auth, sessions, JWT, redis session cache, tokens, api keys |
| ai-tooling | claude config, MCPs, orchestrator, agents, dashboards, doit, prompts |
| migration | skio, monster, translation layer, data model mapping |
| platform | recharge API, bundles, repricing, platform docs |
| infra | ES, sentry, splunk, k8s, zendesk plumbing, vault |
| dev-process | merge train, quality, local dev setup, SDLC |
| dev-tools | nvim, tmux, terminal, shell, alfred |
| personal | bearded giant, non-work |
| security | ticket reviews (HackerOne, internal, client), vuln research, fix proposals; domain = repo alias |

New area = edit `AREAS` in `scripts/note.py` and this table, same commit. Project folders are open; the vault tree is the registry.

## Frontmatter emitted

```yaml
---
id: recharge-auth-redis-keys-and-ttls
aliases: []
tags: [claude, redis, ttl]
area: auth
project: recharge-auth
created: 2026-09-28T14:38:12-04:00
---
```

HTML notes carry the same block inside a leading comment (`<!--`, the block, `-->`) before `<!doctype html>`. `id, aliases, tags, area, project` = obsidian.nvim contract, do not add or rename keys. `project` always equals the folder. Script-owned additions: `created`, `artifact` + `artifact_rev` + `artifact_account` once linked, `artifact_hub` + `artifact_hub_rev` once published to the artifacts hub, and `ticket` + `rev` + `modified` + `status` on `--key` notes. Do not hand-write frontmatter; the script owns it.

## Bump or set status on a ticket note

After any content edit to a `--key` note, and on a status change:

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py bump <note.md>
python3 ~/.claude/skills/obsidian-note/scripts/note.py status <note.md> ready   # new ready blocked in_progress in_review done wont_fix
```

`bump`: `rev` +1, `modified` = now. `status`: sets `status`, `modified` = now, `rev` unchanged. Ticket notes carry no revision log; the `sec-ticket` skill keeps it on the doit list. A note without `rev:` whose filename starts with a ticket key (legacy `pe-1527-review-...`) gains `ticket`, `rev: 2`, `modified`, `status: new` on its first bump; any other note without `rev:` exits non-zero, and so does `status`.

## Link to an artifact

After a `claude-artifact` publish of this note's content:

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py link <note.md> --url <artifact url> --rev N --log "one line on what changed"
```

Upserts `artifact:` / `artifact_rev:` / `artifact_account:` (the session's claude.ai label, `--account` overrides) and appends `- rev N · <ts> · <log>` under `## Artifact revisions` (HTML notes: inside the metadata comment, off the rendered page). `--hub` upserts `artifact_hub:` / `artifact_hub_rev:` instead and logs `hub <url>`, claude.ai keys untouched. Temporal detail and change history belong in the note, never in the artifact. Note already has `artifact:` → re-share updates that URL.

`note.py account [<note.md>]` prints the session's label (keychain slot `subscriptionType`: `team` rc-team, `enterprise` rc-inc; else `~/.claude.json`) and exits non-zero when the note's artifact lives in another account. Building the artifact → `claude-artifact` `## From a note`.

## Read before write

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --area auth --since 90
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --project recharge-auth --tag sessions
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --tag redis
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --ticket PE-1526   # ticket: key or a key-prefixed filename, any area
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --status ready      # ticket notes in one status; rows gain a status column
python3 ~/.claude/skills/obsidian-note/scripts/note.py projects
```

One line per note (`.md` and `.html`): `created | area | project | path | title`. Handoffs are left out. Read the hits that match the subject before writing a new note. Extend an existing note (Edit) when the subject is the same; new note when the subject is new.

## Rules

- Vault pushes to GitHub every 5 min. No secrets, tokens, connection strings with passwords, query dumps, or customer PII. Redact `<REDACTED:token>`. Raw dumps stay in the scratchpad.
- Notes are for the user: paths, dates, changelogs allowed. Anything for others goes out as a `claude-artifact`, not a note.
- The `daily_note` hook logs every vault note write (Write/Edit or `note.py new`) and every artifact publish under `## CLAUDE LINKS` in `daily/<YYYY-MM-DD>.md`, creating the day's note from `templates/dailytemplate.md` when missing. Never hand-edit those sections or log twice.
- Feature state stays in `.giantmem/`: proposal, plan, tasks, specs, facts, reviews, research tied to an in_progress feature. Handoffs go to `areas/<project>/handoffs/` per workspace-rules `## Handoff`, never through `note.py`. Cross-repo durable knowledge (runbook, incident writeup, design note, reference, decision record, how-to) goes to the vault.
- Do not write `areas/areas-index.md`; it is a Dataview page.
- Wiki links `[[note]]` resolve vault-wide in md notes; link existing notes by stem when relevant (`[[stem.html]]` for an html note).
