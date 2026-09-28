---
name: obsidian-note
description: Write Claude-authored markdown into the Obsidian vault (~/Recharge-Notes/areas/<area>/) with the vault frontmatter contract plus a creation timestamp, and list vault notes by area/project/tag to pull prior context. Auto-fires when the user says "note this", "write this up", "save to obsidian", "runbook for", "write me a doc/reference/summary", or asks for any markdown deliverable that is not feature state (.giantmem/) and not an explicit Notion publish. Never writes to ~/Desktop. Skip for feature artifacts (proposal, plan, tasks, specs, handoff, reviews) which stay under .giantmem/.
---
<!-- caveman:compressed -->

Vault = source of truth for local knowledge. Notion = projection, only on explicit "publish"/"share"/"notion this" (then `notion-publish` skill on the vault path). Desktop = never.

## Write

Body to a scratchpad file, then:

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py new \
  --title "recharge-auth Redis keys and TTLs" \
  --area auth \
  --tags redis,ttl \
  --body-file "$SCRATCH/body.md"
```

Prints abs path. Report that path to the user, nothing else.

- `--area` required, closed list below. Pick one; tags carry overlap.
- `--project` defaults to git repo name of cwd (worktree parent minus `-wt`, so `cc-wt/stage` gives `cc`). Pass it when cwd is not the subject repo or the default is too terse.
- `--tags` comma list, lowercase, hyphenated. `claude` prepended always.
- `--created` ISO 8601, only for imports (birthtime). Default now with tz.
- Body starting with `# ` keeps its own H1; otherwise `# <title>` is inserted.
- Filename = slug of title. Collision appends `-YYYY-MM-DD`, then `-N`. Never overwrite.

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

New area = edit `AREAS` in `scripts/note.py` and this table, same commit.

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

`id, aliases, tags, area, project` = obsidian.nvim contract, do not add or rename keys. `created` is the only addition. Do not hand-write frontmatter; the script owns it.

## Read before write

```bash
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --area auth --since 90
python3 ~/.claude/skills/obsidian-note/scripts/note.py list --tag redis
```

One line per note: `created | area | project | path | title`. Read the hits that match the subject before writing a new note. Extend an existing note (Edit) when the subject is the same; new note when the subject is new.

## Rules

- Vault pushes to GitHub every 5 min. No secrets, tokens, connection strings with passwords, query dumps, or customer PII. Redact `<REDACTED:token>`. Raw dumps stay in the scratchpad.
- Shared-doc rules apply (no local paths, no "as of", no changelog) only when the user says the note is for others. Notes for the user alone keep paths and dates.
- Feature state stays in `.giantmem/`: proposal, plan, tasks, specs, facts, handoff, reviews, research tied to an in_progress feature. Cross-repo durable knowledge (runbook, incident writeup, design note, reference, decision record, how-to) goes to the vault.
- Do not write `areas/index.md`; it is a Dataview page.
- Wiki links `[[note]]` resolve vault-wide; link existing notes by stem when relevant.
