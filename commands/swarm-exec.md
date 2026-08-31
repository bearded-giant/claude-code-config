---
description: "Execution swarm via the swarm-exec workflow: plan -> parallel implementers -> validator + tests. Never commits. Artifacts on by default (--no-artifacts to skip)."
argument-hint: "[--no-artifacts] [--test-cmd=...] <plan file path or inline plan>"
---

Run the `swarm-exec` saved workflow. User invoking this command IS the multi-agent opt-in.

## Safety gates (before invoking the workflow)

1. `git status` — if dirty, STOP and ask user to commit or stash.
2. Record current branch, then `git checkout -b swarm-exec/{YYYYMMDD-HHMMSS}`.
3. Never commit, push, or merge — user reviews and commits. Rollback is always: checkout original branch, delete the swarm-exec branch.

## Steps

1. Parse `$ARGUMENTS`: `--no-artifacts`, `--test-cmd=...`, rest = plan (file path preferred: feature `proposal.md`/`tasks.md` or `.giantmem/plans/*.md`; inline description accepted).
2. Run dir (skip when artifacts=false):
   - Plan from a feature dir → `.giantmem/features/{name}/swarm/{YYYYMMDD-HHMMSS}-exec/`
   - Else → `.giantmem/swarm/{YYYYMMDD-HHMMSS}-exec/`
   - `mkdir -p`.
3. Invoke `Workflow` with `name: "swarm-exec"`, args:
   ```json
   { "plan": "<path or text>", "runDir": "<run dir>", "artifacts": true,
     "timestamp": "<YYYYMMDD-HHMMSS>", "testCmd": "<optional>" }
   ```
4. Background — wait for the task notification, read returned `{verdict, tests_passed, files_changed, issues, fix_rounds}`.
5. If artifacts on, write `README.md` manifest to the run dir (caveman, frontmatter `type: review`, `status: complete`, `feature:` or `repo:`, `lifecycle: candidate`): file table + verdict + branch name. If a feature plan, also write/update `.giantmem/features/{name}/qa_report.md` — acceptance criteria table (criterion | PASS/FAIL | evidence) from the delta-spec.
6. Report: verdict, tests, files changed, branch name, run dir, and the commit-or-rollback choice. Do NOT commit.
