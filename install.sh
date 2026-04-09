#!/bin/bash
# install.sh -- set up claude-code-config and its dependencies
# usage: ./install.sh [--clone-dir ~/dev]
set -euo pipefail

CLONE_DIR="${1:-$HOME/dev}"
CONFIG_REPO="git@gitlab.rechargeapps.net:bryan.grimes/claude-code-config.git"
TOOLING_REPO="https://github.com/bearded-giant/giant-tooling.git"
CONFIG_DIR="$CLONE_DIR/claude-code-config"
TOOLING_DIR="$CLONE_DIR/giant-tooling"

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
dim()   { printf '\033[0;90m%s\033[0m\n' "$*"; }

# -- prereqs ------------------------------------------------------------------

check_prereq() {
    if ! command -v "$1" &>/dev/null; then
        red "missing: $1 -- $2"
        return 1
    fi
    dim "  ok: $1"
}

echo "checking prerequisites..."
fail=0
check_prereq git       "install git"                           || fail=1
check_prereq stow      "brew install stow / apt install stow"  || fail=1
check_prereq python3   "install python 3.10+"                  || fail=1
check_prereq fzf       "brew install fzf (optional, for interactive search)" || true
check_prereq bat       "brew install bat (optional, for search previews)"    || true

if [ "$fail" -eq 1 ]; then
    red "\nfix the missing prerequisites above, then re-run."
    exit 1
fi
echo ""

# -- clone repos ---------------------------------------------------------------

clone_if_missing() {
    local url="$1" dir="$2" name="$3"
    if [ -d "$dir" ]; then
        dim "  exists: $dir"
    else
        echo "  cloning $name..."
        git clone "$url" "$dir"
        green "  cloned: $dir"
    fi
}

echo "setting up repos in $CLONE_DIR..."
mkdir -p "$CLONE_DIR"
clone_if_missing "$CONFIG_REPO"  "$CONFIG_DIR"  "claude-code-config"
clone_if_missing "$TOOLING_REPO" "$TOOLING_DIR" "giant-tooling"
echo ""

# -- symlink giant-tooling into config -----------------------------------------

echo "wiring dependencies..."
mkdir -p "$CONFIG_DIR/lib"

if [ -L "$CONFIG_DIR/lib/workspace" ]; then
    dim "  symlink exists: lib/workspace -> giant-tooling/workspace"
elif [ -d "$CONFIG_DIR/lib/workspace" ]; then
    echo "  replacing copied lib/workspace with symlink..."
    rm -rf "$CONFIG_DIR/lib/workspace"
    ln -s "$TOOLING_DIR/workspace" "$CONFIG_DIR/lib/workspace"
    green "  linked: lib/workspace -> $TOOLING_DIR/workspace"
else
    ln -s "$TOOLING_DIR/workspace" "$CONFIG_DIR/lib/workspace"
    green "  linked: lib/workspace -> $TOOLING_DIR/workspace"
fi
echo ""

# -- stow into ~/.claude -------------------------------------------------------

echo "running stow..."
if [ -d "$HOME/.claude" ] && [ ! -L "$HOME/.claude" ]; then
    red "  ~/.claude exists and is a real directory (not a symlink)."
    red "  back it up and remove it, then re-run:"
    red "    mv ~/.claude ~/.claude.bak"
    exit 1
fi

# stow from the parent of the config dir, targeting home
stow_parent="$(dirname "$CONFIG_DIR")"
stow_pkg="$(basename "$CONFIG_DIR")"

cd "$stow_parent"
stow --restow -t "$HOME/.claude" "$stow_pkg" 2>&1 | grep -v "^$" || true
green "  stowed: $CONFIG_DIR -> ~/.claude"
echo ""

# -- shell env -----------------------------------------------------------------

echo "checking shell environment..."
shell_rc="$HOME/.bashrc"
[ -f "$HOME/.zshrc" ] && shell_rc="$HOME/.zshrc"

needs_env=0
if ! grep -q "GIANT_TOOLING_DIR" "$shell_rc" 2>/dev/null; then
    needs_env=1
fi

if [ "$needs_env" -eq 1 ]; then
    echo ""
    echo "add these to your $shell_rc:"
    echo ""
    echo "  export GIANT_TOOLING_DIR=\"\$HOME/dev/giant-tooling\""
    echo "  source \"\$GIANT_TOOLING_DIR/workspace/workspace-lib.sh\""
    echo ""
    echo "  # search aliases"
    echo "  alias gmq='\$GIANT_TOOLING_DIR/giantmem-archive/giantmem-search.py'"
    echo "  alias giantmem-archive='\$GIANT_TOOLING_DIR/giantmem-archive/giantmem-archive.sh'"
    echo "  alias domains='\$GIANT_TOOLING_DIR/domain-search/domains'"
    echo ""
else
    dim "  GIANT_TOOLING_DIR already in $shell_rc"
fi

# -- initial index build -------------------------------------------------------

echo "building search index..."
if python3 "$TOOLING_DIR/giantmem-archive/giantmem-search.py" ingest --sessions-only 2>/dev/null; then
    green "  sessions indexed"
else
    dim "  skipped session indexing (no sessions yet, that's fine)"
fi

# -- verify --------------------------------------------------------------------

echo ""
echo "verifying..."
ok=0
[ -f "$HOME/.claude/CLAUDE.md" ]                     && dim "  ok: ~/.claude/CLAUDE.md" || { red "  missing: ~/.claude/CLAUDE.md"; ok=1; }
[ -f "$HOME/.claude/settings.json" ]                  && dim "  ok: ~/.claude/settings.json" || { red "  missing: ~/.claude/settings.json"; ok=1; }
[ -f "$HOME/.claude/lib/workspace/workspace-lib.sh" ] && dim "  ok: ~/.claude/lib/workspace/workspace-lib.sh" || { red "  missing: workspace-lib.sh"; ok=1; }
[ -f "$TOOLING_DIR/giantmem-archive/giantmem-search.py" ] && dim "  ok: giantmem-search.py" || { red "  missing: giantmem-search.py"; ok=1; }

echo ""
if [ "$ok" -eq 0 ]; then
    green "done. restart claude code to pick up the new config."
else
    red "some files are missing -- check the errors above."
fi
