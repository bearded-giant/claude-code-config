#!/usr/bin/env bash
# Clone every repo in config/repos.csv onto the devbox under the same paths the
# laptop uses (the /Users/bryan bridge makes them resolve there). Worktree
# parents (<base>-wt/.bare) get the giant-tooling layout with the default branch
# checked out as a sibling worktree; plain rows get a plain clone. Idempotent:
# existing targets are skipped.
#
# GitLab clones go over https through a credential helper that reads
# $GITLAB_TOKEN, sourcing ~/dotfiles/.creds.secret when the shell did not, so they
# work in daemon-started sessions and non-interactive ssh with no agent. GitHub clones go over ssh, which needs
# the laptop agent forwarded (Host devbox: ForwardAgent yes) until the devbox
# key is registered on GitHub.
#
# Usage:
#   scripts/devbox-clone-repos.sh [host] [--only <alias>] [--dry-run]

set -euo pipefail

HOST=devbox; ONLY=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --only)    ONLY="$2"; shift 2;;
    --dry-run) DRY=1; shift;;
    -h|--help) sed -n '2,15p' "$0"; exit 0;;
    -*)        echo "unknown flag: $1"; exit 1;;
    *)         HOST="$1"; shift;;
  esac
done

CONFIG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CSV="$CONFIG_DIR/config/repos.csv"
# rows that the bootstrap already rsyncs, or that are not repos of their own
SKIP_ALIASES="dotfiles giantmem giant-tooling doit.nvim kai-live"

to_https() {
  # git@gitlab.rechargeapps.net:group/repo.git -> https://gitlab.rechargeapps.net/group/repo.git
  sed -E 's#^git@([^:]+):#https://\1/#' <<<"$1"
}

MANIFEST=$(mktemp)
trap 'rm -f "$MANIFEST"' EXIT
python3 - "$CSV" <<'PY' > "$MANIFEST.rows"
import csv,sys
seen=set()
for names,path,notes in list(csv.reader(open(sys.argv[1])))[1:]:
    if path in seen: continue
    seen.add(path); print(f"{names.split('|')[0]}\t{path}")
PY
while IFS=$'\t' read -r alias path; do
  [ -n "$ONLY" ] && [ "$alias" != "$ONLY" ] && continue
  case " $SKIP_ALIASES " in *" $alias "*) continue;; esac
  # a row may point at one worktree of a -wt parent; clone the parent layout instead
  [ -f "$path/.git" ] && [ -d "$(dirname "$path")/.bare" ] && path="$(dirname "$path")"
  if [ -d "$path/.bare" ]; then
    layout=wt; g=(git --git-dir "$path/.bare")
  elif [ -e "$path/.git" ]; then
    layout=plain; g=(git -C "$path")
  else
    echo "skip $alias: $path is not a git checkout here"; continue
  fi
  origin=$("${g[@]}" remote get-url origin 2>/dev/null || true)
  [ -n "$origin" ] || { echo "skip $alias: no origin"; continue; }
  case "$origin" in git@gitlab.*) origin=$(to_https "$origin");; esac
  extras=""
  for r in $("${g[@]}" remote); do
    [ "$r" = origin ] && continue
    u=$("${g[@]}" remote get-url "$r"); case "$u" in git@gitlab.*) u=$(to_https "$u");; esac
    extras="$extras $r=$u"
  done
  printf '%s\t%s\t%s\t%s\t%s\n' "$alias" "$path" "$layout" "$origin" "${extras# }" >> "$MANIFEST"
done < "$MANIFEST.rows"
rm -f "$MANIFEST.rows"

echo "==> $(wc -l < "$MANIFEST" | tr -d ' ') repos for $HOST"
if [ "$DRY" = 1 ]; then column -t -s $'\t' "$MANIFEST"; exit 0; fi

scp -q "$MANIFEST" "$HOST:/tmp/devbox-repos.manifest"
ssh "$HOST" 'bash -s' <<'REMOTE'
set -o pipefail
# no set -u here: the sourced alias files reference unset vars
. "$HOME/.claude-devbox.sh" 2>/dev/null || true
echo "==> cloning on $(hostname) as $(id -un)"
# https auth for GitLab from the token already on this box
git config --global credential."https://gitlab.rechargeapps.net".helper '!f() { [ -n "$GITLAB_TOKEN" ] || . "$HOME/dotfiles/.creds.secret"; echo username=oauth2; echo "password=$GITLAB_TOKEN"; }; f'
fail=0
while IFS=$'\t' read -r alias path layout origin extras; do
  if [ "$layout" = wt ]; then
    if [ -d "$path/.bare" ]; then echo "  = $alias (exists)"; continue; fi
    echo "  + $alias  $origin  -> $path/.bare"
    mkdir -p "$path"
    if ! git clone -q --bare "$origin" "$path/.bare"; then echo "    FAIL clone"; fail=1; continue; fi
    git -C "$path/.bare" config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
    git -C "$path/.bare" fetch -q origin
    def=$(git -C "$path/.bare" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
    if [ -z "$def" ]; then for b in main master develop; do git -C "$path/.bare" rev-parse --verify -q "origin/$b" >/dev/null && { def=$b; break; }; done; fi
    [ -n "$def" ] || { echo "    FAIL no default branch"; fail=1; continue; }
    git -C "$path/.bare" update-ref --no-deref HEAD "$(git -C "$path/.bare" rev-parse "origin/$def")"
    git -C "$path/.bare" worktree add -q "$path/$def" "$def" 2>/dev/null || git -C "$path/.bare" worktree add -q "$path/$def" -b "$def" "origin/$def"
    git -C "$path/$def" branch -q --set-upstream-to "origin/$def" "$def" 2>/dev/null || true
    echo "    worktree $path/$def"
    gitdir="$path/.bare"
  else
    if [ -e "$path/.git" ]; then echo "  = $alias (exists)"; continue; fi
    echo "  + $alias  $origin  -> $path"
    mkdir -p "$(dirname "$path")"
    if ! git clone -q "$origin" "$path"; then echo "    FAIL clone"; fail=1; continue; fi
    gitdir="$path/.git"
  fi
  for kv in $extras; do
    git --git-dir "$gitdir" remote add "${kv%%=*}" "${kv#*=}" 2>/dev/null || true
  done
done < /tmp/devbox-repos.manifest
rm -f /tmp/devbox-repos.manifest
exit $fail
REMOTE
