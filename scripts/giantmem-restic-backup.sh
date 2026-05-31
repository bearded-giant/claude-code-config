#!/usr/bin/env bash
# giantmem-restic-backup.sh -- snapshot the giantmem memory backbone to the VPS.
#
# Backs up the durable sources (harness memory md + session transcripts) and the
# giantmem sqlite index to a restic repo over sftp on the Tailscale VPS. Run by
# launchd (com.bryan.giantmem-restic) on a timer; also runnable by hand.
#
# Restore: RESTIC_REPOSITORY/RESTIC_PASSWORD_COMMAND as below, then
#   restic snapshots ; restic restore latest --target /some/dir
# The sqlite DBs are rebuildable from the sources via `giantmem ingest`.
set -euo pipefail

export RESTIC_REPOSITORY="${RESTIC_REPOSITORY:-sftp:bryan@claude-vps:/home/bryan/giantmem-restic}"
export RESTIC_PASSWORD_COMMAND="${RESTIC_PASSWORD_COMMAND:-/usr/bin/security find-generic-password -a bryan -s giantmem-restic -w}"

RESTIC="$(command -v restic || true)"
[ -x "$RESTIC" ] || RESTIC=/opt/homebrew/bin/restic

LOG_DIR="$HOME/.cache/giantmem"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/restic-backup.log"

log() { printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$LOG"; }

candidates=(
  "$HOME/giantmem_archive"
  "$HOME/.claude/projects"
)
paths=()
for p in "${candidates[@]}"; do
  [ -e "$p" ] && paths+=("$p")
done
if [ "${#paths[@]}" -eq 0 ]; then
  log "no backup paths present, skipping"
  exit 0
fi

log "backup start -> $RESTIC_REPOSITORY"
if "$RESTIC" backup "${paths[@]}" \
    --tag giantmem \
    --exclude '*.tmp' \
    --exclude '*-shm' \
    >>"$LOG" 2>&1; then
  log "backup ok"
else
  rc=$?
  log "backup FAILED rc=$rc -- if ssh check expired, apply the tailscale 'accept' ACL rule"
  exit "$rc"
fi

if ! "$RESTIC" forget --tag giantmem \
    --keep-last 24 --keep-daily 14 --keep-weekly 8 --keep-monthly 12 \
    --prune >>"$LOG" 2>&1; then
  log "forget/prune warning (non-fatal)"
fi
log "done"
