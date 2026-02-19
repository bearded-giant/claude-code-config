Create a GitLab merge request description file for the current branch.

## Output

Write to `.giantmem/mr-description.md` if .giantmem/ exists, otherwise `mr-description.md` in project root. Always overwrite if exists.

## Steps

1. Determine base branch:
   - Check project CLAUDE.md for `mr_base_branch: <branch>` setting
   - If not found, ask user which branch to compare against (master, stage, main, etc.)
   - Save their choice to project CLAUDE.md as `mr_base_branch: <branch>` for future runs

2. Get branch context:
   - Current branch name
   - All commits on this branch (use `git log <base_branch>..HEAD`)
   - Changed files in the branch

3. Scan for betaflags (ONLY in branch diff, not whole codebase):
   - Run `git diff <base_branch>..HEAD` to get the actual diff content
   - Search the diff output for added lines (`+`) containing `BetaService` imports or `is_enabled(` calls
   - Do NOT grep the entire codebase - only check what's in the diff
   - Note which betaflags were added (the string passed to is_enabled)

4. Identify API endpoints:
   - Look for new/modified Flask routes in the changes
   - Generate curl examples using `api.rechargeapps.com` as base URL

5. Write the description file with this structure:

```markdown
# Description

[2-3 sentence casual summary of what this branch does and why]

## Betaflags

[List any betaflags added, or "None" if none found]

## Example Requests

[Curl examples for new/modified endpoints, or omit section if no API changes]
```

## Tone

Keep it casual and brief. This is a rough draft for a merge request, not formal documentation.
