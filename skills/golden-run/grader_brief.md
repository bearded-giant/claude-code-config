# Grader brief: golden batch <BATCH_ID>

You grade churn-investigator runs. Each run answers a golden question whose reference is the case's `expected_answer` and `notes` in `<REPO>/eval/golden.yaml` (match by `question_id` = case id, else by the question text under `variants`); an earlier grade of the same question may sit in `<AGAINST_DIR>/grades/<question_id>.json`. You give an independent read using the FULL run data. No code edits. Read-only.

## Files (absolute paths)

- Rows: `<BATCH_DIR>/index.csv` (one row per run: run_id, question_id, store_id, question, outcome, headline, answer markdown and the usage columns). Load with python csv; pick your question ids.
- Run document: `<BATCH_DIR>/<run_id>.full.json` (reading = intake; plan with set-asides; signal; checks[] with verdict, evidence, queries carrying sql and rows; facts; attribution; conclusion; answer.markdown; stages; thresholds; usage). 100-400 KB: extract with python, never Read whole.
- Repo (read-only, for root-cause pointers): `<REPO>`. `investigator/PLAYBOOK.md` (intake/plan/compose rules, 126 lines, read it once), `investigator/run.py` (2083 lines, grep), `investigator/steps.py` (thresholds: MIN_PRIOR_CHURN=25, Z_ANOMALY=3, MIN_ABS_EXCESS=3, MIN_HISTORY_DAYS=14), `investigator/dates.py` (window rules), `investigator/answer.py` (compose + reasons_block), `investigator/packs/recharge_churn_v5.md` (150 KB: grep `^## ` for the check names only). The intake flag `asks_reasons` triggers the `cancellation_reasons` exploration step and a `### Reasons shoppers gave` table in answer.markdown.

## Per row

1. Grade three criteria, each 0-2, over the FULL answer.markdown (not the headline): answered the question? conclusion correct against the reference? evidence captured and correct? Give `prior_score` (from the earlier grade file or the case's `notes`, else null) and `my_score` with one line each.
2. Verify the reference's decisive claims (expected_answer) against the run's own numbers: facts, checks[].evidence, signal, window in setup.reading, query row counts/errors in checks[].queries and exploration.queries. Mark each `confirmed`, `contradicted`, or `not_checkable_from_run`. Keep to the 2-5 claims that decide the grade.
3. Primary failure class, one of: `export_gap` (the answer had it, the surface the reader used did not), `intake_type` (question_type/metric wrong, e.g. a reasons or report ask typed unclear/drift), `window` (wrong days, freshness gap hid the event), `stop_short` (no_anomaly/insufficient_data/weak_signal/needs_clarification with no description of the level, split, or reasons), `missing_check` (pack has no check for it: payment errors, 6-month cohort retention, product-filtered churn, order-count cohorts), `drift_thin` (drift path answered with 2 checks and no breakdown), `compose` (data was in the run, the answer left it out or said it wrong), `packless_partial` (best_fit path answered but incomplete), `correct` (nothing to fix), `analyst_wrong` (the reference answer does not hold against the run's own data). Secondary class optional.
4. Where in the run the wanted answer sat, if anywhere: check id, fact id, query name, or exploration lookup; or "not queried".
5. Fix: one line, with the code area (playbook intake rules, dates.py, steps.py thresholds, run.py routing, answer.py compose, pack section, export csv).
6. Severity for the merchant if shipped as is: `wrong` (misleads), `thin` (true but useless), `fine`.

## Output

Write one JSON per row to `<BATCH_DIR>/grades/<question_id>.json`:

{"qid","run_id","store","question","outcome","question_type","window":{"start","end","mode"},"prior_score","my_score":{"answered":0-2,"correct":0-2,"evidence":0-2,"total"},"agree":true|false,"why":"<=3 sentences","claims":[{"claim","verdict","detail"}],"class","class2","answer_sat_in","fix","code_area","severity","markdown_had_reasons_table":bool,"notes"}

Return to the lead ONLY one line per row, nothing else:
`question_id | prior N/6 -> mine M/6 | class[/class2] | severity | why (<=20 words)`
