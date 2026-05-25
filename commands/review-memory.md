# Review Memory

Walk `lifecycle: candidate` artifacts and decide each: promote to durable, demote to deprecated, or skip.

## Arguments

- scope: (optional) restrict to artifacts in one scope id
- repo: (optional) "current" (default), "all", or a repo name
- limit: (optional) max candidates to walk this session (default 20)

## Steps

1. **Find candidates**

   Run:

   ```bash
   giantmem artifact list --repo {repo|current} --scope {scope|''} --lifecycle candidate --json
   ```

   Pass `--scope` only when the user supplied one. Empty arg = no scope filter.

   If the result list is empty: report "no candidates to review" and stop.

2. **Walk each candidate**

   For each artifact in the list (capped at `limit`):

   1. Print:
      ```
      [<i>/<n>] <id>
        type: <type>   updated: <updated>   lifecycle: candidate
        path: <abs_path>
      ```
   2. Print the first ~200 characters of the body (skip frontmatter).
   3. Ask the user:
      ```
      (a)pprove -> durable | (r)eject -> deprecated | (s)kip | (q)uit
      ```
   4. Apply the decision:
      - **a**: rewrite frontmatter `lifecycle: candidate` -> `lifecycle: durable` and bump `updated: <today>`.
      - **r**: rewrite `lifecycle: candidate` -> `lifecycle: deprecated` and bump `updated: <today>`.
      - **s**: leave file untouched.
      - **q**: stop immediately.
   5. After every approve/reject, run `giantmem artifact reindex` so `artifacts.json` reflects the new state. Use a single trailing reindex if walking many — bunch the reindex calls to one per repo at the end.

3. **Frontmatter edit rules**

   - The file MUST already have a YAML frontmatter block (`---` fenced). If not, report and skip (do NOT add one — that's the backfill script's job).
   - Replace exactly the `lifecycle:` value line. Do NOT reformat other keys.
   - If `updated:` exists, replace its value with today's date (`YYYY-MM-DD`). If missing, do not add one.

4. **Report at end**

   ```
   reviewed: <n>
     approved:   <count>
     rejected:   <count>
     skipped:    <count>
   reindex: ran for <repo_count> repo(s)
   ```

## Rules

- Only edit `lifecycle:` and `updated:` — leave the rest of the artifact alone.
- Never delete the candidate file — rejection = `lifecycle: deprecated`. The user can run a future prune command to remove deprecated files explicitly.
- If the user passes `--scope`, validate it exists via `giantmem scope show <id>` first.
- This is a read-then-edit flow: every edit is preceded by a Read of the file.
