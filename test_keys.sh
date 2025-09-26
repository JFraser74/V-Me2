#!/usr/bin/env bash
set -euo pipefail

mask_stdin(){
  python - <<'PY'
import sys,re
txt=sys.stdin.read()
pattern=re.compile(r"(sk-[A-Za-z0-9_\-]{4})[A-Za-z0-9_\-]+([A-Za-z0-9_\-]{4})")
print(pattern.sub(r"\1***\2", txt))
PY
}

wait_for_startup(){
  local attempts=0
  while [ $attempts -lt 80 ]; do
    if grep -q "Application startup complete" /tmp/uvicorn.log 2>/dev/null; then
      return 0
    fi
    sleep 0.25
    attempts=$((attempts+1))
  done
  return 1
}

run_test(){
  label="$1"
  key="$2"
  printf "\n===== TEST: %s =====\n" "$label"
  printf "%s\n" "OPENAI_API_KEY=${key}" > .env
  pkill -f uvicorn || true
  sleep 0.3
  nohup uvicorn main:app --reload --host 127.0.0.1 --port 8000 --log-level info > /tmp/uvicorn.log 2>&1 &
  uvpid=$!
  if ! wait_for_startup; then
    echo "[${label}] server did not signal startup within timeout; showing partial log:" >&2
    tail -n 200 /tmp/uvicorn.log | mask_stdin >&2 || true
  fi
  echo "[${label}] POSTing /agent/chat..."
  resp=$(curl -sS -X POST http://127.0.0.1:8000/agent/chat -H 'Content-Type: application/json' -d "{\"message\":\"hello from ${label} test\"}" -w '\nHTTP_STATUS:%{http_code}\n' || true)
  echo "--- RESPONSE (masked) ---"
  printf "%s\n" "$resp" | mask_stdin || true
  echo "--- /tmp/uvicorn.log tail (masked) ---"
  tail -n 200 /tmp/uvicorn.log | mask_stdin || true
  echo "uvicorn pid:$uvpid"
  sleep 0.4
}

KEY1='REDACTED'
KEY2='REDACTED'
KEY3='REDACTED'

# NOTE: Replace the REDACTED placeholders with real keys in a local copy
# if you need to run these tests — never commit real secrets to the repo.
run_test "sk-proj-original" "$KEY1"
run_test "sk-svcacct" "$KEY2"
run_test "sk-proj-new" "$KEY3"
