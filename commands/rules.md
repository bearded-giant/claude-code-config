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
- No superfluous comments (only crucial/complex logic)
- All comments lowercase
- No docstrings unless requested
- No emojis

## Git
- Short casual commit messages only
- Confirm before pushing

## Active Feature Reload

Check `.giantmem/features/features.json` for the active feature (status `in_progress`). If one exists:

1. Read `features/{name}/spec.md` -- re-familiarize with acceptance criteria
2. Read `features/{name}/facts.md` -- reload beta flags, config keys, test commands
3. Check `features/{name}/plans/current.md` for session work in progress
4. All feature-scoped output (plans, research, reviews, filebox) goes inside `features/{name}/`

Report the active feature name and a one-line summary of what it is. If no feature is active, say so.

Acknowledge these rules are now active.
