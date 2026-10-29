---
name: golden-run
description: Replay a CSV of golden churn questions against an investigator-v2 deployment, pull every run's complete document, grade each run with a per-row opus subagent (answered, correct, evidence, failure class), diff against an earlier batch, and write the report into the active feature. Auto-fires when the user says "run the goldens", "golden run", "replay the batch", "rerun the 31", "grade this batch", "compare batch X with Y", or invokes /golden-run <questions.csv|batch_id> [--against <batch_id>] [--base-url <url>] [--no-run]. Manual analyst loop, not the judge or evals pages.
---

One loop for the lone engineer: run, pull, grade, diff, report. The repo side is `scripts/golden_batch.py` in investigator-v2 (`make golden-run`, `golden-pull`, `golden-diff`); this skill drives it and does the grading the script cannot.

## Inputs

- `<questions.csv>`: `question, store_id, question_id` (the 31-row analyst set lives at `eval/golden.yaml` cases `R3_*`; `scripts/golden_batch.py questions` is not a thing: keep a CSV beside the feature in `filebox/`).
- or `<batch_id>`: skip the run, pull and grade an existing batch (`--no-run` is the same thing with a CSV present).
- `--against <batch_id>`: the earlier batch to diff against (pull it too when its directory is missing).
- `--base-url`: default production `https://investigator-v2.vercel.app`; preview needs `VERCEL_AUTOMATION_BYPASS_SECRET` in `.env.resolved`.
- Reference answers: the golden case's `expected_answer` and `notes` in `eval/golden.yaml` when the question matches a case; else none (grade on the run alone).

## Steps

1. Env: `make env` in the worktree (needs `vault login`); `INVESTIGATOR_SERVICE_TOKEN` must resolve. Never export values into the shell; the script reads `.env.resolved`.
2. Run (skip with a batch id): `make golden-run QUESTIONS=<csv> BATCH=<id>`; batch id `g_<yyyymmdd>_<short tag>`. Exit 1 means a row failed: rerun only the failed question ids with the same batch id (the script tags runs, the runs list groups them).
3. Pull: `make golden-pull BATCH=<id>` into `golden-runs/<id>/` (`index.csv` + `<run_id>.full.json`). Pull `--against` the same way.
4. Grade: write the grader brief from `grader_brief.md` (this dir) with the batch directory and the golden file filled in, then one `general-purpose` subagent on `opus` per 4 rows, each writing `golden-runs/<id>/grades/<question_id>.json` and returning one line per row. Never grade in the lead; never read a `full.json` whole in the lead (100-400 KB each).
5. Diff: `make golden-diff A=golden-runs/<against> B=golden-runs/<id>` and, when both batches have `grades/`, a grade diff per question id (his or prior total out of 6 against the new total).
6. Report: `research/<tag>_golden_run.md` in the active feature (frontmatter, caveman): scorecard (PASS 5-6, PARTIAL 3-4, FAIL 0-2 by total), failure classes with counts, per-row table (`qid | outcome a -> b | grade a -> b | class | one line`), the five worst rows with the fix each needs, cost and wall time, then the doit items for fixes that are not one-session work (`claude:` items on the feature's list, no `daily` twin). Merge the per-row JSONs into `filebox/<tag>_golden_rows.json`.

## Failure classes

`export_gap`, `intake_type`, `window`, `stop_short`, `missing_check`, `drift_thin`, `compose`, `packless_partial`, `correct`, `analyst_wrong`. Defined in `grader_brief.md`; add a class only when a row fits none, and say so in the report.

## Guards

- Production runs cost about $0.45 each and 30-50 s; say the total before a run over 40 rows.
- A batch id is immutable once runs carry it: a rerun gets a new id.
- Artifacts for the team come from a vault note via `claude-artifact`, never from the report file.
