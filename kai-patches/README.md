# kai-patches

Local patches over the kai plugin clone at `~/dev/ai/kai`. kai is a directory-sourced plugin updated via `git pull origin master` (see kai's `update-kai` skill). Editing files in place would block future pulls; patches let edits survive updates as portable diffs.

## Layout

```
kai-patches/
  0001-<short-name>.patch
  0002-<short-name>.patch
  ...
```

Numbered prefix controls apply order. Use `git format-patch` style.

## Workflow

1. Edit kai file in place inside `~/dev/ai/kai`.
2. Stage + diff: `cd ~/dev/ai/kai && git diff > ~/dev/claude-code-config/kai-patches/0001-<name>.patch`.
3. Revert the in-place edit: `cd ~/dev/ai/kai && git checkout -- <file>`.
4. Reapply via `~/dev/claude-code-config/scripts/apply-kai-patches.sh`.
5. Restart claude session.

## After kai update

`update-kai` skill runs `git pull origin master`. Run `apply-kai-patches.sh` immediately after. Script detects:

- already-applied → skip
- clean apply → apply
- conflict → report and exit non-zero (manual rebase needed)

## Conflict resolution

Upstream changed the patched file. Re-derive the patch:

1. Inspect upstream change: `git -C ~/dev/ai/kai log -p -- <file>`
2. Edit file in place to express your override on top of new upstream
3. Regenerate patch via step 2 of Workflow

## Caveats

- Patch paths are relative to kai repo root (`plugins/kai/skills/...`).
- Don't patch `.claude-plugin/plugin.json` version strings — kai may reset them.
- Restart the claude session after applying; skills/commands cache.
