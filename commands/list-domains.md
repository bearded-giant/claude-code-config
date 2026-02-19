---
description: "List all indexed code domains from the knowledge base"
argument-hint: "[--verbose]"
---

# List Domains

Display all domains in the knowledge base from `.giantmem/domains/_index.json`.

## Arguments

- `--verbose`: Show expanded details (key_paths, features, file counts) instead of compact table

## Steps

### 1. Read the index

Read `.giantmem/domains/_index.json`. If it doesn't exist, tell the user: "No domains indexed yet. Run `/plan-feature` to explore code domains."

### 2. Display domains

**Default (compact):**

```
Code Domains ({n} indexed)

| Domain | Description | Explored | Features |
|--------|-------------|----------|----------|
| auth_session | Authentication and session management | 2026-02-10 | jwt-session-cookie, jwt-enforcement |
| payment_flow | Payment processing pipeline | 2026-02-14 | checkout-redesign |
| merchant_api | Merchant-facing API endpoints | 2026-01-28 | merchant-settings |
```

**With `--verbose`:**

For each domain, also show:
- key_paths (directories/files the domain covers)
- number of key_files and entry_points in the JSON
- whether it's stale (last_explored > 7 days ago)

```
auth_session - Authentication and session management
  explored: 2026-02-10 (6 days ago)
  paths: src/services/auth_session/, src/api/auth/
  coverage: 8 key files, 3 entry points
  features: jwt-session-cookie, jwt-enforcement

payment_flow - Payment processing pipeline [STALE - 14 days]
  explored: 2026-02-02
  paths: src/services/payment/, src/api/checkout/
  coverage: 12 key files, 5 entry points
  features: checkout-redesign
```

### 3. Tip

After the listing, add:
```
Load a domain: "read .giantmem/domains/{name}.json"
Search domains: /search-domains <query>
Refresh stale: /update-domains --all-stale
```

## Rules

- Read-only. Do not modify any files.
- Do not read individual domain JSONs unless `--verbose` is set (the index has enough for the compact view).

$ARGUMENTS
