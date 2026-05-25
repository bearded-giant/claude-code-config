---
description: "Explore codebase domains and create a structured plan for the active feature. Outputs LLM-consumable domain JSONs."
argument-hint: "[feature-name] [--refresh]"
---

# Plan Feature

Explore relevant code domains, output structured domain JSONs, and draft an implementation plan for a feature. Domain JSONs are repo-level knowledge -- reusable across features and sessions.

Domains are derived automatically from the feature spec and codebase analysis. The user does not need to know or specify domain names -- Claude identifies them.

## Arguments

- feature: (optional) Feature name in kebab-case. If not provided, use the current in_progress feature from `.giantmem/features/features.json`.
- `--refresh`: Force re-exploration of domains that already have JSONs.

## Directory Structure

Domain JSONs live at repo level, not per-feature:

```
.giantmem/
  domains/
    _index.json           # registry of all domain explorations
    auth_session.json     # domain exploration
    payment_flow.json     # domain exploration
  features/{name}/
    plan.md               # implementation plan (references domains)
    plan_context.json     # which domains informed this plan
```

## Steps

### 1. Identify the feature

If no argument provided:
- Read `.giantmem/features/features.json` and find the feature with `"status": "in_progress"`
- If multiple in_progress, list them and ask
- If none, tell the user to run `/new-feature` or `/start-feature` first

Validate `.giantmem/features/{feature}/proposal.md` exists (or legacy `spec.md` symlink). Read it.

Also read all delta-specs at `.giantmem/features/{feature}/specs/{domain}/spec.md` (may be empty) and any source-specs at `.giantmem/specs/{domain}/spec.md` for domains the feature touches. Delta-specs describe what behavior changes; source-specs describe current behavior. Both inform the plan.

### 2. Ensure domains directory exists

Create `.giantmem/domains/` if it doesn't exist. Create `.giantmem/domains/_index.json` as `{"repo": "", "last_updated": "", "domains": {}}` if it doesn't exist.

Read `.giantmem/domains/_index.json`.

### 3. Derive domains from the feature spec and codebase

Domains are NOT user-supplied. Claude derives them by:

1. Reading the proposal + delta-specs for clues about what code areas are involved
2. Doing a quick scan of the codebase structure (top-level dirs, module layout, key config files) to understand how the repo is organized
3. Cross-referencing with existing domain index (if any domains already exist)
4. Cross-referencing with existing source-specs at `.giantmem/specs/` — a source-spec for a given name signals that area has already accumulated behavior contracts

From this, propose a set of domains to the user. Each domain should represent a distinct, bounded area of the codebase. Use snake_case names that describe the area, not the feature (e.g., `auth_session` not `jwt_enforcement`).

Present them like:
```
Based on the spec and codebase, I'd explore these domains:

  - command_system (new) -- how commands are structured and loaded
  - feature_lifecycle (exists, explored 2026-02-10) -- new/start/pause/complete workflow
  - workspace_management (new) -- scratch dirs and output rules

Confirm, or adjust?
```

The user can add, remove, or rename domains. Then for each confirmed domain, determine:
- **New**: no existing JSON, needs full exploration
- **Refresh**: existing JSON but `--refresh` flag or user requested update
- **Reuse**: existing JSON, still current (< 7 days), just reference it

### 4. Explore new/refresh domains

For each domain that needs exploration, launch a code-explorer agent (run agents in parallel when exploring multiple domains). Give each agent this prompt structure:

```
Explore the "{domain_name}" domain of this codebase. Focus on: {description of what this domain covers}.

Output your findings in this exact structure (I will parse this into JSON):

DOMAIN: {domain_name}
DESCRIPTION: {one-line description}

ENTRY_POINTS:
- path: {file path}
  type: {api_endpoint|cli_command|ui_component|service|middleware|other}
  description: {what it does}

KEY_FILES:
- path: {file path}
  purpose: {what this file is responsible for}
  exports: {key functions/classes/methods exported}
  patterns: {design patterns used}
  dependencies: {what this file depends on}

ARCHITECTURE:
  layers: {ordered list of abstraction layers}
  data_flow: {how data moves through this domain}
  patterns: {architectural patterns in use}
  key_decisions: {important design decisions and their rationale}

DATA_MODELS:
  tables: {database tables involved}
  cache_keys: {Redis/cache key patterns}
  schemas: {key data shapes}

DEPENDENCIES:
  internal: {other domains/modules this depends on}
  external: {third-party packages}

GOTCHAS:
- {things that are non-obvious, tricky, or have bitten people}
```

### 5. Parse exploration into domain JSONs

For each explored domain, create/update `.giantmem/domains/{domain_name}.json`:

```json
{
  "domain": "{domain_name}",
  "description": "{one-line description}",
  "last_explored": "{today's date}",
  "explored_for_features": ["{feature_name}"],
  "entry_points": [
    {
      "path": "src/api/auth/session_resource.py",
      "type": "api_endpoint",
      "description": "REST endpoint for session operations"
    }
  ],
  "key_files": [
    {
      "path": "src/services/auth_session/session_store.py",
      "purpose": "Redis-backed session storage",
      "exports": ["get_session", "create_session", "invalidate_session"],
      "patterns": ["repository pattern"],
      "dependencies": ["redis_client", "config.JWT_SESSION_SECRET"]
    }
  ],
  "architecture": {
    "layers": ["API resource", "service", "data store"],
    "data_flow": "request -> middleware -> service -> store",
    "patterns": ["repository pattern", "middleware chain"],
    "key_decisions": ["sessions in Redis with TTL"]
  },
  "data_models": {
    "tables": [],
    "cache_keys": [],
    "schemas": {}
  },
  "dependencies": {
    "internal": ["merchant_auth"],
    "external": ["redis", "pyjwt"]
  },
  "gotchas": [
    "SQLAlchemy session isolation causes stale cache in tests"
  ]
}
```

If updating an existing domain JSON:
- Merge `explored_for_features` (append, don't replace)
- Update all other fields with fresh exploration data
- Update `last_explored` to today

### 6. Update domain index

Update `.giantmem/domains/_index.json`:

```json
{
  "repo": "{repo name from git or directory}",
  "last_updated": "{today's date}",
  "domains": {
    "{domain_name}": {
      "file": "{domain_name}.json",
      "description": "{one-line description}",
      "last_explored": "{today's date}",
      "key_paths": ["src/services/auth_session/", "src/api/auth/"],
      "features": ["jwt-session-cookie", "jwt-session-enforcement"]
    }
  }
}
```

For existing domains not being refreshed, leave their entries untouched. Merge the features list (append current feature if not already listed).

### 7. Draft the feature plan

Write `.giantmem/features/{feature}/plan.md`:

```markdown
# Plan: {feature name (title case)}

planned: {today's date}
domains: {comma-separated list of domain names referenced}

## Context

{Brief summary of what the feature does, pulled from spec.md}

## Domain Knowledge

{For each domain referenced, a 2-3 line summary of what's relevant to this feature. Reference the domain JSON file path.}

## Implementation Steps

1. {concrete step with file paths}
2. {concrete step}
...

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| path/to/file.py | modify | add session validation |
| path/to/new_file.py | create | new endpoint |

## Open Questions

- {anything unresolved}
```

Use the domain JSONs and feature spec to inform the plan. The plan should be concrete -- actual file paths, function names, specific changes. Not vague phases.

### 8. Write plan_context.json

Write `.giantmem/features/{feature}/plan_context.json`:

```json
{
  "feature": "{feature_name}",
  "domains_referenced": ["auth_session", "merchant_api"],
  "domains_created": ["auth_session"],
  "domains_refreshed": [],
  "domains_reused": ["merchant_api"],
  "planned_at": "{today's date}"
}
```

### 9. Update meta.json

Add plan-related fields to `.giantmem/features/{feature}/meta.json`:

```json
{
  "planned": true,
  "planned_at": "{today's date}",
  "domains": ["auth_session", "merchant_api"],
  "last_session": "{today's date}"
}
```

### 10. Report

```
Feature '{feature}' planned.

Domains explored:
  - auth_session (new) -> .giantmem/domains/auth_session.json
  - merchant_api (reused, explored 2026-02-10)

Plan: .giantmem/features/{feature}/plan.md
Context: .giantmem/features/{feature}/plan_context.json

Domain index: .giantmem/domains/_index.json ({n} total domains)
```

## Rules

- Do NOT modify code files, only scratch workspace files
- Read every file before modifying it
- Domain JSONs are repo-level assets, not feature-scoped. Treat them as shared knowledge.
- When a domain JSON already exists and is recent (< 7 days), default to reusing it unless `--refresh` is set or user asks
- Keep domain JSONs factual -- no opinions, no plan content, just what the code IS
- Keep plan.md actionable -- concrete steps, file paths, function names
- All JSON must be valid, parseable JSON
- All comments in JSON values must be lowercase

$ARGUMENTS
