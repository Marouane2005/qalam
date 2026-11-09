#!/usr/bin/env bash
# Restore Postgres and uploads from a backup directory created by scripts/backup.sh.
# Usage: scripts/restore.sh /var/backups/qalam/<stamp>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SRC="${1:-}"
if [ -z "$SRC" ]; then
  if [ -L /var/backups/qalam/latest ] || [ -d /var/backups/qalam/latest ]; then
    SRC="/var/backups/qalam/latest"
  else
    echo "Usage: $0 /var/backups/qalam/<stamp>" >&2
    exit 1
  fi
fi

SRC="$(cd "$SRC" && pwd)"
DUMP="${SRC}/qalam.dump"
UPLOADS_TAR="${SRC}/uploads.tar.gz"

if [ ! -f "$DUMP" ]; then
  echo "Missing ${DUMP}" >&2
  exit 1
fi

echo "Restoring Postgres from ${DUMP}"
# Drop and recreate public schema objects via pg_restore --clean
docker compose exec -T postgres \
  pg_restore -U qalam -d qalam --clean --if-exists --no-owner \
  < "$DUMP"

if [ -f "$UPLOADS_TAR" ]; then
  echo "Restoring uploads from ${UPLOADS_TAR}"
  docker compose exec -T api sh -c 'rm -rf /var/lib/qalam/uploads/*'
  docker compose exec -T api tar -C /var/lib/qalam/uploads -xzf - < "$UPLOADS_TAR"
else
  echo "No uploads archive at ${UPLOADS_TAR}; skipping files"
fi

echo "Restarting api and worker"
docker compose up -d api worker

echo "Restore complete from ${SRC}"
