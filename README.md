# Trade AI Dashboard v0.1

An institutional-grade, event-driven cryptocurrency algorithmic research platform and paper trading dashboard built on **Python 3.11, FastAPI, TimescaleDB, Redis 7, and Next.js 14**.

> **Operational Scope**: This platform is engineered strictly for **PAPER TRADING and quantitative research**. There is strictly zero real order execution and zero exchange private keys anywhere.

---

## Technical Stack & Architecture

- **Microservices**: 10 containerized services under `services/` (each with dedicated `Dockerfile`, `requirements.txt`, health checks, and unit tests).
- **Event Bus & Messaging**: Redis 7 Streams with consumer groups (`XREADGROUP`, auto-ack, retry, and Dead-Letter Queue `system.dlq`).
- **Database**: PostgreSQL 16 with TimescaleDB hypertables, domain schemas (`market_data`, `feature_store`, `model_registry`, `signals_ledger`, `paper_execution`, `outbox`), and single Alembic migrations runner.
- **Machine Learning**: LightGBM (Platt calibrated) + Random Forest Meta-Classifier with Purged Combinatorial CV (CPCV), Deflated Sharpe Ratio (DSR), Probability of Backtest Overfitting (PBO), and strict promotion gates.
- **Frontend**: Next.js 14 read-only UI with dark/light themes, live ticker bar, per-symbol/per-timeframe model status matrix (champion/shadow/disabled), and paper-trading labels everywhere.

For detailed architecture diagrams, event flows, and domain schema definitions, see [ARCHITECTURE.md](ARCHITECTURE.md) and [VALIDATION_REPORT.md](VALIDATION_REPORT.md).

---

## Quickstart & How to Run

### 1. Environment Setup
Copy the sample environment configuration:
```bash
cp .env.example .env
```

### 2. Run Database Migrations
Run the one-shot migrator container to create all domain schemas, hypertables, and indexes:
```bash
docker compose run --rm migrator
```

### 3. Start Infrastructure & Microservices
```bash
# Start all microservices in detached mode
docker compose up -d

# Check running containers
docker compose ps
```

### 4. Verify Service Health Probes
```bash
curl -s http://localhost:8000/health  # API Gateway
curl -s http://localhost:8001/health  # Market Collector
curl -s http://localhost:8002/health  # Feature Service
curl -s http://localhost:8003/health  # Model Service
curl -s http://localhost:8004/health  # Training Service
curl -s http://localhost:8005/health  # Risk Service
curl -s http://localhost:8006/health  # Signal Service
curl -s http://localhost:8007/health  # Paper Execution Service
curl -s http://localhost:8009/health  # Notifier Service
```

### 5. Access the Next.js Dashboard
Open [http://localhost:3000](http://localhost:3000) in your web browser.

---

## How to Test

### 1. Run Microservice Test Suites
```bash
pytest services/market-collector/tests
pytest services/feature-service/tests
pytest services/model-service/tests
pytest services/training-service/tests
pytest services/risk-service/tests
pytest services/signal-service/tests
pytest services/paper-exec-service/tests
pytest tests/test_e2e_pipeline.py
```

### 2. Run Leakage Audit Suite
```bash
python -m services.training-service.leakage_audit
```

### 3. Run Frontend Production Build & Unit Tests
```bash
npm run build --prefix dashboard
```

---

## Production Deployment

A hardened production configuration is available in `docker-compose.prod.yml`:
- Internal bridge network isolation (`internal-net`) preventing external exposure of internal microservices.
- Hard resource reservations and memory limits.
- Log rotation (`json-file`, max 50MB $\times$ 10 files).
- Production command:
  ```bash
  docker compose -f docker-compose.prod.yml up -d
  ```
