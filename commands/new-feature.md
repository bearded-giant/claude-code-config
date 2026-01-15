Create a new feature folder with templates.

## Arguments

- name: Feature name in kebab-case (e.g., "jwt-session-enforcement")
- builds_on: (optional) Parent feature this depends on

## Steps

1. Validate scratch/features/ exists, if not inform user to run /ws-init
2. Create scratch/features/{name}/ directory
3. Create spec.md:

```markdown
# Feature: {name (title case)}

builds_on: {builds_on or "none"}
status: in_progress
created: {today's date}

## Purpose

<!-- describe what this feature does and why -->

## Scope

<!-- what's included and what's out of scope -->

## Key Decisions

<!-- architectural decisions made, with rationale -->

## Acceptance Criteria

- [ ] criterion 1
- [ ] criterion 2

## Files Modified

<!-- list key files created/modified -->
```

4. Create facts.md:

```markdown
# {name} facts

## Identifiers

beta_flag:
config_keys:
  -

## Endpoints

affected:
  -
new:
  -

## Key Files

-

## Test Commands

```bash
# add test commands here
```
```

5. Create meta.json:

```json
{
  "name": "{name}",
  "status": "in_progress",
  "builds_on": ["{builds_on}"],
  "beta_flag": "",
  "created": "{today's date}",
  "last_session": "{today's date}"
}
```

6. Update scratch/features/_index.md:
   - Add new row to the Active Features table
   - Format: `| [{name}]({name}/) | in_progress | | {builds_on or "-"} |`

7. Display the created structure and remind user to fill in the templates
