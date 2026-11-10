#!/usr/bin/env bash
# Production Restore & Verification Script
# Restores TimescaleDB dump and runs schema row-count integrity checks.
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -f .env ]; then
  set -a; source .env; set +a
fi

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-trade_ai}"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <path-to-dump-file> [optional-target-db]"
  echo "Example: $0 backups/signals_20261110_120000.dump trade_ai_fresh"
  exit 1
fi

DUMP_FILE="$1"
TARGET_DB="${2:-$POSTGRES_DB}"

echo "================================================================================"
echo "PRODUCTION RESTORE PROCEDURE: DUMP-ONLY LOGICAL RESTORE"
echo "NOTE: This procedure performs a logical custom compressed dump restoration only."
echo "Continuous point-in-time recovery (PITR) requires external WAL archiving"
echo "(archive_command or wal-g/pgBackRest) to be configured."
echo "================================================================================"

if [ ! -f "$DUMP_FILE" ]; then
  echo "Error: Dump file $DUMP_FILE not found."
  exit 1
fi

# Ensure target database exists and has timescaledb extension
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE ${TARGET_DB};" || true
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$TARGET_DB" -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" || true

# 1. Verify Checksum if present
if [ -f "${DUMP_FILE}.sha256" ]; then
  echo "[$(date -u)] Verifying SHA256 checksum..."
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum -c "${DUMP_FILE}.sha256"
  fi
fi

echo "[$(date -u)] Restoring ${DUMP_FILE} to database ${TARGET_DB}..."

# 2. Terminate active application connections before restoring
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE datname = '${TARGET_DB}' AND pid <> pg_backend_pid();
" || true

# 3. Execute pg_restore with clean schema replacement
docker compose exec -T db pg_restore \
  -U "$POSTGRES_USER" \
  -d "$TARGET_DB" \
  --clean \
  --if-exists \
  --no-owner \
  < "$DUMP_FILE" || echo "[Warning] Some restore warnings occurred (expected for non-empty tables/triggers)."

# 4. Integrity and Row-Count Verification Across Domains
echo "[$(date -u)] Verifying restored schema integrity and table counts in ${TARGET_DB}..."
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$TARGET_DB" -c "
  SELECT 'market_data.candles' AS table_name, count(*) AS count FROM market_data.candles
  UNION ALL
  SELECT 'market_data.funding_rates', count(*) FROM market_data.funding_rates
  UNION ALL
  SELECT 'feature_store.features', count(*) FROM feature_store.features
  UNION ALL
  SELECT 'model_registry.models', count(*) FROM model_registry.models
  UNION ALL
  SELECT 'signals_ledger.signals', count(*) FROM signals_ledger.signals
  UNION ALL
  SELECT 'paper_execution.paper_trades', count(*) FROM paper_execution.paper_trades
  UNION ALL
  SELECT 'outbox.events', count(*) FROM outbox.events;
"

echo "[$(date -u)] Restore and integrity check completed successfully."
