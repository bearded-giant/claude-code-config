#!/usr/bin/env bash
set -euo pipefail

KAI_LIVE="${KAI_LIVE_DIR:-$HOME/dev/ai/kai-live}"
SRC="$KAI_LIVE/plugins/kai"
OUT="$(cd "$(dirname "$0")/.." && pwd)/kai-local/plugins/kai"

# allowlist so new upstream skills stay out until added; dapr-*, chronoctl, stackdriver-promql are called by review-code and chronosphere-expert
SKILLS=(
  open-mr glab accept-kai-feedback gitlab-inline-comments
  review-code review-code-select review-adversarial classify-repo
  dapr-parallel-deploy dapr-pubsub dapr-pubsub-debugging dapr-recharge-foundations dapr-grpc-resilience
  chronoctl stackdriver-promql update-kai
)
AGENTS=(code-reviewer chronosphere-expert backend-engineer incident-investigator)
MCPS=(watchtower dba-mcp-prod dba-mcp-stage atlassian)

[ -d "$SRC/skills" ] || { echo "kai source missing: $SRC" >&2; exit 1; }

rm -rf "${OUT:?}"
mkdir -p "$OUT/skills" "$OUT/agents" "$OUT/.claude-plugin"

shopt -s dotglob
for e in "$SRC"/*; do
  case "$(basename "$e")" in
    skills | agents | .claude-plugin) ;;
    references) cp -R "$e" "$OUT/" ;;
    *) echo "warn: upstream top-level not copied: $(basename "$e")" >&2 ;;
  esac
done

for s in "${SKILLS[@]}"; do
  if [ -d "$SRC/skills/$s" ]; then cp -R "$SRC/skills/$s" "$OUT/skills/"; else echo "warn: skill not upstream: $s" >&2; fi
done
for a in "${AGENTS[@]}"; do
  if [ -f "$SRC/agents/$a.md" ]; then cp "$SRC/agents/$a.md" "$OUT/agents/"; else echo "warn: agent not upstream: $a" >&2; fi
done
# upstream pins model: claude-opus, which the API 404s; bare aliases resolve
sed -i '' -E 's/^model: claude-(opus|sonnet|haiku)$/model: \1/' "$OUT"/agents/*.md

python3 - "$SRC/.claude-plugin/plugin.json" "$OUT/.claude-plugin/plugin.json" "${MCPS[@]}" <<'PY'
import json
import sys

src, dst, keep = sys.argv[1], sys.argv[2], set(sys.argv[3:])
plugin = json.load(open(src, encoding="utf-8"))
servers = plugin.get("mcpServers", {})
missing = keep - set(servers)
if missing:
    print(f"warn: mcp not upstream: {' '.join(sorted(missing))}", file=sys.stderr)
plugin["mcpServers"] = {k: v for k, v in servers.items() if k in keep}
with open(dst, "w", encoding="utf-8") as fh:
    json.dump(plugin, fh, indent=2)
PY

total=$(find "$SRC/skills" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
echo "kai-local: ${#SKILLS[@]}/$total skills, ${#AGENTS[@]} agents, ${#MCPS[@]} mcps from $KAI_LIVE@$(git -C "$KAI_LIVE" rev-parse --short HEAD)"

# install copies into the plugin cache and `plugin update` skips same-version refreshes, so reinstall
claude plugin uninstall kai@kai-local >/dev/null 2>&1 || true
claude plugin install kai@kai-local >/dev/null
echo "kai-local: reinstalled into plugin cache (restart claude sessions to load)"
