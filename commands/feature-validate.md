---
description: Lint a feature's structure (proposal/delta-specs/tasks/facts/frontmatter). `--fix` auto-repairs structural gaps.
argument-hint: "<feature-name> [--fix]"
---

Lint a feature folder's structure and frontmatter. With `--fix`, auto-repair
structural gaps (run A.5 rename, backfill frontmatter, scaffold missing files,
reindex). Never modifies user-written content.

## Arguments

- feature: (required) Feature name in kebab-case. Pass `--all` to validate every
  feature in `.giantmem/features/`.
- `--fix`: (optional) Apply auto-repairs. Idempotent — re-runs are no-ops on
  clean features.

## Steps

1. **Resolve target features.**
   - `--all` → iterate every dir under `.giantmem/features/` that has `meta.json`.
   - Else → single feature at `.giantmem/features/{feature}/`.

2. **For each feature, run these checks:**

   ### Structural

   | Check | Severity |
   |---|---|
   | `meta.json` parses, has `name`, `status`, `branch`, `base_branch`, `created` keys | error |
   | `proposal.md` exists (or legacy `spec.md` symlink) | warn — fixable |
   | `proposal.md` has `## Intent`, `## Scope`, `## Approach` sections | warn |
   | `facts.md` exists, has Branch + Identifiers sections | warn — fixable |
   | `tasks.md` exists | warn — fixable (empty scaffold) |
   | `specs/` dir exists (may be empty) | warn — fixable (mkdir) |
   | `{name}-notes.md` exists (empty allowed) | warn — fixable |

   ### Frontmatter

   For every `.md` and `.yaml` artifact under `features/{name}/` (and JSON for
   `meta.json`):

   | Check | Severity |
   |---|---|
   | Has frontmatter / top-level keys (per ws-rules) | warn — fixable |
   | `type:` present and in v1 taxonomy | error |
   | `feature:` matches folder name | error |
   | `status:` is one of `draft|ready|done|blocked|stale` | error |

   ### Delta-spec content

   For each `features/{name}/specs/{domain}/spec.md`:

   | Check | Severity |
   |---|---|
   | Has exactly the headings `## ADDED Requirements`, `## MODIFIED Requirements`, `## REMOVED Requirements` (any may be empty) | warn |
   | Each `### Requirement:` has at least one `#### Scenario:` block | warn |
   | Each scenario has `GIVEN`, `WHEN`, `THEN` lines | info |

   ### Cross-file

   | Check | Severity |
   |---|---|
   | `meta.json.status` matches `features.json[{name}].status` | error |
   | Feature row exists in `features/_index.md` | warn — fixable |

3. **Report findings.**

   ```
   feature: {name}

     [ok]    structural checks 7/7
     [warn]  proposal.md missing — legacy spec.md found (run with --fix)
     [error] meta.json.status (in_progress) != features.json (complete)
     [info]  workflow/spec.md scenario "Idle timeout" missing WHEN line

   Exit code: {0 clean | 1 warnings | 2 errors}
   ```

4. **If `--fix` was passed, apply auto-repairs (additive, never content-touching):**

   In order:

   1. Run `~/dev/giant-tooling/workspace/scripts/migrate_spec_to_proposal.py --feature {name}` if a legacy `spec.md` is present without a sibling `proposal.md`.
   2. Run `~/dev/giant-tooling/workspace/scripts/backfill_frontmatter.py` (scoped to this feature dir via cwd) to stamp any missing frontmatter.
   3. Scaffold missing structural files:
      - `tasks.md` → empty header + frontmatter
      - `specs/` → mkdir
      - `{name}-notes.md` → touch
   4. Add missing `features/_index.md` row.
   5. Resync `meta.json.status` ↔ `features.json[{name}].status` — prefer `features.json` as authority. Print diff before writing.
   6. Run `giantmem artifact reindex`.

   Report what was repaired. Re-run validation after fixes and report new status.

## Rules

- NEVER touch user-written content. `--fix` only writes structural files / frontmatter / index rows.
- Adversarial test: run `--fix` on a feature whose `proposal.md` body has hand-written prose. Verify the body is byte-identical after fix.
- Fail fast on `error`-severity checks before any fix attempt unless `--fix` is exactly the thing that resolves the error (e.g., missing frontmatter).
- Do not invent Requirements, scenarios, or task entries. Empty templates only.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | clean (or `--fix` resolved everything) |
| 1 | warnings only (non-blocking) |
| 2 | errors (blocking — `--fix` could not resolve, or no `--fix` passed) |
