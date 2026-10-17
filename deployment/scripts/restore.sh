#!/usr/bin/env bash
# =============================================================================
#  restore.sh — Restore a PostgreSQL backup for the Personal AI Agent Platform
#
#  Usage:
#    ./restore.sh <path-to-backup.sql.gz>
#
#  The backup file may be:
#    - A local path:        /backups/pgdump_agentdb_20240101T000000Z.sql.gz
#    - An S3 URI:           s3://my-bucket/database/pgdump_agentdb_20240101T000000Z.sql.gz
#
#  Required environment variables:
#    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
#
#  Optional (needed when restoring from S3):
#    BACKUP_S3_KEY, BACKUP_S3_SECRET, BACKUP_S3_REGION, BACKUP_S3_ENDPOINT
#
#  WARNING: This script drops and recreates the target database.
#           ALL EXISTING DATA WILL BE LOST.
# =============================================================================
set -euo pipefail

# ─── Helpers ──────────────────────────────────────────────────────────────────
LOG_PREFIX="[restore] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
log()  { echo "${LOG_PREFIX} INFO  $*"; }
warn() { echo "${LOG_PREFIX} WARN  $*" >&2; }
die()  { echo "${LOG_PREFIX} ERROR $*" >&2; exit 1; }

require_cmd() {
    command -v "$1" &>/dev/null || die "Required command not found: $1"
}

usage() {
    echo "Usage: $0 <backup-file-or-s3-uri>" >&2
    echo "  Example (local): $0 /backups/pgdump_agentdb_20240101T000000Z.sql.gz" >&2
    echo "  Example (S3):    $0 s3://my-bucket/database/pgdump_agentdb_20240101T000000Z.sql.gz" >&2
    exit 1
}

# ─── Parse argument ───────────────────────────────────────────────────────────
[[ $# -lt 1 ]] && usage
BACKUP_SOURCE="$1"

# ─── Validate required env vars ───────────────────────────────────────────────
: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

# ─── Check base dependencies ──────────────────────────────────────────────────
require_cmd psql
require_cmd gunzip

# ─── Safety confirmation ─────────────────────────────────────────────────────
warn "=========================================================="
warn "  This will DROP and RECREATE database: ${POSTGRES_DB}"
warn "  on host: ${POSTGRES_HOST}:${POSTGRES_PORT}"
warn "  ALL EXISTING DATA WILL BE PERMANENTLY LOST."
warn "=========================================================="

if [[ -t 0 ]]; then
    # Interactive — prompt the user
    read -r -p "[restore] Type 'yes' to confirm: " CONFIRM
    [[ "${CONFIRM}" == "yes" ]] || die "Aborted by user"
else
    warn "Non-interactive mode — proceeding without confirmation"
fi

# ─── Resolve backup file ──────────────────────────────────────────────────────
LOCAL_BACKUP=""

if [[ "${BACKUP_SOURCE}" == s3://* ]]; then
    require_cmd aws

    : "${BACKUP_S3_KEY:?BACKUP_S3_KEY is required for S3 restore}"
    : "${BACKUP_S3_SECRET:?BACKUP_S3_SECRET is required for S3 restore}"

    export AWS_ACCESS_KEY_ID="${BACKUP_S3_KEY}"
    export AWS_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET}"
    export AWS_DEFAULT_REGION="${BACKUP_S3_REGION:-us-east-1}"

    ENDPOINT_ARGS=()
    if [[ -n "${BACKUP_S3_ENDPOINT:-}" ]]; then
        ENDPOINT_ARGS=(--endpoint-url "${BACKUP_S3_ENDPOINT}")
    fi

    TMPDIR_RESTORE="$(mktemp -d)"
    trap 'rm -rf "${TMPDIR_RESTORE}"' EXIT

    FILENAME="$(basename "${BACKUP_SOURCE}")"
    LOCAL_BACKUP="${TMPDIR_RESTORE}/${FILENAME}"

    log "Downloading backup from ${BACKUP_SOURCE} ..."
    aws s3 cp "${BACKUP_SOURCE}" "${LOCAL_BACKUP}" "${ENDPOINT_ARGS[@]}" \
        || die "Failed to download backup from S3"

    unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_DEFAULT_REGION
    log "Downloaded to ${LOCAL_BACKUP}"
else
    LOCAL_BACKUP="${BACKUP_SOURCE}"
    [[ -f "${LOCAL_BACKUP}" ]] || die "Backup file not found: ${LOCAL_BACKUP}"
fi

# ─── Restore ─────────────────────────────────────────────────────────────────
export PGPASSWORD="${POSTGRES_PASSWORD}"

PG_CONN_ARGS=(
    --host="${POSTGRES_HOST}"
    --port="${POSTGRES_PORT}"
    --username="${POSTGRES_USER}"
    --no-password
)

log "Terminating existing connections to '${POSTGRES_DB}' ..."
psql "${PG_CONN_ARGS[@]}" --dbname=postgres --command \
    "SELECT pg_terminate_backend(pid)
     FROM   pg_stat_activity
     WHERE  datname = '${POSTGRES_DB}'
     AND    pid <> pg_backend_pid();" \
    &>/dev/null || true

log "Dropping database '${POSTGRES_DB}' ..."
psql "${PG_CONN_ARGS[@]}" --dbname=postgres --command \
    "DROP DATABASE IF EXISTS \"${POSTGRES_DB}\";" \
    || die "Failed to drop database"

log "Creating database '${POSTGRES_DB}' ..."
psql "${PG_CONN_ARGS[@]}" --dbname=postgres --command \
    "CREATE DATABASE \"${POSTGRES_DB}\" OWNER \"${POSTGRES_USER}\";" \
    || die "Failed to create database"

log "Restoring from ${LOCAL_BACKUP} ..."
gunzip -c "${LOCAL_BACKUP}" \
    | psql "${PG_CONN_ARGS[@]}" --dbname="${POSTGRES_DB}" \
    || die "psql restore failed"

unset PGPASSWORD

log "Restore complete ✓  Database '${POSTGRES_DB}' has been restored."
