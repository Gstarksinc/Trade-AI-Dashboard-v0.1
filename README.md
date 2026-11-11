# Trade AI Dashboard

An institutional-grade, event-driven cryptocurrency algorithmic research platform and paper trading dashboard built on **Python 3.11, FastAPI, TimescaleDB, Redis 7 Streams, and Next.js 14**.

> [!IMPORTANT]
> **Operational Scope**: This platform is engineered strictly for **PAPER TRADING and quantitative research**. There is strictly zero real order execution and zero exchange private keys. The scope is restricted to **crypto futures only** (8 Binance USD-M perpetual pairs: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `LINKUSDT`, `TRXUSDT`; `1h` and `4h` timeframes; `15m` is disabled by risk policy).

> [!NOTE]
> **Current Model Validation Status**: Under rigorous combinatorial purged cross-validation (CPCV), deflated Sharpe ratio (DSR), and probability of backtest overfitting (PBO) audits on 3+ years of real backfilled data, **zero models passed promotion gates**. In accordance with our zero-leakage policy, **no model is promoted to champion or challenger**. The API Gateway and Next.js Dashboard honestly display `"No validated model"`. Forward testing is not active.

---

## Architecture Summary

```
[Binance Futures REST/WS]
          │
          ▼
   market-collector (:8001) ──(candle.closed)──► feature-service (:8002)
                                                        │ (features.ready)
                                                        ▼
   risk-service (:8005) ◄──(prediction.ready)─── model-service (:8003)
          │
    (signal.approved)
          ▼
   signal-service (:8006) ──(signal.state_changed)──► api-gateway (:8000) ──► Next.js Dashboard (:3000)
          ▲                                                ▲
          │ (trade.closed)                                 │ (SSE / REST)
   paper-exec-service (:8007) ─────────────────────────────┘
```

- **Microservice Mesh**: 9 containerized Python 3.11 FastAPI microservices + 1 Next.js 14 Web Dashboard + TimescaleDB (PostgreSQL 16) + Redis 7 Streams + Prometheus/Grafana.
- **Event Bus**: Redis 7 Streams with consumer groups (`XREADGROUP`, auto-acknowledgement, retry, and Dead-Letter Queue `system.dlq`).
- **Data Persistence**: PostgreSQL 16 with TimescaleDB hypertables across isolated domain schemas (`market_data`, `feature_store`, `model_registry`, `signals_ledger`, `paper_execution`, `outbox`).
- **ML Governance**: LightGBM (Platt calibrated) + Random Forest meta-model, Combinatorial Purged Cross-Validation (CPCV), PBO, Deflated Sharpe Ratio (DSR), dynamic ATR break-even thresholding, and automated experiment logging.
- **Client Presentation**: Next.js 14 read-only dashboard connecting solely to `api-gateway` via REST and Server-Sent Events (SSE). No browser-side state mutations or exchange connections.

For detailed specifications, see:
- [System Architecture](docs/ARCHITECTURE.md)
- [End-to-End Workflow](docs/WORKFLOW.md)
- [Events & Contracts](docs/EVENTS.md)
- [Database Domain Model](docs/DATA_MODEL.md)
- [Authoritative Signal Lifecycle](docs/SIGNAL_LIFECYCLE.md)
- [Model Validation Report](docs/VALIDATION_REPORT.md)
- [Quantitative Experiment Registry](docs/EXPERIMENTS.md)

---

## Service Inventory & Port Allocations

The Compose project name is `signals`. When running, 13 containers are active (the `migrator` exits `0` upon completion, and `training-service` runs on-demand via the `train` profile):

| Service | Port | Bind Address | Role & Responsibility | Compose Profile |
| :--- | :---: | :---: | :--- | :---: |
| `market-collector` | `8001` | `127.0.0.1:8001` | Binance Futures public WS/REST ingestion; candle aggregation | Default |
| `feature-service` | `8002` | `127.0.0.1:8002` | 48 point-in-time causal technical & derivatives indicators | Default |
| `model-service` | `8003` | `127.0.0.1:8003` | Real-time ML inference (champion & shadow models) | Default |
| `training-service` | `8004` | `127.0.0.1:8004` | On-demand offline CPCV, calibration & promotion pipeline | `train` |
| `risk-service` | `8005` | `127.0.0.1:8005` | Advisory-locked portfolio sizing, cost-to-risk gating | Default |
| `signal-service` | `8006` | `127.0.0.1:8006` | Authoritative signal ledger & optimistic state machine | Default |
| `paper-exec-service` | `8007` | `127.0.0.1:8007` | Simulated paper order fills & SL-first position exits | Default |
| `api-gateway` | `8000` | `0.0.0.0:8000` | Public REST API, system status & multiplexed SSE stream | Default |
| `notifier-service` | `8009` | `127.0.0.1:8009` | Telegram / Discord webhook alert dispatcher | Default |
| `dashboard` | `3000` | `0.0.0.0:3000` | Next.js 14 frontend user interface (read-only) | Default |
| `db` (TimescaleDB) | `5432` | `127.0.0.1:5432` | TimescaleDB PostgreSQL 16 time-series storage | Default |
| `redis` | `6379` | `127.0.0.1:6379` | Redis 7 event streaming bus & fast cache | Default |
| `prometheus` | `9090` | `127.0.0.1:9090` | Metrics scraping engine | Default |
| `grafana` | `3001` | `0.0.0.0:3001` | Observability dashboards & alert visualizer | Default |
| `migrator` | — | Internal | One-shot Alembic migration runner (exits `0`) | Default |

---

## Quickstart & Operations

### 1. Prerequisites
- **Operating System**: Windows 10/11 with Docker Desktop (WSL 2 backend) or Linux (Ubuntu 22.04+).
- **Docker Compose**: Version v2.20+.
- **Shell**: PowerShell (Windows) or Bash (Linux / WSL / Git Bash).

### 2. Environment Configuration

**PowerShell (Windows)**:
```powershell
Copy-Item .env.example .env
```

**Bash / WSL / Git Bash**:
```bash
cp .env.example .env
```

### 3. Run Database Migrations
Run the one-shot migrator container to apply Alembic revisions up to `head`:

**PowerShell**:
```powershell
docker compose run --rm migrator
```

**Bash**:
```bash
docker compose run --rm migrator
```

### 4. Start Infrastructure & Microservices

**PowerShell**:
```powershell
# Start all 13 core containers in detached mode
docker compose up -d

# Verify all containers report healthy
docker compose ps
```

**Bash**:
```bash
docker compose up -d
docker compose ps
```

### 5. Verify Service Health

**PowerShell**:
```powershell
@(8000, 8001, 8002, 8003, 8005, 8006, 8007, 8009) | ForEach-Object {
    $res = Invoke-RestMethod -Uri "http://localhost:$_/health"
    Write-Host "Port $_ : $($res.service) is $($res.status)"
}
```

**Bash**:
```bash
for port in 8000 8001 8002 8003 8005 8006 8007 8009; do
    echo "Port $port: $(curl -s http://localhost:$port/health)"
done
```

### 6. Access User Interfaces
- **Next.js Web Dashboard**: [http://localhost:3000](http://localhost:3000)
- **API Gateway Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Grafana Dashboards**: [http://localhost:3001](http://localhost:3001) (default login: `admin` / `admin`)
- **Prometheus Targets**: [http://localhost:9090](http://localhost:9090)

---

## Running Automated Tests

All tests run inside isolated Docker containers without requiring host Python installations:

```powershell
# Run all 41 microservice unit and integration tests
docker compose run --rm signal-service pytest services/signal-service/tests
docker compose run --rm risk-service pytest services/risk-service/tests
docker compose run --rm paper-exec-service pytest services/paper-exec-service/tests
docker compose run --rm market-collector pytest services/market-collector/tests
docker compose run --rm feature-service pytest services/feature-service/tests
docker compose run --rm model-service pytest services/model-service/tests
docker compose run --rm training-service pytest services/training-service/tests

# Run End-to-End recorded fixture pipeline test
docker compose run --rm training-service pytest tests/test_e2e_pipeline.py

# Run Frontend contract test suite (21 tests)
docker compose run --rm dashboard npm test
```

---

## Backup & Restore Policy

> [!WARNING]
> Database backups via `scripts/backup.sh` and `scripts/restore.sh` are **DUMP-ONLY** logical snapshots using `pg_dump -Fc`. Point-in-time recovery (PITR) and continuous WAL archiving are **not configured**. To execute scripts on Windows, run them via WSL or Git Bash:
> ```bash
> ./scripts/backup.sh
> ./scripts/restore.sh backups/<dump-file>.dump trade_ai_scratch
> ```
