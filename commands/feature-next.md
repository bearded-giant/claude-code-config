---
description: "Feature or repo status: next ready artifact (artifacts.json + artifact_dag.yaml), doit list, and open MRs merged into one report, with what's next split user vs claude. Read-only. Auto-fires when user asks \"what's next\", \"what's left\", \"what is pending\", \"where are we\", \"where did I leave this\", \"levelset\", or invokes /feature-next."
argument-hint: "[feature-name]"
---

Read-only, informational. Never writes docs, todos, or MRs, and never enforces the DAG. The user can skip any artifact; never push back.

## Gather (independent, run in parallel)

1. Artifacts:

   ```bash
   python3 ~/dev/giant-tooling/workspace/scripts/feature.py --cwd "$(pwd)" next [feature]
   ```

   Feature is inferred from the in_progress one when omitted. Exit 1 with `no active feature` means bare-repo mode: skip this step and the `tasks.md` part of step 4, and keep the rest.

2. doit list: use the name from the SessionStart `doit session list` line. Re-derive only if cwd or feature changed:

   ```bash
   python3 ~/.claude/hooks/doit_session_prime.py --name-only [--feature <name>] --cwd "$(pwd)"
   ```

   Then `list_todos` with `list=<name>` (doit MCP only, never the JSON). A `claude:` prefix marks claude's items; everything else is the user's.

3. MRs / PRs: the current branch plus every MR/PR URL in the feature dir, since features span repos.

   ```bash
   grep -rhoE 'https://[^ )>"`]+/(merge_requests|pull)/[0-9]+' .giantmem/features/<name>/ | sort -u
   ```

   - GitLab origin: `glab mr list --source-branch "$(git branch --show-current)"`, and per URL `glab mr view <iid> -R <group/project>`
   - GitHub origin: `gh pr list --head "$(git branch --show-current)" --state open`, and per URL `gh pr view <url>`

   Pull the state (draft / open / merged / closed), the pipeline result, and the unresolved thread count.

4. Feature docs: unchecked items in `tasks.md`. Also the handoff (`features/<name>/handoff.md`, else `.giantmem/handoff.md`) when it is `status: ready`: its `Open edges` feed Blocked and its `Start here` feeds Next. A ready handoff older than the branch's last commit is listed as stale (workspace-rules `## Handoff`).

## Output

Fixed order, blockers first. One line per item, with identifiers exact (`!43`, doit `#12`). Omit empty sections. No sources at all → say so in one line.

```
<feature or repo>  branch: <branch>

Blocked / needs decision
- ...
In flight
- !43 recharge-auth  open, pipeline green, 2 unresolved threads
Next: user
1. ...
Next: claude
1. ...
Done
- ...
Artifacts
<feature.py next output, verbatim>
```

- Next merges the doit order (`N.` prefix, priority bucket) with MR state. An MR waiting on review or merge is a user item. A failing pipeline or an unresolved thread claude can fix is a claude item.
- Done covers merged MRs and completed doit items for this feature. Cap it at 5.
- When sources disagree (tasks.md says done but the MR is open, or a doit item is open for a merged MR), list it under Blocked as stale and name both sources. Don't fix it. After the report, offer the cleanup in one batched AskUserQuestion.
