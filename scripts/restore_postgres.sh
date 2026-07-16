#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
  echo "Usage: $0 backup.sql.gz" >&2
  exit 2
fi
echo "This replaces all data in ${POSTGRES_DB:-video_analizier}. Type RESTORE to continue:"
read -r confirmation
[ "$confirmation" = "RESTORE" ] || exit 1
gzip -dc "$1" | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-video_analizier}" "${POSTGRES_DB:-video_analizier}"
