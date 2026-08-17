---
name: review-comment
description: >-
  Turn verified review findings into an MR/PR comment that reads like a human
  reviewer wrote it, show it for approval, then post it. Auto-fires when user
  says "post this as a review comment", "comment this on the MR", "leave review
  comments", "add findings to the MR", or invokes /review-comment. Needs
  findings already in session (run /kai:review-adversarial or /grill first).
  Skip for MR descriptions (use ship-it).
argument-hint: "<mr-or-pr-url> [--post]"
---
<!-- caveman:compressed -->

Findings → one human-voiced comment → user approves → post.

Findings must already exist in session (from `/kai:review-adversarial`, `/grill`, `/review-code`, or manual trace). No findings → say so, point at those skills, stop. Do NOT re-review here.

## Steps

1. **Filter.** Blockers + warnings only. Nits dropped unless user asks for them. Anything you couldn't verify in code stays out — a reviewer who guesses loses credibility.
2. **Draft** per Voice below.
3. **Show draft in chat, fenced, and stop.** Wait for approval. Exception: user said `--post` / "post it" up front → skip straight to 4.
4. **Post** per Posting below. Report the note URL.

## Voice

The review skills emit scaffolding — severity tags, triage summaries, claim tables, citation chains. None of that belongs in a comment. Rewrite, don't paste.

Do:

- Lead each finding with what breaks for a person (merchant can't save, customer gets wrong copy), then the mechanism.
- One paragraph per blocker. Prose, contractions, normal sentences.
- Bullets ONLY for the short tail of smaller items.
- One citation per claim — `file.py:1031`, basename only, no repo path. The chain of five files that proved it stays in your head.
- Name what a reviewer would want to know unasked: why the pipeline is green, whether the MR's own QA steps still hold, blast radius on real stores.
- Close with one line on what IS right. True, and it buys goodwill for the blocker.
- One small code snippet, only when the fix isn't obvious from prose. Zero is usually right.

Don't:

- `**CRITICAL —**` / `**WARNING —**` label runs. Severity comes from "this is a blocker before it goes out", said once.
- Section headers per finding. At most `## Blocking` / `## Non-blocking`, and often neither.
- Tables, verdict matrices, "Applied checks", "Skipped N checks", emojis.
- Restating the MR description back at the author.
- Hedging ("might possibly", "you may want to consider"), or padding ("great work overall!").
- Findings outside the diff's scope unless the diff is wrong without them.

Length: a blocker plus 3-4 smaller items fits in ~25 lines. Over 40 lines means you kept scaffolding.

## Posting

Body to scratchpad file first — inline quoting trips the permission parser.

GitLab:

```bash
glab mr note create <iid> -R <group>/<project> -m "$(cat <body-file>)"
```

GitHub:

```bash
gh pr comment <num> --body-file <body-file>
```

curl fallback when `glab` isn't authed for that host (project path URL-encoded, `/` → `%2F`):

```bash
curl -s -o /dev/null -w "%{http_code}" --request POST \
  "https://<host>/api/v4/projects/<encoded-project>/merge_requests/<iid>/notes" \
  --header "PRIVATE-TOKEN: $GITLAB_TOKEN" --header "Content-Type: application/json" \
  --data @<json-file>
```

201 → confirm with the note URL. Anything else → report the code, no retry.

## Inline threads (optional)

Line-anchored comment when a finding sits on a line the diff actually touches:

```bash
glab mr note create <iid> -R <repo> --file <path> --line <n> -m "..."
```

Ceiling: only works for lines present in the latest diff version. Findings in untouched files — the common case for "the caller you didn't change also breaks" — must go in the main note. Don't split one review across five inline threads; authors read one comment, not a scavenger hunt.
