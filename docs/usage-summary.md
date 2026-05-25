# Artifact + spec workflow — usage summary

What shipped from the OpenSpec-hybrid migration. Two-column "before / after" so you can grok the diff, then a daily-driver cheat sheet.

## The single biggest shift

Per-feature `spec.md` split into three artifact types:

| Type | Lives | Holds |
|---|---|---|
| `proposal` | `features/{name}/proposal.md` | intent + scope + approach. NOT behavior. |
| `delta-spec` | `features/{name}/specs/{domain}/spec.md` | `## ADDED / MODIFIED / REMOVED Requirements` blocks. Each Requirement has `#### Scenario:` (GIVEN / WHEN / THEN, RFC 2119). |
| `source-spec` | `.giantmem/specs/{domain}/spec.md` | accumulated behavior across every completed feature. `/complete-feature` merges delta-specs in. Never hand-edit mid-feature. |

Legacy `features/{name}/spec.md` symlinks → `proposal.md` for ~30 days. Old `cat features/foo/spec.md` muscle memory keeps working.

The second-biggest shift: every `.md` / `.yaml` artifact under `.giantmem/` now starts with YAML frontmatter (`type`, `status`, `feature` or `repo`, …). That's what makes the typed query layer possible.

## Before vs after

| Task | Before | After |
|---|---|---|
| Create a feature | `/new-feature foo` → `spec.md` (purpose + acceptance criteria all in one) | `/new-feature foo` → `proposal.md` (intent only) + empty `specs/` + `tasks.md`, all with frontmatter, then auto-reindex |
| Capture behavior | bullet "Acceptance Criteria" inside `spec.md` | `features/foo/specs/{domain}/spec.md` with `## ADDED Requirements`, each `### Requirement:` carrying `#### Scenario:` GIVEN/WHEN/THEN blocks |
| Complete a feature | `/complete-feature` flips `meta.json` status, updates indexes | `/complete-feature` merges delta-specs into `.giantmem/specs/{domain}/spec.md`, writes per-feature `spec_history.md` AND repo-level `_history.md`, then flips status + reindexes |
| Find a related doc | `grep -r` across `.giantmem/`, then climb worktrees by hand | `giantmem artifact list --type X --repo all` or `gma` (fzf) or MCP `find_artifact(...)` |
| Track task progress | manually edit `meta.json.status` | `tasks.md` checkboxes auto-derive status (0% = draft, 0<x<100% = ready, 100% = done) on every reindex |
| Lint feature shape | none | `/feature-validate foo` (warn/error), `/feature-validate foo --fix` auto-repairs structural gaps |
| "What should I write next?" | reread plan | `/feature-next` — reads `artifacts.json` + `config/artifact_dag.yaml`, prints next ready artifact + suggested path |
| Forgotten work | none | `giantmem artifact stale [--all-repos] [--days N]` |

## Net new — daily driver cheat sheet

### Terminal — `giantmem artifact` subcommands

```bash
# current repo, all types
giantmem artifact list

# filter
giantmem artifact list -t delta-spec -s ready
giantmem artifact list -f openspec-compare
giantmem artifact list -d auth

# cross-repo (87 live workspaces on this mac as of writing)
giantmem artifact list --repo all -t proposal
giantmem artifact list --repo all --include-archived -t proposal   # include ~/giantmem_archive/

# branch-keyed (same feature name across worktrees)
giantmem artifact list -f session-cookie --branch jwt-session-cookie

# read one
giantmem artifact show feat:openspec-compare:proposal

# rebuild index (already wired into /new-feature + /complete-feature)
giantmem artifact reindex

# linters
giantmem artifact orphans                    # files lacking frontmatter
giantmem artifact stale --days 30            # current repo, untouched >30d
giantmem artifact stale --all-repos --days 90
```

### Interactive — `gma` fzf picker

```bash
gma                                  # default --repo all, opens selection in $EDITOR
gma -t delta-spec -d workflow        # filter then pick
gma --include-archived               # surface old worktree snapshots
gma --path                           # print path to stdout instead of opening
```

### Slash commands

| Command | What it does |
|---|---|
| `/new-feature <name>` | scaffolds `proposal.md` + `tasks.md` + empty `specs/` + frontmatter, reindexes |
| `/start-feature <name>` | unchanged in shape — pending → in_progress |
| `/complete-feature [--no-merge] [--reason "..."]` | merges delta-specs to source-of-truth, flips delta status → done, writes both history files, reindexes. Skips merge when `specs/` empty or `--no-merge` passed. |
| `/feature-validate <name> [--fix]` | structural lint; `--fix` runs rename + frontmatter backfill + scaffold + reindex. Never touches content. |
| `/feature-next [name]` | informational — reads index + DAG, prints next ready artifact + path + hint |
| `/feature-report [name]` | parses delta-spec Requirements (legacy "Acceptance Criteria" bullets are fallback) |
| `/plan-feature [name]` | now reads proposal + delta-specs + source-specs when deriving domains |

### MCP tools (in-Claude, no shell)

| Tool | Use |
|---|---|
| `find_artifact(type, status, feature, domain, repo, branch, query, limit)` | typed search across one repo or every workspace. Returns ID + path + status + snippet (when `query` matches). |
| `get_artifact(id)` | full frontmatter + body for one ID. |
| `list_features_with_artifacts(repo, artifact_types)` | "show every feature with open tasks across all my repos." |

Six existing tools (`search_archive`, `list_sessions`, `get_session_summary`, `recent_writes`, `feature_status`, `workspace_tree`) still there — total 9 now.

### Session start

The session hook now appends an `ACTIVE ARTIFACTS` block to the context block at session start, summarizing the live `artifacts.json`. Shape:

```
=== ACTIVE ARTIFACTS ===
repo=claude-code-config branch=feat/openspec-compare total=24
by type: delta-spec=4, facts=3, notes=2, pattern=3, plan=4, proposal=3, research=3, source-spec=2
  better-search: ready:4  ready: plan/current, delta-spec/better-search
  openspec-compare: ready:7  ready: plan/migration_plan, delta-spec/workflow
```

Cuts the "where was I?" overhead at session start.

### Scripts (giant-tooling/workspace/scripts/)

| Script | What it does | When |
|---|---|---|
| `backfill_frontmatter.py` | stamps legacy `.md` / `.yaml` / `.json` with YAML frontmatter inferred from path | one-shot per repo, or whenever you've added files outside the commands |
| `migrate_spec_to_proposal.py` | renames `features/*/spec.md` → `proposal.md`, splits any `## Requirements` block into a delta-spec, leaves a back-compat symlink | one-shot per repo (already done for claude-code-config) |
| `merge_delta_spec.py <feature> [--dry-run] [--reason "..."]` | applies ADDED/MODIFIED/REMOVED to source-of-truth; idempotent | called by `/complete-feature`; runnable by hand for mid-feature spot merges |

### Templates (`templates/` in claude-code-config)

`proposal.md`, `source_spec.md`, `delta_spec.md`, `tasks.md`, `design.md` — canonical scaffolds. `/new-feature` references them.

### DAG config

`config/artifact_dag.yaml` — type → requires map. Drives `/feature-next` only. Tweak freely; no rebuild needed.

## Frontmatter shape — quick reference

```yaml
---
type: delta-spec
feature: openspec-compare
domain: workflow
status: ready                # draft | ready | done | blocked | stale
repo: claude-code-config
branch: feat/openspec-compare
created: 2026-05-25
updated: 2026-05-25
---
```

Required for indexing: `type`, `status`, plus either `feature` (per-feature artifact) or `repo` (repo-level).

JSON artifacts (`meta.json`, `domains/*.json`) put the same keys at top level — no `---` fences.

## The decisions table (recap)

These shaped the migration. Worth reskimming when something feels off.

| # | Decision | Where it lands |
|---|---|---|
| 1 | Hardcoded taxonomy v1, plugin model v2 fast-follow | `internal/artifacts/types.go` `ValidType` |
| 2 | YAML frontmatter for `.md` AND `.yaml` artifacts | `backfill_frontmatter.py` + `internal/artifacts/frontmatter.go` |
| 3 | Rename `spec.md` → `proposal.md`; behavior moves into delta-specs | `migrate_spec_to_proposal.py` + commands/templates |
| 4 | FTS join (no separate archive index for artifacts) | crawl walks files; archives.db FTS unchanged |
| 5 | Tasks auto-promote from checkbox % | `internal/artifacts/scan.go` `taskStatusFromFile` |
| 6 | Index keyed on `(repo, branch, feature)` — separate entries for same feature in different branches | `Index` shape + `--branch` filter |
| Loose | `/complete-feature` never blocks — empty specs = silent skip, `--no-merge` to skip even when present | `commands/complete-feature.md` step 3 + `merge_delta_spec.py` |
| Both-histories | per-feature `spec_history.md` AND repo `.giantmem/specs/_history.md` | `merge_delta_spec.py` `write_history` |
| Domain reuse | `domains/{name}.json` (code KB) and `specs/{name}/spec.md` (behavior contract) share the namespace | informational hint in `/plan-feature` |

## What is NOT done (deferred follow-ups)

Tracked, not blocking:

1. Plugin-v2 artifact taxonomy via `~/.config/giantmem/artifact_types.toml`
2. Filesystem watcher for auto-reindex (today: reindex on feature commands or by hand)
3. Paired-feature view — `--paired` joins cwt ↔ fewt branches that share a feature name
4. Full SQL `artifacts` table in `archives.db` with FTS join (today: file-walk crawl, fine until ~hundreds of workspaces)
5. Adversarial test for `/feature-validate --fix` — verify a hand-written proposal body is byte-identical after fix

## Where to read more

| Topic | File |
|---|---|
| Mental model + invariants | `~/.claude/CLAUDE.md` "Three-Spec Model" + "Finding artifacts" sections |
| Output rules | `~/.claude/skills/workspace-rules/SKILL.md` |
| Feature lifecycle + commands table | `~/.claude/skills/feature-management/SKILL.md` |
| The full plan that drove this | `.giantmem/features/openspec-compare/plans/migration_plan.md` |
| Cross-repo findability design | `.giantmem/features/openspec-compare/plans/artifact_registry.md` |
| What was compared in the first place | `.giantmem/features/openspec-compare/research/comparison.md` |
