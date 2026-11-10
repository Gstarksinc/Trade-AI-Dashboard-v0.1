#!/usr/bin/env bash
# Production Backup Script for Trade AI Microservices Pipeline
# Dumps TimescaleDB schemas, archives WAL, takes Redis RDB snapshot, and computes SHA256 checksums.
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -f .env ]; then
  set -a; source .env; set +a
fi

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-trade_ai}"
BACKUP_DIR="backups"
STAMP=$(date -u +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
echo "[$(date -u)] Starting full production backup: ${STAMP}..."

# 1. Trigger Redis Background Save
echo "[$(date -u)] Triggering Redis BGSAVE..."
docker compose exec -T redis redis-cli -a "${REDIS_PASSWORD:-redis_local_pass}" bgsave || true

# 2. Archive PostgreSQL WAL
echo "[$(date -u)] Archiving WAL..."
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT pg_switch_wal();" || true

# 3. Create Custom Compressed pg_dump (all domain schemas)
DUMP_FILE="${BACKUP_DIR}/signals_${STAMP}.dump"
echo "[$(date -u)] Dumping TimescaleDB database schemas to ${DUMP_FILE}..."
docker compose exec -T db pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  --compress=9 \
  --no-owner \
  --schema="market_data" \
  --schema="feature_store" \
  --schema="model_registry" \
  --schema="signals_ledger" \
  --schema="paper_execution" \
  --schema="outbox" \
  --schema="public" \
  > "$DUMP_FILE"

# 4. Generate SHA256 Checksum
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$DUMP_FILE" > "${DUMP_FILE}.sha256"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$DUMP_FILE" > "${DUMP_FILE}.sha256"
fi

# 5. Cleanup Backups Older than 7 Days
find "$BACKUP_DIR" -name 'signals_*.dump*' -mtime +7 -delete

echo "[$(date -u)] Backup completed successfully: ${DUMP_FILE}"
