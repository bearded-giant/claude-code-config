---
description: Re-inject key workspace and output rules plus active feature context
---

**REMINDER - Apply these rules for the rest of this session:**

## Document Output
- ALWAYS write docs/plans/research to `.giantmem/` subdirectories
- NEVER output long-form content only in chat
- Plans → `.giantmem/plans/`
- Research/analysis → `.giantmem/research/`
- Context/discoveries → `.giantmem/context/`
- Reviews → `.giantmem/reviews/`

## Code Style
- See `code_comment_rules` in CLAUDE.md (default ZERO comments, lowercase when warranted, no docstrings, no emojis)

## Git
- See `git_rules` in CLAUDE.md. `/commit`, `/commit-push-pr`, "commit and push", "ship it" → no re-confirmation between steps.

## Active Feature Reload

Check `.giantmem/features/features.json` for the active feature (status `in_progress`). If one exists:

1. Read `features/{name}/spec.md` -- re-familiarize with acceptance criteria
2. Read `features/{name}/facts.md` -- reload beta flags, config keys, test commands
3. Check `features/{name}/plans/current.md` for session work in progress
4. All feature-scoped output (plans, research, reviews, filebox) goes inside `features/{name}/`

Report the active feature name and a one-line summary of what it is. If no feature is active, say so.

Acknowledge these rules are now active.
