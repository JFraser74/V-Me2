#!/usr/bin/env bash
set -euo pipefail

REQ_VARS=(SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY SETTINGS_ADMIN_TOKEN APP_ENCRYPTION_KEY)
OPT_VARS=(OPENAI_MODEL OPENAI_API_KEY AGENT_TOOLS_ENABLED)
BASE_URL_DEFAULT="${BASE_URL:-http://127.0.0.1:8000}"

echo "[preflight] checking required Railway env vars…"
missing=0
for v in "${REQ_VARS[@]}"; do
  if [ -z "${!v:-}" ]; then echo "  - MISSING: $v"; missing=1; else echo "  - ok: $v"; fi
done
echo "[preflight] optional vars:"
for v in "${OPT_VARS[@]}"; do
  if [ -z "${!v:-}" ]; then echo "  - empty (optional): $v"; else echo "  - ok: $v"; fi
done
if [ "$missing" -ne 0 ]; then
  echo "[preflight] ❌ missing required vars. set them in Railway and retry."
  exit 2
fi

echo "[preflight] pinging health @ ${BASE_URL_DEFAULT}/health …"
if curl -fsS "$BASE_URL_DEFAULT/health" >/dev/null; then
  echo "[preflight] ✅ health ok"
else
  echo "[preflight] ⚠️ health not reachable (this is fine if the app isn’t started yet)."
fi

if [ "${RUN_SMOKE:-0}" = "1" ]; then
  echo "[preflight] running smoke_all.sh…"
  chmod +x scripts/smoke_all.sh
  BASE_URL="$BASE_URL_DEFAULT" ADMIN_TOKEN="${SETTINGS_ADMIN_TOKEN}" scripts/smoke_all.sh
fi
