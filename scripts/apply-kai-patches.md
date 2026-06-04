# apply-kai-patches.sh

Reapply local patches over the kai plugin clone at `~/dev/ai/kai` after any upstream change.

## Why this exists

kai is a directory-sourced Claude plugin updated via `git pull origin master`. Editing kai files in place blocks future pulls (dirty tree). Patches kept in this repo (`kai-patches/*.patch`) let local overrides survive every upstream update.

Override targets so far:
- `plugins/kai/skills/review-code/SKILL.md` — terse output style block injected near top
- `plugins/kai-review/skills/review-code/SKILL.md` — same file (hardlink, inode `333988286`)
- `plugins/kai/skills/review-adversarial/SKILL.md` — same terse style block

## Usage

```bash
~/dev/claude-code-config/scripts/apply-kai-patches.sh
```

No arguments. Exits 0 on clean apply or all-skipped. Exits non-zero if any patch fails to apply (upstream drift — see below).

Override default kai path:
```bash
KAI_DIR=/custom/path/to/kai ~/dev/claude-code-config/scripts/apply-kai-patches.sh
```

## When it runs automatically

Git hooks in `~/dev/ai/kai/.git/hooks/` invoke this script after working-tree changes:

| Event | Hook |
|---|---|
| `git pull` (merge / fast-forward) | `post-merge` |
| `git pull --rebase` | `post-rewrite` (symlink → post-merge) |
| `git checkout <branch>` | `post-checkout` (symlink → post-merge) |
| `git fetch` only | none — no files changed, nothing to reapply |
| `git reset --hard` | none — git design choice. Run script manually. |

Hooks live in `.git/hooks/` which is NOT tracked by git. On a fresh clone of kai, rewire them:

```bash
cd ~/dev/ai/kai/.git/hooks
cat > post-merge <<'EOF'
#!/usr/bin/env bash
exec "$HOME/dev/claude-code-config/scripts/apply-kai-patches.sh"
EOF
chmod +x post-merge
ln -sf post-merge post-rewrite
ln -sf post-merge post-checkout
```

## Behavior

For each `*.patch` in `kai-patches/` (alphabetical):

1. `git apply --reverse --check` → if patch already applied, **skip**.
2. `git apply --check` → if clean, **apply**.
3. Neither → **fail loud**, report file, exit non-zero. Means upstream rewrote the lines this patch anchors on.

Summary line at end: `N applied, N skipped, N failed`.

## Conflict resolution

When upstream drift breaks a patch:

1. Open the failing patch file. Note target paths and context lines.
2. Inspect new upstream content: `git -C ~/dev/ai/kai log -p -- <target>`.
3. Edit the target file in place to express your override on top of the new upstream.
4. Regenerate the patch:
   ```bash
   cd ~/dev/ai/kai
   git diff plugins/<...>/SKILL.md > ~/dev/claude-code-config/kai-patches/<NNNN>-<name>.patch
   git checkout -- plugins/<...>/SKILL.md
   ```
5. Rerun the script. Should report `+ applied`.

## Wrapper command

`/kai-update` in `commands/kai-update.md` chains kai's own `update-kai` skill with this script. Use it instead of bare `git pull` when you want a single command.

## Files

- Script: `scripts/apply-kai-patches.sh`
- Patches: `kai-patches/*.patch` (see `kai-patches/README.md` for patch authoring workflow)
- Command: `commands/kai-update.md`
- Hooks: `~/dev/ai/kai/.git/hooks/post-merge` (+ symlinks)
