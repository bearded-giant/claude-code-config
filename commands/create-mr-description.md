---
description: Create a GitLab merge request description (Summary / Test plan / etc.) for the current branch. Writes to active feature dir, .giantmem/, or repo root. Auto-fires when user says "draft MR description", "write up an MR", "ready for MR", "create MR description", or after a successful `git push -u origin <feature-branch>` when on a non-base branch. Skip if branch is base (main/master/stage).
---

Create a GitLab merge request description file for the current branch.

## Output

Write to the current feature dir .`giantmem/{feature}/mr-description.md` if no active feature then write to `.giantmem/mr-description.md` if .giantmem/ exists, otherwise `mr-description.md` in project root. Always overwrite if exists.

After writing the file, print the full markdown content in chat, then the file path on its own line at the end so it's easy to copy.

## Steps

1. Determine base branch:
   - Check project CLAUDE.md for `mr_base_branch: <branch>` setting
   - If not found, ask user which branch to compare against (master, stage, main, etc.)
   - Save their choice to project CLAUDE.md as `mr_base_branch: <branch>` for future runs

2. Get branch context:
   - Current branch name
   - All commits on this branch (use `git log <base_branch>..HEAD`)
   - Read the diff for understanding, but the description is a conceptual overview, not a text diff
   - Do not list changed files — the MR diff handles that
   - Do not include test files or test changes in the description
   - Do not reference specific code (file paths, function names, variable names) unless critical to understanding the change

3. Scan for betaflags (ONLY in branch diff, not whole codebase):
   - Run `git diff <base_branch>..HEAD` to get the actual diff content
   - Search the diff output for added lines (`+`) containing `BetaService` imports or `is_enabled(` calls
   - Do NOT grep the entire codebase - only check what's in the diff
   - Note which betaflags were added (the string passed to is_enabled)
   - If no betaflags, omit the Betaflags section entirely

4. Identify API endpoints:
   - Look for new/modified Flask routes in the changes
   - Generate curl examples using `api.rechargeapps.com` as base URL
   - Include example response bodies from context when possible (read route handlers, serializers, or tests to infer response shape)

5. Write the description file with this structure:

```markdown
# description

- what the branch does
- why it exists
- any other key context (one bullet per idea)

## betaflags

- `flag_name` - what it gates

## example requests

[Curl examples for new/modified endpoints, or omit section if no API changes]
[Include example response body when inferable from code context]
```

## Style

- Ultra-concise bullet points over prose
- One idea per bullet
- If a sentence would need a comma, split it into two bullets instead
- No compound sentences
- Keep it scannable - someone skimming the MR should get the gist in seconds
- This is a rough draft to supplement the diff, not formal documentation
- Bullet lists start with lower case letters
- No periods at the end of a bullet point
- Conceptual overview only — describe what changed and why, not how the code implements it
- No code references (file paths, function names, class names) unless critical for reviewer context

## Post-Processing

After writing the description, run it through caveman compression: tighten phrasing, drop filler words, keep all technical substance.
