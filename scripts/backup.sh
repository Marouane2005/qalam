#!/usr/bin/env bash
# Backup Postgres (custom format) and the uploads directory.
# Run from the compose project root (where docker-compose.yml lives).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKUP_ROOT="${QALAM_BACKUP_ROOT:-/var/backups/qalam}"
RETENTION_DAYS="${QALAM_BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="${BACKUP_ROOT}/${STAMP}"

mkdir -p "$DEST"

echo "Backing up Postgres to ${DEST}/qalam.dump"
docker compose exec -T postgres \
  pg_dump -U qalam -d qalam -Fc \
  > "${DEST}/qalam.dump"

echo "Backing up uploads to ${DEST}/uploads.tar.gz"
docker compose exec -T api \
  tar -C /var/lib/qalam/uploads -czf - . \
  > "${DEST}/uploads.tar.gz"

echo "${STAMP}" > "${DEST}/stamp"
ln -sfn "$DEST" "${BACKUP_ROOT}/latest"

echo "Pruning backups older than ${RETENTION_DAYS} days"
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d ! -name "${STAMP}" -mtime "+${RETENTION_DAYS}" -exec rm -rf {} +

echo "Backup complete: ${DEST}"
