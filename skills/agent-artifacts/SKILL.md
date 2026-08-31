---
name: agent-artifacts
description: "Durable per-agent artifact contract for multi-agent runs (Workflow tool, Agent fan-outs). Auto-fires when user says 'with artifacts', 'save the agent outputs', 'artifact this run', 'artifacts on', or asks to review what agents produced in a prior run. Also fires when authoring any ad-hoc Workflow script IF the user asked for reviewable output. Swarm commands (/swarm, /swarm-exec) apply this by default; 'no artifacts' / --no-artifacts opts out."
---

# Agent artifacts

Stock Agent/Workflow results live in the run return + transcript — invisible on disk, gone on compaction. This contract makes any multi-agent run reviewable after the fact. Opt-in per run, except swarm commands where it is opt-out.

## When it applies

| Signal | Behavior |
|---|---|
| User says "with artifacts" / "artifacts on" / "save agent outputs" | Apply to the run being set up |
| `/swarm`, `/swarm-exec` | On by default; `--no-artifacts` skips |
| User says "no artifacts" | Skip, even for swarm |
| Nothing said, ad-hoc fan-out | No artifacts — do not create dirs speculatively |

## Contract

1. **Run dir**, created by the main session BEFORE spawning (workflow scripts have no fs access):
   - Active feature → `.giantmem/features/{name}/swarm/{YYYYMMDD-HHMMSS}-{slug}/`
   - Else research-shaped → `.giantmem/research/swarm/{YYYYMMDD-HHMMSS}-{slug}/`
   - Else exec-shaped → `.giantmem/swarm/{YYYYMMDD-HHMMSS}-{slug}/`
2. **Per-agent capture, by the agent itself.** Append to every worker prompt:
   > AFTER composing your report, use the Write tool to save it verbatim to {runDir}/{role}-{id}.json (pretty-printed). Then return the same content.
   Agent writes mid-run = survives orchestrator compaction and dead runs. Naming: `worker-{aspect}.json`, `validator-{n}.json`, `fix-{round}-{unit}.json`, rounds suffixed `-r{n}`.
3. **Manifest + human-readable synthesis**, written by the main session after the run returns:
   - `README.md` — file table (name → description), config line (models, phases, iteration count)
   - `analysis.md` (or `review.md` / `qa_report.md` by shape) — verdict, findings, recommendations
   - Both caveman-compressed with YAML frontmatter: `type: research|review`, `status: complete`, `feature:` or `repo:`, `lifecycle: candidate`
4. **Workflow tool runs**: journal + persisted script already exist under the session dir — the README manifest SHOULD link the script path and runId from the tool result, so a run can be resumed or re-read (`journal.jsonl` has raw agent returns).
5. After writing, `giantmem artifact reindex` if the run dir is under `.giantmem/`.

## What NOT to do

- No artifacts for single-agent delegations (one Explore/debugger call) — transcript is enough.
- No dumping raw transcripts; the JSON report the agent composed is the artifact.
- Never write outside `.giantmem/` (no repo `docs/`, no `/tmp`).
