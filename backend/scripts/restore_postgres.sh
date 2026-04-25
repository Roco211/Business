#!/usr/bin/env bash
set -euo pipefail

BACKUP_PATH="${1:-}"
if [[ -z "${BACKUP_PATH}" ]]; then
  echo "Usage: $0 /path/to/business-postgres-YYYYmmddTHHMMSSZ.dump" >&2
  exit 2
fi
if [[ ! -f "${BACKUP_PATH}" ]]; then
  echo "Backup file not found: ${BACKUP_PATH}" >&2
  exit 2
fi
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required for PostgreSQL restore" >&2
  exit 2
fi
case "${DATABASE_URL}" in
  postgresql://*|postgresql+psycopg://*|postgres://*) ;;
  *)
    echo "Refusing restore: DATABASE_URL is not PostgreSQL" >&2
    exit 2
    ;;
esac

PG_URL="${DATABASE_URL/postgresql+psycopg:\/\//postgresql://}"

if [[ -f "${BACKUP_PATH}.sha256" ]]; then
  sha256sum --check "${BACKUP_PATH}.sha256"
fi

pg_restore --clean --if-exists --no-owner --no-privileges --dbname "${PG_URL}" "${BACKUP_PATH}"
echo "restore_completed=${BACKUP_PATH}"
