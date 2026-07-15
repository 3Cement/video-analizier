#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TMP="$(mktemp -d)"
cleanup() {
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID" || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

export DATA_DIR="$TMP/data"
export MEDIA_DIR="$TMP/media"
export DATABASE_URL="sqlite:///$TMP/app.db"
export WORKER_MODE=false
export AUTH_REQUIRED=false
export OPENAI_API_KEY=""
export ANTHROPIC_API_KEY=""
export CURSOR_API_KEY=""
export PYTHONPATH="$ROOT/backend"

mkdir -p "$DATA_DIR" "$MEDIA_DIR"

echo "[smoke-local] starting API..."
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 >/tmp/va-smoke-local.log 2>&1 &
PID=$!

ok=0
for _ in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8010/api/health >/tmp/va-health.json; then
    ok=1
    break
  fi
  sleep 0.5
done
if [[ "$ok" != "1" ]]; then
  echo "[smoke-local] API unhealthy"
  cat /tmp/va-smoke-local.log || true
  exit 1
fi

EMAIL="smoke_$RANDOM@example.com"
curl -sf -c /tmp/va-local-cookies.txt -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"secret123\"}" \
  http://127.0.0.1:8010/api/auth/register >/tmp/va-auth.json
TOKEN=$(python3 -c 'import json;print(json.load(open("/tmp/va-auth.json"))["token"])')

curl -sf -b /tmp/va-local-cookies.txt -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"title":"Smoke note","text":"Protein recovery guidance for local smoke test content.","auto_summarize":false}' \
  http://127.0.0.1:8010/api/sources/text >/tmp/va-source.json
SID=$(python3 -c 'import json;print(json.load(open("/tmp/va-source.json"))["id"])')

final=""
for _ in $(seq 1 40); do
  curl -sf -b /tmp/va-local-cookies.txt -H "Authorization: Bearer $TOKEN" \
    "http://127.0.0.1:8010/api/sources/$SID/status" >/tmp/va-status.json
  final=$(python3 -c 'import json;print(json.load(open("/tmp/va-status.json"))["status"])')
  if [[ "$final" == "ready" || "$final" == "failed" ]]; then
    break
  fi
  sleep 0.5
done
[[ "$final" == "ready" ]]

curl -sf -b /tmp/va-local-cookies.txt -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8010/api/library/search?q=Protein" >/tmp/va-search.json
python3 -c 'import json; assert json.load(open("/tmp/va-search.json")).get("hits")'

curl -sf http://127.0.0.1:8010/api/admin/queue >/tmp/va-queue.json
python3 -c 'import json; d=json.load(open("/tmp/va-queue.json")); assert "ready" in d'

# password reset
curl -sf -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\"}" \
  http://127.0.0.1:8010/api/auth/password-reset/request >/tmp/va-reset.json
RTOKEN=$(python3 -c 'import json;print(json.load(open("/tmp/va-reset.json"))["reset_token"])')
curl -sf -c /tmp/va-local-cookies2.txt -H 'Content-Type: application/json' \
  -d "{\"token\":\"$RTOKEN\",\"new_password\":\"newpass123\"}" \
  http://127.0.0.1:8010/api/auth/password-reset/confirm >/tmp/va-reset-ok.json

echo "[smoke-local] OK"
