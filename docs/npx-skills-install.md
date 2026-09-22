# npx skills + stow

`npx skills` (vercel-labs/skills) installs Agent Skills for ~20 agents. Two modes. Only one plays with stow.

Stow layout that matters: `~/.claude` is the stow target, `~/.claude/skills` is a symlink to `~/dev/claude-code-config/skills`. Anything landing in the repo's `skills/` is live immediately, no re-stow.

## TL;DR

| Want | Run |
|---|---|
| Skills for one project only | `npx skills add <repo> --skill '*' --agent claude-code --yes` from project root |
| Skills everywhere (stow-backed) | local install into scratch dir, then `cp -R` into `claude-code-config/skills/`, commit |
| `--global` | never on this box. Breaks. See below |

## Local mode (safe)

```bash
npx skills add langchain-ai/langsmith-skills --skill '*' --agent claude-code --yes
```

Writes real files to `./.claude/skills/<name>/`, prints `(copied)`, drops a `skills-lock.json` in cwd. No symlinks. No `~/.agents`.

## Global mode (broken under stow)

```bash
npx skills add <repo> --skill '*' --yes --global    # DO NOT
```

What it does:

1. Writes real files to `~/.agents/skills/<name>/`
2. Symlinks each agent's skill dir at it, relative: `../../.agents/skills/<name>`
3. For Claude Code that link is meant to sit at `~/.claude/skills/<name>`, where `../../` = `~`

Why it breaks: `~/.claude/skills` is itself a symlink into the stow source. The link physically lands in `~/dev/claude-code-config/skills/`, so `../../` resolves to `~/dev`, not `~`. `/Users/bryan/dev/.agents` does not exist. Every link dangles.

Installer prints green checks anyway. It never follows its own links. Symptom is silent: skills do not load, no error.

## Stow-winning install (the "global" replacement)

```bash
cd $(mktemp -d)
npx skills add <repo> --skill '*' --agent claude-code --yes
cp -R .claude/skills/* ~/dev/claude-code-config/skills/
cd ~/dev/claude-code-config && git add skills/ && git commit -m "add skills"
```

Real files in the stow source. Tracked in git. Other machines get them from `git pull`, no npx needed. Live in `~/.claude/skills` through the existing stow symlink.

## Repair after an accidental `--global`

```bash
cd ~/dev/claude-code-config/skills
for s in <names>; do [ -L "$s" ] && rm "$s"; cp -R "$HOME/.agents/skills/$s" "$s"; done
```

Verify no dangling links left anywhere in the skills dir:

```bash
find ~/dev/claude-code-config/skills -maxdepth 1 -type l -exec test ! -e {} \; -print
```

Empty output = clean.

## Notes

- `~/.agents/skills/` is the shared store for the other agents (Codex, Cursor, Gemini CLI, OpenCode, Amp). Deleting it only affects those, not the vendored copies.
- `Failed to install → PromptScript: PromptScript does not support global skill installation` is that one agent refusing global installs. Harmless unless you use PromptScript.
- Claude Code reads skills at boot. New skills need a session restart unless the harness picks them up mid-session.
