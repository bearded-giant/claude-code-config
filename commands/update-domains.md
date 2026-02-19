---
description: "Update domain JSONs after code changes. Refresh specific domains or detect stale ones."
argument-hint: "[domain1,domain2,...] [--all-stale] [--for=feature-name]"
---

# Update Domains

Refresh domain exploration JSONs after code changes. Use this when key files in a domain have been modified, added, or removed and the domain JSON is now out of date.

## Arguments

- domains: (optional) Comma-separated domain names to update (e.g., `auth_session,payment_flow`)
- `--all-stale`: Update all domains whose key_paths have git changes since last_explored
- `--for={feature}`: Scope to domains referenced by a specific feature's plan_context.json

If no arguments provided, detect stale domains automatically and ask.

## Steps

### 1. Load domain index

Read `.giantmem/domains/_index.json`. If it doesn't exist, tell the user to run `/plan-feature` first to create initial domain explorations.

### 2. Determine which domains to update

**If specific domains provided:** validate each exists in the index.

**If `--all-stale` provided:**
For each domain in the index, check if files under its `key_paths` have changed since `last_explored`:
```
git log --since="{last_explored}" --name-only -- {key_paths}
```
If any files changed, mark that domain as stale.

**If `--for={feature}` provided:**
Read `.giantmem/features/{feature}/plan_context.json` and get `domains_referenced`. Check each for staleness.

**If no arguments:**
Run the staleness check on all domains, then present the stale ones and ask the user which to update. Also list any domains that have never been explored but whose key_paths appear in recent git diffs.

### 3. Read current domain JSONs

For each domain being updated, read `.giantmem/domains/{domain}.json` to understand what was previously captured.

### 4. Re-explore each domain

For each domain, launch a code-explorer agent with the same structured prompt format used in `/plan-feature` step 4. Include the previous domain JSON as context so the agent can focus on what changed:

```
Re-explore the "{domain_name}" domain. Here is the previous exploration:

{previous domain JSON}

Focus on changes and additions since {last_explored}. Update all sections with current state. Flag anything that was removed or significantly refactored.

Output your findings in this exact structure:
{same structured format as plan-feature step 4}
```

Run agents in parallel when updating multiple domains.

### 5. Update domain JSONs

For each domain, update `.giantmem/domains/{domain_name}.json`:
- Replace all fields with fresh exploration data
- Preserve `explored_for_features` (merge, don't replace)
- Update `last_explored` to today
- If the domain was explored for a specific feature (`--for`), append that feature to `explored_for_features`

### 6. Update domain index

Update `.giantmem/domains/_index.json`:
- Update `last_explored` for each refreshed domain
- Update `key_paths` if the exploration revealed new paths
- Update `features` list
- Set `last_updated` to today

### 7. Update affected feature plan_context.json files

For each updated domain, check which features reference it:
- Read the domain's `explored_for_features` list
- For each feature that has a `plan_context.json`, update the `domains_refreshed` list

This is informational only -- don't modify the feature's plan.md (the user may want to re-plan, or the plan may still be valid).

### 8. Report

```
Domains updated:
  - auth_session: 4 files changed since last exploration
  - payment_flow: 2 files changed

Referenced by features:
  - auth_session -> jwt-session-enforcement, jwt-session-cookie
  - payment_flow -> checkout-redesign

Domain index: .giantmem/domains/_index.json ({n} total domains)

Tip: If a feature plan is now outdated, run /plan-feature {feature} --refresh
```

## Rules

- Do NOT modify code files, only scratch workspace files
- Read every file before modifying it
- Domain JSONs capture what the code IS, not what it should be
- Keep updates factual and grounded in the actual code
- All JSON must be valid, parseable JSON
- All comments in JSON values must be lowercase

$ARGUMENTS
