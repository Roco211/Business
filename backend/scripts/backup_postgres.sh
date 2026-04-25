#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_PATH="${BACKUP_DIR}/business-postgres-${TIMESTAMP}.dump"

mkdir -p "${BACKUP_DIR}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required for PostgreSQL backup" >&2
  exit 2
fi

case "${DATABASE_URL}" in
  postgresql://*|postgresql+psycopg://*|postgres://*) ;;
  *)
    echo "Refusing backup: DATABASE_URL is not PostgreSQL" >&2
    exit 2
    ;;
esac

PG_URL="${DATABASE_URL/postgresql+psycopg:\/\//postgresql://}"
pg_dump --format=custom --no-owner --no-privileges --file "${OUTPUT_PATH}" "${PG_URL}"
sha256sum "${OUTPUT_PATH}" > "${OUTPUT_PATH}.sha256"

echo "backup_path=${OUTPUT_PATH}"
echo "checksum_path=${OUTPUT_PATH}.sha256"
