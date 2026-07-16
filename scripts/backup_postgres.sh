#!/usr/bin/env bash
set -euo pipefail

backup_dir="${BACKUP_DIR:-./backups}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
mkdir -p "$backup_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$backup_dir/video-analizier-$stamp.sql.gz"
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-video_analizier}" "${POSTGRES_DB:-video_analizier}" | gzip -9 > "$target"
find "$backup_dir" -type f -name 'video-analizier-*.sql.gz' -mtime "+$retention_days" -delete
echo "$target"
