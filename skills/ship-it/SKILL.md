---
name: ship-it
description: >-
  End-to-end ship chain — commit + push + write MR description + open MR; on GitLab with `glmon-jirad` enabled it also creates or syncs the Jira ticket; in Greptile repos also triggers a re-review on an existing MR; starts `/loop 5m /babysit <worktree>` on every GitLab MR and every GitHub PR in the orgs skio-org / RechargePayments. Returns description and MR URL. Auto-fires when user says "ship it", "ship this", "ship the branch", "ship and open MR", or invokes /ship-it. MR description format is remote-keyed (GitLab→concise-kai: kai headers at compressed caveman density; GitHub skio-org / RechargePayments→Skio four-header format; other GitHub→personal bullets); override with "brief"/"short"/"--brief" (bullets) or "full"/"standard"/"--full" (verbose org kai template). Runs every step in order with no re-confirmation between. Skip if on base branch (main/master/stage).
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
3. **Grill gate** (skip if invocation contains `--no-grill`):
   - Check `git diff --stat <base>...HEAD`. Gate triggers when ANY: ≥300 changed lines, ≥10 files, or diff touches migrations / data-emitting scripts (converters, generators, mutation builders, exporters) / prod-batch tooling.
   - Triggered → look for grill `final.md` for this branch (feature grill dir per `grill` skill routing) newer than HEAD commit.
   - Found + rating SHIP IT → proceed, note `grill: SHIP IT (runs N)` in chat.
   - Found + rating BLOCK/NEEDS WORK → STOP, report rating + final.md path. User decides.
   - Not found / stale → AskUserQuestion ONCE: run `/grill` first (recommended) or ship without. Autonomous mode (`commands/auto.md`) → run `/grill` without asking. Small/simple diffs never trigger — no gate friction on routine ships.

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

GitHub twin (repos.csv note says `github twin`, remote `github` exists): also `git push github <current-branch>`.

- If push is rejected (non-fast-forward, hook rejection, auth): STOP the chain. Report exact error. Do NOT force-push. Do NOT retry destructively.

### Step 3 — Write MR description

Two formats exist. Pick ONE deterministically, generate it, write it to disk. This step is the ONLY MR-description generator in the chain — Step 4 consumes the file, never regenerates.

**Format selection (first match wins):**

1. Brief opt-in — invocation contains `brief`, `short`, or `--brief` → **personal bullet format**.
2. Full opt-in — invocation contains `full`, `standard`, or `--full` → **verbose org kai format** (the full kai template, escape hatch for high-risk MRs).
3. Default by MR-target remote host (the same remote Step 4 opens against — `git remote get-url origin`):
   - `gitlab.rechargeapps.net` / any GitLab → **concise-kai format** (kai section headers, compressed density)
   - `github.com`, org `skio-org` or `RechargePayments` (first path segment of the remote, case-insensitive) → **Skio format**
   - any other `github.com` → **personal bullet format** (your own repos default to your bullets)

**Personal bullet format:** generate the description per `bullet-format.md` (in this skill dir) — bullet style, 3–7 bullets, curl/section rules it specifies. Write it to `mr-description.md` at the routing below (active feature dir → `.giantmem/` → repo root) and print the path. Apply the caveman post-processing that file specifies: tighten phrasing, drop filler, KEEP bullet structure (do NOT convert bullets to prose).

**Skio format (work GitHub default):** generate the description per `skio-format.md` (in this skill dir): `## Why`, `## Scope`, `## Blast Radius`, `## Verification`, normal prose and bullets, no caveman pass. Write it to `mr-description.md` at the same routing and print the path.

**Concise-kai format (GitLab default):** generate the description per `concise-kai-format.md` (in this skill dir) — kai's exact section headers (`## Description`, `## Impacted Areas in Application`, `## Related Issues`, `## Post Deploy Monitoring`, `## How to QA`, `## Post Deploy Action`, `## Risk Assessment`; headers sourced from `kai:open-mr` Step 7, do not duplicate here) at the compressed density that file specifies: minimum signal per section, caveman prose, code identifiers preserved exactly. Write it to `mr-description.md` at the same routing and print the path.

**Verbose org kai format (`--full`/`standard` only):** generate the description using the full team template — the exact structure AND paragraph-level density from `kai:open-mr` Step 7 (source of truth, do not duplicate/paraphrase it here). Write it to `mr-description.md` at the same routing and print the path. Do NOT caveman this format — it is the normative team template; keep it verbatim.

Either branch ends with a description file on disk and its path printed.

**Paired MRs (any format):** when the change spans repos (frontend + customcheckout, remi + monolith) or depends on another open MR, the description opens with an H1 naming every partner and the deploy order, then one line on what breaks or degrades between the two deploys: `# Pairs with frontend!17058 + frontend!17062: frontend ships first, this deploys after`. The pairing never lives only in `## Related Issues` or `## Post Deploy Action`. A partner opened later gets the same H1 on every MR in the set (update the earlier ones). Ask the user for the deploy order when it is not obvious; never assume backend first.

Base-branch resolution: read `mr_base_branch:` from project CLAUDE.md. If absent, ask the user ONCE — this and the grill gate are the only acceptable interruptions in the chain. Persist their answer back into project CLAUDE.md as `mr_base_branch: <branch>` so this never asks again.

### Step 4 — Open MR

Pick the host based on remote:
- `gitlab.rechargeapps.net` or other GitLab → invoke `kai:open-mr` skill, passing the step-3 description file as the MR body (`--description "$(cat <path-from-step-3>)"`) and `mr_base_branch` as the target. `kai:open-mr` MUST use this supplied description and MUST NOT regenerate from its own Step 7 default template — Step 3 already chose the format.
- `github.com` → `gh pr create --base <mr_base_branch> --head <current-branch> --title "<subject>" --body-file <path-from-step-3>`

Title: use the most recent commit subject (or the branch's primary commit subject if multi-commit). Do NOT prefix with "MR:" or "PR:".

Paired MRs: open the one that deploys later as Draft (`glab mr create --draft`, `gh pr create --draft`), so it cannot merge before its partner ships. A customcheckout MR in a pair opens as Draft. The user marks it ready.

If the MR/PR already exists for this branch: skip creation, capture the existing URL.

GitHub twin: also open the GitHub PR (`gh pr create -R <owner/repo from the github remote> --base <mr_base_branch> --head <current-branch> --title "<subject>" --body-file <path-from-step-3>`) for Greptile and the preview; it auto-closes as merged once `main` is pushed to `github`. Then, only when the repos.csv note also says `merge: github`: `gh pr merge <n> -R <owner/repo> --auto --squash` and skip the GitLab MR (GitHub is the merge path there; GitLab `main` follows by mirror). Without that note the GitLab MR stays the merge path and the PR is never armed: a GitHub merge would fork `main`, since GitLab `main` takes pushes only from "Gitlab Integrations".

### Step 4a — Jira ticket (GitLab only; skip on GitHub)

Skip when `glmon-jirad` is not on PATH or `glmon-jirad --status` prints `enabled=False`.

1. Write `jira-summary.md` to the session scratchpad (never the repo, so no stray untracked file): at most 3 bullets on what the MR is for, plain sentences a non-engineer can read. No code, identifiers, file paths, routes, or implementation detail. Normal prose, not caveman.
2. Run `glmon-jirad --mr <mr-url> --summary-file <path>`. It creates a ticket in `jira.project` when the title carries no real key (a `PE-0000` placeholder is replaced in place), writes the key into the MR title, and syncs status. Excluded namespaces and already-keyed MRs are handled inside it, and it is idempotent, so an existing MR is safe.
3. A non-zero exit or error never stops the chain. Keep its last log line (`<project>:<iid>: ticket PE-N, <outcome>`, or the skip / error line) for step 5. It may wait up to 90s for a running poller tick to finish.

### Step 4b — Review handoff (GitLab, and GitHub orgs skio-org / RechargePayments; skip on personal GitHub)

1. Greptile repo (`.greptile/` or `greptile.json` at root, or a note by `greptile` on this MR; GitHub: `<!-- greptile_summary -->` in the PR body. Org-level enablement reviews repos with no config), MR existed before this run (step 4 skipped creation), and step 2 pushed → invoke the `greptile` skill **review** mode; ship-it is the authorization. New MR → nothing; Greptile reviews on open and auto re-review is off.
2. Every GitLab MR and every skio-org / RechargePayments PR: no `CronList` job whose prompt is `/babysit <worktree path>` (`git rev-parse --show-toplevel`) → invoke the `loop` skill with `5m /babysit <worktree path>`. A new MR has no Greptile note yet, so a config-less repo cannot be told apart here; babysit detects Greptile from the summary note and stops its own loop at READY or BLOCKED.

### Step 5 — Final output

Print to chat in EXACTLY this order, nothing else:

1. The full MR description markdown (so user sees what was posted)
2. One blank line
3. The MR URL on its own line
4. Only when step 4a ran: `glmon-jirad`'s last log line (created / retitled / skip / error)

Then STOP. Do NOT add a closing summary. Do NOT offer next steps. Do NOT explain what happened — the description and URL are the report.

In autonomous mode, STOP ends this chain only; continue with the next piece in scope.

Inside a longer turn (several branches shipped, doc or doit work after): the turn's final message still ends with every MR URL, one per line as `<repo>!N <url>`, after all other output. `hooks/created_links_gate.py` opens new MRs in the browser; don't `open` them yourself.

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
ship it  →  grill gate (big/data-heavy diffs only; --no-grill skips) → commit (caveman) → push -u → MR desc (GitLab→concise-kai / skio-org+RechargePayments GitHub→skio / other GitHub→bullets; `brief`=bullets, `full`=verbose kai) → kai:open-mr (or gh pr create; github twin: both, `--auto --squash` only with `merge: github`) → GitLab + glmon-jirad enabled: `glmon-jirad --mr` (Jira ticket) → greptile repos: `@greptile review` (GitHub `@greptileai review`) if MR existed; every GitLab MR and skio-org/RechargePayments PR: `/loop 5m /babysit <worktree>` → print desc + URL
```
