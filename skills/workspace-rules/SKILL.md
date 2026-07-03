---
name: workspace-rules
description: Output rules for .giantmem/ — directory selection, format, verbosity, anti-patterns, naming. Auto-fires before writing any file under .giantmem/**, before writing to repo docs/, when user asks to "save findings", "write a plan", "document this", or invokes /ws-init. Also fires when generating long-form analysis or reference docs.
---

Output rules for `.giantmem/` workspace. Loads on-demand.

## Critical rules

1. **Feature-scoped routing applies.** When a feature is `in_progress`, plans/research/reviews/filebox go inside the active feature dir. See [[feature-management]] for routing table.
2. **Never write to repo `docs/` unprompted.** Repo `docs/` is shipped doc, human-owned. Route Claude-generated output to `.giantmem/context/<topic>.md` or the active feature's `research/`.
3. **Never output long-form content only in chat.** If `.giantmem/` exists and output is >40 lines or has tables/diagrams, write to the correct subdir per the routing tables below.

## Open Questions block

When a doc has unresolved questions, put them at the TOP under `## Open Questions for User`. Before any TOC, summary, or content. Buried questions get missed.

Format: numbered list, mark blocking vs non-blocking.

```markdown
## Open Questions for User
1. [BLOCKING] Should auth tokens expire at 1h or 24h?
2. [non-blocking] Redis or Postgres for session store?
```

Remove the section once answered.

## Global directories — always at `.giantmem/` level

| Directory | Format | Verbosity | Example |
|---|---|---|---|
| `artifacts.json` | Live artifact index | Machine-built, never hand-edit | Built by `giantmem artifact reindex` |
| `features/_index.md` | Registry table | Terse, table rows | Feature name, status, beta flag |
| `features/{name}/proposal.md` | Feature intent (renamed from spec.md) | Medium, structured | Intent + scope + approach |
| `features/{name}/design.md` | Technical design (optional) | Medium | Architecture, decisions, file changes |
| `features/{name}/tasks.md` | Checkbox list | Hierarchical | Auto-status from checkbox % |
| `features/{name}/specs/{domain}/spec.md` | Delta-spec | Structured | ADDED / MODIFIED / REMOVED Requirements |
| `features/{name}/facts.md` | Quick lookup | Terse, key-value | Beta flags, config keys, test cmds |
| `features/{name}/plan.md` | Implementation plan | Concise, actionable | Steps, file paths, function names |
| `specs/_index.md` | Source-spec registry | Terse, table rows | Domains, last merged, requirement counts |
| `specs/_history.md` | Spec merge log | Append-only | Chronological per `/complete-feature` merge |
| `specs/{domain}/spec.md` | Source-of-truth spec | Requirements + Scenarios | RFC 2119, Given/When/Then. Merged from delta-specs. |
| `context/patterns.md` | Curated patterns | Medium, organized | Architectural decisions, gotchas |
| `context/*.md` | Reference docs | Minimal prose, lists ok | API lists, dep maps |
| `history/sessions.md` | Session log | One line per session | `- 2026-05-18: worked on auth` |
| `prompts/*.md` | Prompt templates | N/A | Reusable templates |

## Feature-scoped directories — inside active feature when present, else `.giantmem/` level

| Directory | Format | Verbosity | Example |
|---|---|---|---|
| `plans/current.md` | Transient session work | Concise, mutates throughout session | Active task steps. Deleted on `/complete-feature`. |
| `research/*.md` | Findings + sources | Medium, cite sources | Key findings, code examples |
| `reviews/*.md` | Issues + locations | Terse, file:line refs | Bullets with code refs |
| `filebox/*` | Raw data | N/A | JSON, logs, samples |

`tasks.md` vs `plans/current.md`: tasks.md is durable, archived with feature, OpenSpec-style checkbox list with auto-status from checkbox %. `plans/current.md` is transient scratchpad — what you're currently handling, mutates throughout the session, deleted on `/complete-feature`.

`context/discoveries.md` deprecated. Use `context/patterns.md` for curated architectural patterns.

## Frontmatter requirement

Every `.md` and `.yaml` artifact MUST start with YAML frontmatter:

```yaml
---
type: {one of: source-spec | delta-spec | proposal | design | tasks | plan | research | review | notes | pattern | facts}
feature: {name}              # for feature-scoped artifacts
repo: {repo-name}            # for repo-level artifacts (one of feature or repo)
status: {draft | ready | done | blocked | stale}
lifecycle: {durable | candidate | deprecated}    # SHOULD; default durable
scope: {scope_id}            # optional; overrides repo→scope membership
domain: {name}               # optional
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

JSON artifacts (`meta.json`) get the same keys at top level (no `---` fences).

Lifecycle stage rules:
- `durable` (default): human-authored, scaffolded by `/new-feature`, accumulated source-specs. Never auto-pruned.
- `candidate`: AI-captured discoveries / research / mid-session notes. Surface in `/review-memory` for promote → durable / demote → deprecated.
- `deprecated`: kept on disk but excluded from default preload packs and stale reports.

Backfill legacy files:
- Frontmatter keys: `python3 ~/dev/giant-tooling/workspace/scripts/backfill_frontmatter.py`
- Lifecycle only: `python3 ~/dev/giant-tooling/workspace/scripts/backfill_lifecycle.py`

## Anti-patterns — DO NOT

- "Phase 1:", "Step 1 of 5:", progress tracking headers
- "Work in Progress", "Status:", progress banners
- Verbose summaries of what you're about to do
- Dump everything into `plans/` — use correct directory
- Filler text ("Great!", "Let's begin by...")
- Multiple files when one suffices

## File naming

- snake_case: `auth_flow_plan.md`, `replica_lag_analysis.md`
- Suffix indicates type: `*_plan.md`, `*_analysis.md`, `*_api.md`

## Format examples

**features/_index.md — CORRECT:**

```markdown
| Feature | Status | Beta Flag | Builds On | FE |
|---|---|---|---|---|
| [jwt-session-cookie](jwt-session-cookie/) | complete | `enable_jwt_session_cookie` | - | - |
| [jwt-session-enforcement](jwt-session-enforcement/) | in_progress | `enable_jwt_session_enforcement` | jwt-session-cookie | FE: jwt-session-enforcement |
```

**features/{name}/facts.md — CORRECT:**

```markdown
## Identifiers
beta_flag: enable_jwt_session_enforcement
config_keys:
  - JWT_SESSION_SECRET

## Test Commands
docker compose run --rm test pytest -s --disable-warnings tests/services/auth_session/
```

**context/patterns.md — CORRECT:**

```markdown
## Session Layer
- Redis key format: `rc_session_{user_id}_{store_id}_{session_id}`
- Lookup by session_id: use SCAN with pattern `rc_session_*_*_{session_id}`

## Gotchas
- SQLAlchemy session isolation causes stale cache in tests
```

**plans/current.md — CORRECT:**

```markdown
# Active: Add session lookup endpoint

## Steps
1. Add get_session_by_session_id to session_store.py
2. Create API resource
3. Register route
```

**WRONG — verbose phase tracking:**

```markdown
## Phase 1: Research and Planning
- [ ] Review current authentication flow
## Progress Tracking
- Started: 2026-01-15
- Status: In Progress
```

## On /ws-init

Organize loose files in `.giantmem/` root:

1. Move `.md` files (except `WORKSPACE.md`):
   - `*_analysis.md`, `*_research.md` → `research/`
   - `*_plan.md`, `*_design.md` → `plans/`
   - `*_endpoints.md`, `*_api.md` → `context/`
   - `*_review.md` → `reviews/`
   - Other `.md` → `context/` (default)

2. Move non-markdown (`.json`, `.yaml`, `.sh`) → `filebox/`

## Concise output

When user asks for "concise":

| Ask | Format |
|---|---|
| Question | 1-2 sentences + up to 5 bullets |
| Analysis | Max 2 short paragraphs + up to 5 summary bullets |
| Pros and cons | 3-4 sentence summary + table (not lists) |

For workspace docs: same constraints. Bullets/tables over prose. Code snippets over prose explanations. No filler paragraphs.
