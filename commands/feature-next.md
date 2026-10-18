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

3. MRs / PRs: the current branch, every MR/PR URL in the feature dir, and every MR/PR this repo's Claude sessions opened or touched on any repo, since features span repos (a terraform MR opened from an auth worktree only shows up in the third source).

   ```bash
   grep -rhoE 'https://[^ )>"`]+/(merge_requests|pull)/[0-9]+' .giantmem/features/<name>/ | sort -u
   ```

   ```bash
   giantmem mr list --project "$(basename -s .git "$(git remote get-url origin)")" --json
   ```

   - GitLab origin: `glab mr list --source-branch "$(git branch --show-current)"`, and per URL `glab mr view <iid> -R <group/project>`
   - GitHub origin: `gh pr list --head "$(git branch --show-current)" --state open`, and per URL `gh pr view <url>`

   Pull the state (draft / open / merged / closed), the pipeline result, and the unresolved thread count.

4. Feature docs: unchecked items in `tasks.md`. Also the handoff (`features/<name>/handoff.md`, then `.giantmem/handoff.md`) when it is `status: ready`: its `Open edges` feed Blocked and its `Start here` feeds Next. A ready handoff older than the branch's last commit is listed as stale (workspace-rules `## Handoff`).

## Output

Fixed order, blockers first. One line per item, with identifiers exact (`recharge-auth!43`, doit `#12`). MR refs always carry the repo, since repos share ids. Omit empty sections. No sources at all → say so in one line.

```
<feature or repo>  branch: <branch>

Blocked / needs decision
- ...
In flight
- recharge-auth!43  open, pipeline green, 2 unresolved threads
Next: user
1. ...
Next: claude
1. ...
Done
- ...
Artifacts
<feature.py next output, verbatim>
```

- Next leads with the doit item that is `in_progress` (the active one a prior turn or session left), under its owner. Then it merges the doit order (`N.` prefix, priority bucket) with MR state. Owed items (`owed in daily #M`) and an MR waiting on review or merge are user items; name the `daily #M` handle. A failing pipeline or an unresolved thread claude can fix is a claude item.
- Done covers merged MRs and completed doit items for this feature. Cap it at 5.
- When sources disagree (tasks.md says done but the MR is open, or a doit item is open for a merged MR), list it under Blocked as stale and name both sources. Don't fix it. After the report, offer `/doit-prune` in one batched AskUserQuestion.
