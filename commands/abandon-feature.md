---
description: "Abandon a feature: mark abandoned, skip spec merge, archive it (docs stay in live.db)"
argument-hint: "[feature-name] [--reason=...] [--no-archive]"
---

For a feature that got framed and is not getting built. NOT the same as complete — no delta-spec merge, so nothing leaks into a source-spec.

```bash
python3 ~/dev/giant-tooling/workspace/scripts/feature.py abandon [feature] \
  [--reason "scope died"] [--no-archive] --cwd "$(pwd)"
```

Works from any status except `archived`/`abandoned`. Name required unless there's exactly one in_progress feature. The CLI:
- stamps `status: abandoned` + `abandoned: <date>` + `lifecycle: deprecated` on proposal.md, appends `## Abandoned` with the reason
- flips status across meta.json/features.json, drops the `_index.md` row
- skips the delta-spec merge entirely
- reindexes, then chains `giantmem feature archive {feature}` — verifies every file is in live.db, removes the dir, sets status=archived (`--no-archive` keeps the dir)

Artifacts are left untouched on the way out; `live_docs` rows stay searchable via `giantmem find`, MCP, and the GUI.

Ask the user for a `--reason` if they didn't give one — it's the only record of why the feature died. Do not offer to salvage or re-scope the feature unless they ask.
