# Operations Manual & Infrastructure Guide

> **Stack Scope**: 9 Python 3.11 microservices, 1 Next.js 14 Dashboard, TimescaleDB PG16, Redis 7, Prometheus, Grafana.
> **Compose Project Name**: `signals`
> **Target Environment**: Windows PC with Docker Desktop (WSL 2 backend) or Ubuntu 22.04+ Server.

---

## 1. Startup & Shutdown Sequencing

### Startup Order (Managed by Compose Dependencies):
1. **Tier 1 (Storage)**: `db` (TimescaleDB) and `redis` start first and must pass health checks.
2. **Tier 2 (Schema Migration)**: `migrator` runs once (`restart: 'no'`), applies Alembic migrations, verifies head revision, and exits `0`.
3. **Tier 3 (Core Services)**: `market-collector`, `feature-service`, `model-service`, `risk-service`, `signal-service`, `paper-exec-service`, `notifier-service`, `prometheus`.
4. **Tier 4 (Presentation)**: `api-gateway` starts after Redis; `dashboard` starts after `api-gateway`; `grafana` starts after `prometheus`.

### Operational Commands:

**PowerShell (Windows)**:
```powershell
# 1. Start storage and execute one-shot migrations
docker compose run --rm migrator

# 2. Start all production services in background
docker compose up -d

# 3. View live health status of all 13 containers
docker compose ps

# 4. View aggregated real-time logs
docker compose logs -f --tail=100

# 5. Graceful shutdown without data loss
docker compose stop

# 6. Full shutdown (preserves volumes)
docker compose down
```

**Bash (Linux / WSL / Git Bash)**:
```bash
docker compose run --rm migrator
docker compose up -d
docker compose ps
docker compose logs -f --tail=100
docker compose stop
docker compose down
```

> [!CAUTION]
> **Data Protection Rule**: NEVER run `docker compose down -v` on the active instance. Doing so destroys the Docker named volumes (`pgdata`, `redisdata`) containing 3+ years of backfilled klines and funding records.

---

## 2. Comprehensive Environment Variable Reference

| Environment Variable | Default Value | Target Services | Description |
| :--- | :--- | :--- | :--- |
| `POSTGRES_USER` | `postgres` | `db`, `migrator`, all services | TimescaleDB superuser |
| `POSTGRES_PASSWORD` | `postgres` | `db`, `migrator`, all services | TimescaleDB authentication password |
| `POSTGRES_DB` | `trade_ai` | `db`, `migrator`, all services | Primary TimescaleDB database name |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/trade_ai` | All Python microservices | Async SQLAlchemy database connection string |
| `REDIS_PASSWORD` | `redis_local_pass` | `redis`, all services | Redis 7 authentication password |
| `REDIS_URL` | `redis://:redis_local_pass@redis:6379/0` | All Python microservices | Redis Streams connection string |
| `BINANCE_FUTURES_BASE_URL` | `https://fapi.binance.com` | `market-collector`, `training` | Binance USD-M public REST endpoint |
| `BINANCE_WS_URL` | `wss://fstream.binance.com/ws` | `market-collector` | Binance USD-M public WebSocket stream |
| `RISK_ADVISORY_LOCK_ID` | `888888` | `risk-service` | PostgreSQL transaction advisory lock ID |
| `DEFAULT_RISK_PER_TRADE` | `0.005` (0.5%) | `risk-service` | Fixed-fractional equity risk fraction |
| `MAX_LEVERAGE_CAP` | `3.0` | `risk-service` | Maximum allowable effective leverage |
| `DSR_TRIALS` | (Dynamic) | `training-service` | Override for Deflated Sharpe trial count |
| `API_URL` | `http://api-gateway:8000` | `dashboard` | Next.js internal backend API proxy URL |
| `GF_SECURITY_ADMIN_PASSWORD` | `admin` | `grafana` | Grafana administrator login password |

---

## 3. Database Migration Management (Alembic)

Database schema migrations are unified under [`libs/database/migrations/`](file:///libs/database/migrations/).
- **Verify Heads**:
  ```powershell
  docker compose run --rm migrator alembic heads
  ```
- **Check Current Applied Revision**:
  ```powershell
  docker compose run --rm migrator alembic current
  ```
- **Apply Upgrades**:
  ```powershell
  docker compose run --rm migrator alembic upgrade head
  ```
- **Idempotency Rule**: Running `upgrade head` repeatedly on an up-to-date database produces no DDL changes, prints `current revision: <id>`, and exits `0`. Existing migration files must never be modified.

---

## 4. Backup & Restore Procedures (Dump-Only)

> [!WARNING]
> **Dump-Only Architecture**: Backups are logical snapshots generated using `pg_dump -Fc`. Point-In-Time Recovery (PITR) and continuous WAL archiving are **not configured**.

### Backup Execution:
Run via WSL or Git Bash on Windows:
```bash
./scripts/backup.sh
```
- Creates a timestamped dump file in `backups/signals_YYYYMMDD_HHMMSS.dump`.
- Backs up all domain schemas (`market_data`, `feature_store`, `model_registry`, `signals_ledger`, `paper_execution`, `outbox`).

### Restore Execution:
Restores into an isolated scratch database without disrupting live data:
```bash
./scripts/restore.sh backups/signals_20261110_165241.dump trade_ai_scratch
```
- Restores all hypertables, compression policies, and row records.
- Verifies domain table row counts against the primary database.

---

## 5. Storage & Memory Sizing Rules

### Redis 7 Streams:
- **Max Memory**: Hard-capped at `512mb` (`--maxmemory 512mb`).
- **Eviction Policy**: Set strictly to `--maxmemory-policy noeviction`. Messages in streams are critical business events; Redis must return an error rather than evict unconsumed messages.
- **Persistence**: Hybrid AOF + RDB (`--appendonly yes --appendfsync everysec`).
- **Stream Trimming**: Every event producer invokes approximate trimming (`maxlen=10000`), keeping stream memory footprint stable under 100MB.

### TimescaleDB:
- Hypertable chunks are compressed after 30 days (`market_data.candles`), reducing disk storage requirements by up to 90%.
- Volume mount: `pgdata` named Docker volume backed by host NVMe SSD.

---

## 6. Windows-Specific Environment Notes

1. **WSL 2 Resource Allocation**: Docker Desktop on Windows runs within WSL 2 (`vmmem`). To prevent out-of-memory errors during multi-symbol model training, configure `C:\Users\<User>\.wslconfig`:
   ```ini
   [wsl2]
   memory=16GB
   processors=8
   swap=8GB
   ```
2. **PowerShell Execution Policy**: Run PowerShell as Administrator if script execution is blocked:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
3. **System Sleep Prevention**: Ensure Windows power settings do not enter system sleep during market collection or training runs.
