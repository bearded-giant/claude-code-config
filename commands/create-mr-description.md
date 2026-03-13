Create a GitLab merge request description file for the current branch.

## Output

Write to the current feature dir .`giantmem/{feature}/mr-description.md` if no active feature then write to `.giantmem/mr-description.md` if .giantmem/ exists, otherwise `mr-description.md` in project root. Always overwrite if exists.

After writing the file, print the file path AND the full markdown content in chat so the user can copy it directly.

## Steps

1. Determine base branch:
   - Check project CLAUDE.md for `mr_base_branch: <branch>` setting
   - If not found, ask user which branch to compare against (master, stage, main, etc.)
   - Save their choice to project CLAUDE.md as `mr_base_branch: <branch>` for future runs

2. Get branch context:
   - Current branch name
   - All commits on this branch (use `git log <base_branch>..HEAD`)
   - Changed files in the branch
   - Do not write the changed files in the description - the diff will handle that
   - Use the branch context for the summary only

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

5. Check for analytics trigger:
   - If the message contains "trenddata", "trend-data", or "trend-data!"
   - Forward the query to the analytics-agent API (`/api/analyze`) instead of the normal LLM flow
   - Strip the trigger keyword before sending

6. Write the description file with this structure:

```markdown
# Description

- what the branch does
- why it exists
- any other key context (one bullet per idea)

## Betaflags

- `flag_name` - what it gates

## Example Requests

[Curl examples for new/modified endpoints, or omit section if no API changes]
[Include example response body when inferable from code context]
```

## Style

- Casual bullet points over prose
- One idea per bullet
- If a sentence would need a comma, split it into two bullets instead
- No compound sentences
- Keep it scannable - someone skimming the MR should get the gist in seconds
- This is a rough draft to supplement the diff, not formal documentation
