---
name: feature-management
description: Feature folder lifecycle, scoping, and feature-scoped output routing for .giantmem/features/. Auto-fires when user says "create a plan", "draft a plan", "plan this out", "new feature", or invokes /new-feature, /plan-feature, /start-feature, /pause-feature, /complete-feature, /reopen-feature, /list-features, /feature-facts, /feature-report. Also fires before writing to .giantmem/features/** or when checking which feature is active.
---

Feature system for `.giantmem/features/`. Persistent capabilities that span sessions.

## Folder structure

```
features/
├── features.json          # cache, every command reads/writes
├── _index.md              # human-readable registry
├── {feature-name}/
│   ├── spec.md            # what + why + acceptance
│   ├── facts.md           # beta flags, config, test commands
│   ├── meta.json          # machine-readable (swarm)
│   ├── plan.md            # /plan-feature output
│   ├── plan_context.json  # domain linkage
│   ├── plans/current.md   # session work scoped here
│   ├── research/          # scoped research
│   ├── reviews/           # scoped reviews
│   └── filebox/           # scoped data
```

## Cache discipline — CRITICAL

Every feature command (new/start/pause/complete/reopen) MUST update both:
- `.giantmem/features/features.json`
- `.giantmem/features/_index.md`

When adding beta flags or key config, add to Quick Reference section.

## Domain knowledge base

```
domains/
├── _index.json
├── {domain-name}.json
```

Repo-level, not feature-scoped. Created by `/plan-feature`, refreshed by `/update-domains` and `/complete-feature`. Load relevant domain JSONs at session start instead of re-reading code.

## When to create a feature folder

- Distinct capability, not a bug fix
- Spans multiple sessions
- Has identifiable artifacts (beta flag, endpoints)

## Commands

| Command | Purpose |
|---|---|
| `/list-features` | display registry |
| `/new-feature <name>` | scaffold folder (auto-detects pending vs in_progress) |
| `/plan-feature [name] [--refresh]` | explore domains, draft plan |
| `/list-domains [--verbose]` | show indexed domains |
| `/search-domains <query> [--load]` | search domain JSONs |
| `/update-domains [domains] [--all-stale]` | refresh domain JSONs |
| `/feature-facts <name>` | quick lookup |
| `/feature-report [feature]` | validation report |
| `/start-feature <name>` | promote pending → in_progress |
| `/pause-feature` | mark current paused |
| `/complete-feature` | mark complete, update index |
| `/reopen-feature <name>` | complete → in_progress |

## "Create a plan" disambiguation — CRITICAL

When user says "create a plan", "plan this out", "draft a plan", or similar, MUST emit AskUserQuestion BEFORE any file write:

```
Question: feature (persistent, spans sessions) or session work (transient)?
Options:
  1. feature → /new-feature → features/{name}/spec.md
  2. session work → plans/current.md
```

Ask first. Write second. User often forgets which context they're in.

## Feature-scoped output routing

When a feature has status `in_progress` in `features.json`, it is the **active feature**. All session output that would normally go to top-level `.giantmem/` subdirectories MUST instead go inside the active feature's directory:

| Without active feature | With active feature `{name}` |
|---|---|
| `.giantmem/plans/current.md` | `.giantmem/features/{name}/plans/current.md` |
| `.giantmem/research/{topic}.md` | `.giantmem/features/{name}/research/{topic}.md` |
| `.giantmem/reviews/{subject}.md` | `.giantmem/features/{name}/reviews/{subject}.md` |
| `.giantmem/filebox/*` | `.giantmem/features/{name}/filebox/*` |

## Always global — NEVER feature-scoped

- `domains/` — repo-level code knowledge
- `history/` — session log spans all features
- `prompts/` — reusable templates
- `context/patterns.md` — curated architectural patterns (repo-level)
- `WORKSPACE.md`, `features/_index.md`, `features.json`

Create subdirectories inside feature folder on first write. Don't require upfront.

When no feature is `in_progress`, use top-level `.giantmem/` subdirectories.

## Session start check

Read in order if files exist:
1. `.giantmem/WORKSPACE.md`
2. `.giantmem/features/features.json` — find active feature
3. Active feature's `plans/current.md`, else `.giantmem/plans/current.md`

If step 1's file is missing, skip steps 2-3.
