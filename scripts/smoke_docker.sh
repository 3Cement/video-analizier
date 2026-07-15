#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "[smoke] docker not available; run: make smoke-local"
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

echo "[smoke] building and starting compose..."
docker compose up -d --build

echo "[smoke] waiting for /api/health..."
ok=0
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health >/tmp/va-health.json; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  echo "[smoke] API did not become healthy"
  docker compose logs --tail=80 api worker || true
  exit 1
fi
grep -q '"status":"ok"' /tmp/va-health.json || grep -q '"status": "ok"' /tmp/va-health.json

echo "[smoke] register + cookie session..."
EMAIL="smoke_$RANDOM@example.com"
PASS="secret123"
curl -sf -c /tmp/va-cookies.txt -H 'Content-Type: application/json'   -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}"   http://localhost:8000/api/auth/register >/tmp/va-auth.json
TOKEN=$(python3 -c 'import json;print(json.load(open("/tmp/va-auth.json"))["token"])')

echo "[smoke] create text source..."
curl -sf -b /tmp/va-cookies.txt -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json'   -d '{"title":"Smoke note","text":"Protein recovery guidance for smoke test content that is long enough.","auto_summarize":false}'   http://localhost:8000/api/sources/text >/tmp/va-source.json
SID=$(python3 -c 'import json;print(json.load(open("/tmp/va-source.json"))["id"])')

echo "[smoke] wait for source $SID..."
final=""
for i in $(seq 1 40); do
  curl -sf -b /tmp/va-cookies.txt -H "Authorization: Bearer $TOKEN"     "http://localhost:8000/api/sources/$SID/status" >/tmp/va-status.json
  final=$(python3 -c 'import json;print(json.load(open("/tmp/va-status.json"))["status"])')
  if [[ "$final" == "ready" || "$final" == "failed" ]]; then
    break
  fi
  sleep 2
done
if [[ "$final" != "ready" ]]; then
  echo "[smoke] source did not become ready: $final"
  docker compose logs --tail=100 api worker || true
  exit 1
fi

echo "[smoke] library search..."
curl -sf -b /tmp/va-cookies.txt -H "Authorization: Bearer $TOKEN"   "http://localhost:8000/api/library/search?q=Protein" >/tmp/va-search.json
python3 -c 'import json; d=json.load(open("/tmp/va-search.json")); assert d.get("hits"), d'

echo "[smoke] admin queue..."
curl -sf http://localhost:8000/api/admin/queue >/tmp/va-queue.json
python3 -c 'import json; d=json.load(open("/tmp/va-queue.json")); assert "pending" in d and "ready" in d, d'

echo "[smoke] OK"
