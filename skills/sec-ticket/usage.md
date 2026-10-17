# sec-ticket usage

Research a security or bug ticket against the code, write the review as a vault note, then implement the fix from that note once you approve it.

## Commands

| command | does |
|---|---|
| `/sec-ticket PE-1526` | review one ticket; repo inferred from the ticket |
| `/sec-ticket PE-1526 PE-1527 --repo cc` | review several, repo pinned by its `config/repos.csv` alias |
| `/sec-ticket <jira url> ...` | same, with ticket URLs |
| `/sec-ticket PE-1526 --status ready` | approve the fix (or `blocked`, `wont_fix`) |
| `/sec-ticket PE-1526 --fix` | implement the fix from the note |
| `/sec-ticket --fix --status ready` | implement every approved note |
| `/sec-ticket --queue [status]` | list notes grouped by status |
| `/sec-ticket --sweep` | close tickets whose MRs all merged |

Plain phrases work too: "research PE-1526", "approve PE-1526", "implement PE-1526", "security queue".

## Typical flow

1. Review: `/sec-ticket PE-1526`. The note lands at `areas/security/<repo>/PE-1526-<slug>.md` with `status: new`, and the doit list `security-tickets` gets one item for the ticket. Chat shows the gates and a scores row.
2. Read the note's Summary and Gates. Answer any `[BLOCKING]` question in it.
3. Triage: `/sec-ticket PE-1526 --status ready` to approve, or `blocked` / `wont_fix`.
4. Fix: `/sec-ticket PE-1526 --fix`. It branches `PE-1526-<slug>` off each repo's base, writes failing tests, applies the change, and commits with `[PE-1526]` at the start of the subject. It stops before push.
5. Ship: say "ship it". The MR title carries the key, so Jira links it. Once every repo in the note has an open MR, the note moves to `in_review`.
6. Sweep: `/sec-ticket --sweep` after the MRs merge. The note moves to `done` and its doit item closes.

## Status

| status | set by | next |
|---|---|---|
| `new` | review | you triage |
| `ready` | you | fix run |
| `blocked` | you | you |
| `in_progress` | fix run | ship it |
| `in_review` | after ship it | sweep |
| `done` | sweep | none |
| `wont_fix` | you | none |

## What it never does

It never pushes or opens an MR without "ship it", never comments on Jira, HackerOne, or Slack, and never writes to a database. Review mode never edits the repo.
