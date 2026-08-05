---
name: mr-comment-volume
description: >-
  Given a GitLab MR URL, count code lines vs comment lines in the MR diff
  (added lines only) and report totals plus comment percentage. Auto-fires
  when user says "comment volume", "comment ratio of this MR", "how many
  comment lines in this MR", "code vs comment lines in the diff", or invokes
  /mr-comment-volume. Skip for whole-file comment counts (use cloc on files).
argument-hint: "<gitlab-mr-url>"
---
<!-- caveman:compressed -->

Count code vs comment lines in a GitLab MR **diff** — added lines only (new content the MR introduces). Removed/context lines excluded. Output: total code, total comment, comment %, blank count, per-language breakdown.

## Run

```bash
python3 ~/.claude/skills/mr-comment-volume/scripts/mr_comment_volume.py "<MR_URL>"
```

URL form: `https://<host>/<group>/<project>/-/merge_requests/<iid>`. Script parses host+path+iid, fetches diff via `glab mr diff <iid> -R <repo-url> --raw`, classifies each added line. Needs `glab` authed for that host.

## Output

```
code lines / comment lines / comment %  (blank excluded from %)
by language: <ext> code N comment M P%
files changed: N
```

`comment % = comment / (code + comment)`. Blank lines excluded from the %.

## Rules (SLOC-standard)

- Comment line = stripped line **starts with** a comment token (`#`, `//`, `--`, `;`, `/* */`, `<!-- -->`, Python `""" """`). Trailing comments (`x=1  // note`) count as **code**.
- Block comments track open/close state within a file's added lines only.
- Ceiling: added lines lack full-file context — a `+` line inside a pre-existing block comment reads as code. Diff-only counting can't see that. Good enough for change-level ratio, not exact.

## Self-check

```bash
python3 ~/.claude/skills/mr-comment-volume/scripts/mr_comment_volume.py --self-check
```
