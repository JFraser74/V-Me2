#!/usr/bin/env bash
# scripts/smoke_all.sh
# One-click smoke for V-Me2: health, settings GET/PUT+refresh, chat, tool call, tool_events clamp.
# Usage:
#   BASE_URL=https://your-domain ADMIN_TOKEN=your-admin-token ./scripts/smoke_all.sh
# Defaults:
#   BASE_URL=http://127.0.0.1:8000  (local dev)
#   ADMIN_TOKEN='' (settings checks that require admin will be skipped if missing)

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_TOKEN="${ADMIN_TOKEN:-${SETTINGS_ADMIN_TOKEN:-}}"

# --- auto-start local server (optional) ---
START_LOCAL="${START_LOCAL:-0}"
UVICORN_CMD="${UVICORN_CMD:-uvicorn main:app --host 127.0.0.1 --port 8000}"
SERVER_PID=""

cleanup() {
  if [[ -n "${SERVER_PID}" ]]; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

wait_for_health() {
  for i in {1..30}; do
    if curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "[FAIL] health check never went ready at $BASE_URL/health" >&2
  exit 1
}

if [[ "$START_LOCAL" == "1" && "$BASE_URL" =~ ^http://(127\.0\.0\.1|localhost):8000$ ]]; then
  echo "[info] starting local server: $UVICORN_CMD"
  $UVICORN_CMD >/tmp/vme2-uvicorn.log 2>&1 &
  SERVER_PID=$!
  wait_for_health
fi
# --- end auto-start block ---

PASS=0; FAIL=0; WARN=0
# Prefer a workspace-local temp directory to avoid /tmp permission issues in some CI/dev envs
TMPDIR="$PWD/.tmp_smoke_$$"
mkdir -p "$TMPDIR"
chmod 700 "$TMPDIR" || true
trap 'rm -rf "$TMPDIR"' EXIT

# Save option: either SMOKE_SAVE_DIR env or --save <dir> argument
SAVE_DIR="${SMOKE_SAVE_DIR:-}"
if [ "${1:-}" = "--save" ] && [ -n "${2:-}" ]; then
  SAVE_DIR="$2"
  shift 2
fi
if [ -n "$SAVE_DIR" ]; then
  mkdir -p "$SAVE_DIR"
  echo "[info] saving responses to $SAVE_DIR"
fi

save_json() {
  # usage: echo "$BODY" | save_json name
  if [ -z "$SAVE_DIR" ]; then return 0; fi
  local name="$1"; shift
  ts="$(date +%Y%m%d-%H%M%S)"
  path="$SAVE_DIR/${name}_${ts}.json"
  cat >"$path"
  echo "[saved] $path"
}

say()  { printf "\n%s\n" "$*"; }
ok()   { PASS=$((PASS+1)); printf "✅ %s\n" "$*"; }
bad()  { FAIL=$((FAIL+1)); printf "❌ %s\n" "$*"; }
warn() { WARN=$((WARN+1)); printf "⚠️  %s\n" "$*"; }

# curl helper -> writes body to file, prints status to stdout
req() {
  local method="$1"; shift
  local url="$1"; shift
  local out="$1"; shift
  local extra=("$@")
  curl -sS -X "$method" "${extra[@]}" "$url" -o "$out" -w "%{http_code}"
}


# tiny JSON getter via python (no jq dependency)
jget() {
  local key="$1"; local file="$2"
  python3 - "$key" "$file" <<'PY'
import sys, json, pathlib
k, f = sys.argv[1], sys.argv[2]
try:
    with open(f, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    # Flexible: support {"k":...} or nested "items" or array roots
    if isinstance(data, dict):
        if k in data:
            v = data[k]
        elif 'items' in data and isinstance(data['items'], list) and k == 'len':
            v = len(data['items'])
        else:
            v = data.get(k, '')
    elif isinstance(data, list) and k == 'len':
        v = len(data)
    else:
        v = ''
    if isinstance(v, (dict, list)): print(json.dumps(v))
    else: print(v)
except Exception:
    print("")
PY
}

# pretty-print JSON from stdin (fallback to raw)
pp_json () {
  python3 - <<'PY'
import sys, json
try:
    data = json.load(sys.stdin)
    print(json.dumps(data, indent=2, sort_keys=True))
except Exception:
    sys.stdout.write(sys.stdin.read())
PY
}

say "🌐 Base URL: $BASE_URL"
if [[ -n "$ADMIN_TOKEN" ]]; then
  say "🔐 Admin token: provided"
else
  warn "Admin token not set — settings write/refresh checks will be skipped."
fi

# 1) Health
code=$(req GET "$BASE_URL/health" "$TMPDIR/health.txt")
if [[ "$code" == "200" ]] && grep -qi "ok" "$TMPDIR/health.txt"; then
  ok "Health: 200 ok"
else
  bad "Health failed (code=$code, body=$(cat "$TMPDIR/health.txt"))"
fi

# 2) Settings (masked GET, unauthorized GET)
code=$(req GET "$BASE_URL/api/settings" "$TMPDIR/settings_noauth.json")
if [[ "$code" == "401" || "$code" == "403" ]]; then
  ok "Settings GET (no auth): $code (expected deny)"
else
  warn "Settings GET (no auth): got $code (body: $(head -c 200 "$TMPDIR/settings_noauth.json"))"
fi

if [[ -n "$ADMIN_TOKEN" ]]; then
  code=$(req GET "$BASE_URL/api/settings" "$TMPDIR/settings_auth.json" -H "X-Admin-Token: $ADMIN_TOKEN")
  if [[ "$code" == "200" ]]; then
    ok "Settings GET (admin): 200"
  else
    warn "Settings GET (admin): $code (body: $(head -c 200 "$TMPDIR/settings_auth.json"))"
  fi

  # PUT model + refresh
  code=$(req PUT "$BASE_URL/api/settings" "$TMPDIR/settings_put.json" \
          -H "X-Admin-Token: $ADMIN_TOKEN" -H "content-type: application/json" \
          --data '{"OPENAI_MODEL":"gpt-4o-mini"}')
  if [[ "$code" == "200" ]]; then
    ok "Settings PUT: 200"
  else
    warn "Settings PUT: $code (likely Supabase not configured). Body: $(head -c 200 "$TMPDIR/settings_put.json")"
  fi

  code=$(req POST "$BASE_URL/api/settings/refresh" "$TMPDIR/settings_refresh.json" \
          -H "X-Admin-Token: $ADMIN_TOKEN")
  if [[ "$code" == "200" ]]; then
    ok "Settings refresh: 200"
  else
    warn "Settings refresh: $code (body: $(head -c 200 "$TMPDIR/settings_refresh.json"))"
  fi
fi

# 3) Chat (plain)
CHAT_CODE=$(req POST "$BASE_URL/agent/chat" "$TMPDIR/chat_plain.json" \
        -H "content-type: application/json" \
        --data '{"message":"ping","label":"smoke"}')
if [[ "$CHAT_CODE" == "200" ]]; then
  ok "Chat (plain): 200"
else
  bad "Chat (plain): $CHAT_CODE (body:)"; cat "$TMPDIR/chat_plain.json" | pp_json
fi
# extract session id robustly from response body
SID="$(python3 -c 'import sys, json
try:
  d=json.load(open(sys.argv[1]))
  print(d.get("session_id",""))
except Exception:
  print("")' "$TMPDIR/chat_plain.json")"

# 4) Chat (tool ask)
# Chat (tool ask)
CHAT_TOOL_CODE=$(req POST "$BASE_URL/agent/chat" "$TMPDIR/chat_tool.json" \
        -H "content-type: application/json" \
        --data '{"message":"Use the ls tool to list project files and summarize.","label":"smoke"}')
if [[ "$CHAT_TOOL_CODE" == "200" ]]; then
  ok "Chat (tool-ask): 200"
else
  warn "Chat (tool-ask): $CHAT_TOOL_CODE (body:)"; cat "$TMPDIR/chat_tool.json" | pp_json
fi
# prefer new SID if returned
SID_TOOL="$(python3 -c 'import sys, json
try:
  d=json.load(open(sys.argv[1]))
  print(d.get("session_id",""))
except Exception:
  print("")' "$TMPDIR/chat_tool.json")"
if [[ -n "$SID_TOOL" ]]; then SID="$SID_TOOL"; fi

# 5) Tool events (clamp test)
if [[ -n "$SID" ]]; then
  echo "[info] checking /agent/tool_events clamp for session_id=$SID"
  OK=0
  for i in 1 2 3 4 5; do
    TE_CODE=$(curl -sS -o "$TMPDIR/tool_events.json" -w "%{http_code}" "$BASE_URL/agent/tool_events?session_id=${SID}&limit=999" || true)
    if [[ "$TE_CODE" == "200" ]]; then
      # compute count
      CNT=$(python3 - <<'PY'
import sys,json
try:
    d=json.load(open(sys.argv[1]))
    items = d.get('items', d if isinstance(d, list) else [])
    print(len(items))
except Exception:
    print(0)
PY
"$TMPDIR/tool_events.json")
      if [[ "$CNT" -le 50 ]]; then
        ok "Tool events: 200 (count=${CNT}, clamped ≤ 50)"
        OK=1; break
      fi
    fi
    sleep 1
  done
  if [[ "$OK" != "1" ]]; then
    warn "tool_events clamp not confirmed; last body:"; cat "$TMPDIR/tool_events.json" | pp_json
  fi
else
  warn "Tool events: skipped (no session_id; likely Supabase not configured)"
fi

say "----------------------------------------"
printf "PASS: %d   FAIL: %d   WARN: %d\n" "$PASS" "$FAIL" "$WARN"
if [[ "$FAIL" -gt 0 ]]; then exit 1; fi
