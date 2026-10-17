#!/usr/bin/env bash
# =============================================================================
#  backup.sh — PostgreSQL backup script for the Personal AI Agent Platform
#
#  Usage:
#    ./backup.sh
#
#  Environment variables (loaded from /app/.env or exported in the shell):
#    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
#    BACKUP_S3_BUCKET, BACKUP_S3_KEY, BACKUP_S3_SECRET, BACKUP_S3_REGION
#    BACKUP_S3_ENDPOINT  (optional, for S3-compatible stores)
#
#  Keeps the last 7 local backups in /backups.
# =============================================================================
set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_LOCAL="${KEEP_LOCAL:-7}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILENAME="pgdump_${POSTGRES_DB:-agentdb}_${TIMESTAMP}.sql.gz"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"
LOG_PREFIX="[backup] $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ─── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo "${LOG_PREFIX} INFO  $*"; }
warn() { echo "${LOG_PREFIX} WARN  $*" >&2; }
die()  { echo "${LOG_PREFIX} ERROR $*" >&2; exit 1; }

require_cmd() {
    command -v "$1" &>/dev/null || die "Required command not found: $1"
}

# ─── Validate required env vars ───────────────────────────────────────────────
: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

# ─── Check dependencies ───────────────────────────────────────────────────────
require_cmd pg_dump
require_cmd gzip

# ─── Ensure backup directory exists ───────────────────────────────────────────
mkdir -p "${BACKUP_DIR}"

# ─── Dump database ────────────────────────────────────────────────────────────
log "Starting backup of database '${POSTGRES_DB}' on ${POSTGRES_HOST}:${POSTGRES_PORT}"

export PGPASSWORD="${POSTGRES_PASSWORD}"

pg_dump \
    --host="${POSTGRES_HOST}" \
    --port="${POSTGRES_PORT}" \
    --username="${POSTGRES_USER}" \
    --dbname="${POSTGRES_DB}" \
    --no-password \
    --format=plain \
    --no-owner \
    --no-acl \
    | gzip -9 > "${BACKUP_PATH}" \
    || die "pg_dump failed — backup aborted"

unset PGPASSWORD

BACKUP_SIZE="$(du -sh "${BACKUP_PATH}" | cut -f1)"
log "Backup written: ${BACKUP_PATH} (${BACKUP_SIZE})"

# ─── Upload to S3 (optional) ──────────────────────────────────────────────────
if [[ -n "${BACKUP_S3_BUCKET:-}" ]] && \
   [[ -n "${BACKUP_S3_KEY:-}" ]]   && \
   [[ -n "${BACKUP_S3_SECRET:-}" ]]; then

    require_cmd aws

    export AWS_ACCESS_KEY_ID="${BACKUP_S3_KEY}"
    export AWS_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET}"
    export AWS_DEFAULT_REGION="${BACKUP_S3_REGION:-us-east-1}"

    S3_URI="s3://${BACKUP_S3_BUCKET}/database/${BACKUP_FILENAME}"

    ENDPOINT_ARGS=()
    if [[ -n "${BACKUP_S3_ENDPOINT:-}" ]]; then
        ENDPOINT_ARGS=(--endpoint-url "${BACKUP_S3_ENDPOINT}")
    fi

    log "Uploading backup to ${S3_URI} ..."
    aws s3 cp "${BACKUP_PATH}" "${S3_URI}" "${ENDPOINT_ARGS[@]}" \
        --storage-class STANDARD_IA \
        || die "S3 upload failed"

    log "Upload complete: ${S3_URI}"

    # Unset AWS credentials from environment
    unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_DEFAULT_REGION
else
    warn "S3 vars not set — backup stored locally only"
fi

# ─── Rotate local backups (keep last N) ───────────────────────────────────────
log "Rotating local backups — keeping last ${KEEP_LOCAL}"

# List backups sorted oldest-first; delete everything beyond the limit
mapfile -t OLD_BACKUPS < <(
    ls -1t "${BACKUP_DIR}"/pgdump_*.sql.gz 2>/dev/null | tail -n "+$((KEEP_LOCAL + 1))"
)

if [[ ${#OLD_BACKUPS[@]} -gt 0 ]]; then
    for f in "${OLD_BACKUPS[@]}"; do
        log "Removing old backup: ${f}"
        rm -f "${f}"
    done
fi

log "Backup complete ✓"
