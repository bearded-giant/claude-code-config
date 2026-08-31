---
description: "Aspect-parallel analysis swarm via the swarm-analyze workflow. Artifacts on by default (--no-artifacts to skip)."
argument-hint: "[--no-artifacts] [--kind=review|analysis|custom] <task description>"
---

Run the `swarm-analyze` saved workflow. User invoking this command IS the multi-agent opt-in.

## Steps

1. Parse `$ARGUMENTS`:
   - `--no-artifacts` → artifacts=false
   - `--kind=X` → explicit kind; otherwise detect: review/evaluate/assess/audit → `review`; analyze/examine/investigate/architecture → `analysis`; anything else (incl. compare/versus) → `custom`
   - Rest = task description
2. Run dir (skip entirely when artifacts=false):
   - Active feature → `.giantmem/features/{name}/swarm/{YYYYMMDD-HHMMSS}-{slug}/`
   - Else → `.giantmem/research/swarm/{YYYYMMDD-HHMMSS}-{slug}/`
   - `mkdir -p` it. Slug = 2-4 word topic.
3. If the task names a feature, read its `proposal.md` / `facts.md` and pass the relevant parts as `context`.
4. Invoke `Workflow` with `name: "swarm-analyze"`, args:
   ```json
   { "task": "...", "kind": "analysis", "runDir": "<run dir>", "artifacts": true,
     "timestamp": "<YYYYMMDD-HHMMSS>", "context": "<optional>" }
   ```
5. Workflow is background — wait for the task notification, then read the returned `{synthesis, workers, iterations}`.
6. If artifacts on, write to the run dir (both caveman, YAML frontmatter `type: research`, `status: complete`, `feature:` or `repo:`, `lifecycle: candidate`):
   - `analysis.md` — human-readable synthesis: verdict, per-aspect summaries, issues by severity, recommendations
   - `README.md` — manifest table: file → description (worker-*.json, validator-*.json, analysis.md), config line (kind, iterations, aspect list)
7. Report to user: verdict, confidence, top issues, run dir path (or "no artifacts" note).

## Notes

- Worker/validator JSON files are written by the agents themselves mid-run — reviewable even if the run dies partway.
- Re-run/iterate: edit the persisted script path from the tool result, resume with `resumeFromRunId`.
