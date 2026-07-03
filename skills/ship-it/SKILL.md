---
name: ship-it
description: End-to-end ship chain — commit + push + write MR description + open MR. Returns description and MR URL. Auto-fires when user says "ship it", "ship this", "ship the branch", "ship and open MR", or invokes /ship-it. MR description format is remote-keyed (GitLab→org kai template, GitHub→personal bullets); override with "brief"/"short"/"--brief" (bullets) or "full"/"standard"/"--full" (org template). Runs every step in order with no re-confirmation between. Skip if on base branch (main/master/stage).
---

# ship-it

Single end-to-end chain. Execute every step in order. No intermediate confirmation. No "should I continue?" prompts. The user invoking `ship it` IS the consent for the whole chain.

This skill exists because the chain was previously a one-line rule in CLAUDE.md and Opus would skip steps or stall mid-chain. Treat each step below as MUST-DO unless its skip condition fires.

## Preconditions (check before step 1)

1. Current branch MUST NOT be `main`, `master`, or `stage`. If it is, STOP and tell user to switch to a feature branch first.
2. Determine state:
   - `git status --porcelain` non-empty → there are local changes to commit
   - `git log @{u}..HEAD` non-empty (or no upstream) → there are unpushed commits
   - Both empty AND upstream exists AND remote MR already open → STOP, report "branch already shipped, MR: <url>"

## Chain (execute in order, no breaks)

### Step 1 — Commit

Skip if `git status --porcelain` is empty (nothing to commit; jump to step 2).

Otherwise:
- Use `caveman:caveman-commit` skill format: Conventional Commits, subject ≤50 chars, body only when "why" is non-obvious.
- NO Claude attribution. NO `Co-Authored-By`. NO `🤖 Generated with...` footer.
- Stage explicit files (not `git add -A`) when safe to enumerate; otherwise stage tracked modifications with `git add -u` plus the specific untracked files you intend to include.
- Use HEREDOC for the message body.
- If pre-commit hook fails: fix the underlying issue, re-stage, create a NEW commit. NEVER `--amend`. NEVER `--no-verify`.

### Step 2 — Push

`git push -u origin <current-branch>`

- If push is rejected (non-fast-forward, hook rejection, auth): STOP the chain. Report exact error. Do NOT force-push. Do NOT retry destructively.

### Step 3 — Write MR description

Two formats exist. Pick ONE deterministically, generate it, write it to disk. This step is the ONLY MR-description generator in the chain — Step 4 consumes the file, never regenerates.

**Format selection (first match wins):**

1. Brief opt-in — invocation contains `brief`, `short`, or `--brief` → **personal bullet format**.
2. Full opt-in — invocation contains `full`, `standard`, or `--full` → **org kai format**.
3. Default by MR-target remote host (the same remote Step 4 opens against — `git remote get-url origin`):
   - `gitlab.rechargeapps.net` / any GitLab → **org kai format** (org repos default to the team template)
   - `github.com` → **personal bullet format** (your own repos default to your bullets)

**Personal bullet format:** invoke the `create-mr-description` command. It writes the markdown per its own routing rules (active feature dir → `.giantmem/` → repo root) and prints the file path. Then apply caveman post-processing per the rules inside `create-mr-description.md`: tighten phrasing, drop filler, KEEP bullet structure (do NOT convert bullets to prose).

**Org kai format:** do NOT invoke `create-mr-description`. Generate the description using the team template — the exact structure from `kai:open-mr` Step 7 (source of truth, do not duplicate/paraphrase it here): `## Description`, `## Impacted Areas in Application`, `## Related Issues`, `## Post Deploy Monitoring`, `## How to QA`, `## Post Deploy Action`, `## Risk Assessment`. Write it to `mr-description.md` at the same routing (active feature dir → `.giantmem/` → repo root) and print the path. Do NOT caveman this format — it is the normative team template; keep it verbatim.

Either branch ends with a description file on disk and its path printed.

Base-branch resolution: read `mr_base_branch:` from project CLAUDE.md. If absent, ask the user ONCE — this is the only acceptable interruption in the chain. Persist their answer back into project CLAUDE.md as `mr_base_branch: <branch>` so this never asks again.

### Step 4 — Open MR

Pick the host based on remote:
- `gitlab.rechargeapps.net` or other GitLab → invoke `kai:open-mr` skill, passing the step-3 description file as the MR body (`--description "$(cat <path-from-step-3>)"`) and `mr_base_branch` as the target. `kai:open-mr` MUST use this supplied description and MUST NOT regenerate from its own Step 7 default template — Step 3 already chose the format.
- `github.com` → `gh pr create --base <mr_base_branch> --head <current-branch> --title "<subject>" --body-file <path-from-step-3>`

Title: use the most recent commit subject (or the branch's primary commit subject if multi-commit). Do NOT prefix with "MR:" or "PR:".

If the MR/PR already exists for this branch: skip creation, capture the existing URL.

### Step 5 — Final output

Print to chat in EXACTLY this order, nothing else:

1. The full MR description markdown (so user sees what was posted)
2. One blank line
3. The MR URL on its own line

Then STOP. Do NOT add a closing summary. Do NOT offer next steps. Do NOT explain what happened — the description and URL are the report.

## Failure handling

Any step fails → STOP the chain immediately. Report:
- which step failed
- the exact error
- what state the branch is in (committed? pushed? MR open?)

Do NOT skip a failed step and continue. Do NOT take destructive recovery actions (force-push, reset --hard, branch -D) without explicit user instruction.

## Anti-patterns (do NOT do these)

- Ask "should I push now?" between commit and push — chain is implicit consent
- Ask "should I open the MR?" after writing the description — keep going
- Rewrite the description in prose form after the bullets were generated
- Add Claude/Anthropic attribution to commit message OR MR body
- Use `git commit --amend` to "fix" a previous commit during the chain
- Use `git push --force` or `--force-with-lease` to recover from a rejection
- Run additional exploratory greps/reads between steps — the chain is mechanical, not investigative
- Print a trailing "✅ Done!" / "Shipped!" / summary block — output ends at the MR URL line

## Quick reference

```
ship it  →  commit (caveman) → push -u → MR desc (GitLab→org kai / GitHub→bullets; `brief`|`full` overrides) → kai:open-mr (or gh pr create) → print desc + URL
```
