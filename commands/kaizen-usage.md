---
description: "Usage guide for /kaizen and /kaizen-review commands"
---

# Kaizen Command Usage

Two commands for generating and iterating on Kaizen User/Web/DB design docs.

## Setup

Set the templates env var in your shell config:

```bash
export KAIZEN_TEMPLATES_DIR=~/dev/docs_and_designs/templates
```

Both commands will refuse to run without it.

## /kaizen -- Generate a doc

```
/kaizen [codebase_path] [--docs=path1,path2] "<problem statement>" [--type=feature|fix|refactor] [--light] [--split]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `codebase_path` | no | Project root. Triggers codebase exploration to ground the doc in real code. |
| `--docs=path1,path2` | no | Comma-separated paths to plans, specs, PRDs, prior kaizen docs. Fed into generation. |
| `"problem statement"` | yes | Quoted description of what you're solving. |
| `--type=feature\|fix\|refactor` | no | Controls User/Web/DB section structure. Asked interactively if omitted. |
| `--light` | no | Fewer scenarios, skip edge cases, compact sections. |
| `--split` | no | Separate docs per concern instead of one unified doc. |

**Output:** `scratch/filebox/kaizen_{slug}.md`

### Examples

Greenfield, no codebase:
```
/kaizen "merchants need a way to bulk-edit subscription frequencies" --type=feature
```

With codebase exploration:
```
/kaizen ~/dev/python/cc-wt/flask-session "session records accumulate in Redis causing logout loops" --type=fix
```

With input docs:
```
/kaizen ~/dev/python/cc-wt/flask-session --docs=scratch/research/session_analysis.md,scratch/features/redis-sessions/spec.md "consolidate session storage to latest-only" --type=refactor
```

Light doc for a small change:
```
/kaizen ~/dev/python/cc-wt/flask-session "add session expiry TTL" --type=feature --light
```

## /kaizen-review -- Iterate on a doc

```
/kaizen-review <doc_path> [codebase_path] "<what to change>"
```

| Argument | Required | Description |
|----------|----------|-------------|
| `doc_path` | yes | Path to existing kaizen doc. |
| `codebase_path` | no | Project root, for grounding new content in code. |
| `"what to change"` | yes | Quoted description of the revision. |

### Examples

Lighten a heavy doc:
```
/kaizen-review scratch/filebox/kaizen_session_storage.md "too many scenarios, cut the edge cases and tighten the prose"
```

Add missing scenarios:
```
/kaizen-review scratch/filebox/kaizen_session_storage.md ~/dev/python/cc-wt/flask-session "add scenarios for admin user bypass and OAuth token refresh"
```

Apply peer review feedback:
```
/kaizen-review scratch/filebox/kaizen_session_storage.md "reviewers flagged: missing rollback strategy for the migration, and the redis key format doesn't match what's in production"
```

Split a large doc:
```
/kaizen-review scratch/filebox/kaizen_session_storage.md "split into separate docs for the redis migration and the JWT cookie work"
```

## Getting the most out of /kaizen

### 1. Front-load your problem statement

The problem statement is the single biggest lever on output quality. A vague one-liner produces a generic doc. A few sentences with specific pain points, user types, and system names produces something reviewable.

Bad: `"fix sessions"`

Good: `"merchants get logged out when reopening the app because session records accumulate in Redis -- the session_id changes on every OAuth callback and the old sessions aren't cleaned up, so the lookup returns stale data"`

### 2. Pass existing docs with --docs

If you've already done discovery, have a PRD, or wrote a prior kaizen doc that's related, pass it in. The command reads these and pulls key points, data models, and scope boundaries directly into the generated doc. This prevents the LLM from re-inventing context you already have.

### 3. Point at the codebase

Without a codebase path, you get a reasonable design doc with invented names. With one, you get actual table names, column types, endpoint paths, and response shapes from the code. The doc becomes verifiable against the implementation.

If you know which directories matter most, say so when the command asks about key files -- this focuses the exploration and avoids wasting budget on irrelevant code.

### 4. Use --type to control structure

The doc type changes how the User/Web/DB section is organized:

- **feature** -- scenarios grouped by user flow (create, read, update, delete)
- **fix** -- three-part structure: how it works today, what's broken, the fix. Reviewers can evaluate each layer independently.
- **refactor** -- current vs target architecture. Good for migration designs.

If you pick the wrong type, `/kaizen-review` can restructure it after the fact.

### 5. Iterate with /kaizen-review, don't regenerate

The first pass won't be perfect. Use `/kaizen-review` to tighten, expand, or restructure. It preserves what's already good and only touches what you ask it to change. Faster and more predictable than re-running `/kaizen` from scratch.

### 6. Use --light for small changes

Not every design needs 12 scenarios. `--light` produces a compact doc that covers the happy path and key variations without exhaustive edge case coverage. Good for small features, bug fixes, or when the team already has strong context.

### 7. Answer the interactive questions well

When the command asks about known decisions, exemptions, and scope boundaries, give specific answers. These go directly into the Background and Key Points sections -- the parts reviewers read first. Saying "Recharge admins are exempt because they auth via Google OAuth" saves a round of review feedback.

$ARGUMENTS
