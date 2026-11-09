#!/usr/bin/env bash
# Daily TimescaleDB dump, 7-day retention. Copy dumps off the machine too.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
STAMP=$(date -u +%Y%m%d_%H%M%S)
mkdir -p backups
docker compose exec -T db pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -Fc > backups/signals_$STAMP.dump
find backups -name 'signals_*.dump' -mtime +7 -delete
