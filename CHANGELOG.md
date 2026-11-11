# Changelog

All notable changes to the **Trade AI Dashboard** platform are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v0.2.0] - 2026-11-11

### Added
- **Microservice Mesh**: Decomposed architecture into 9 containerized Python 3.11 FastAPI microservices with dedicated Dockerfiles, healthchecks, and unit test suites.
- **Redis 7 Streams**: Replaced raw Pub/Sub with persistent Redis Streams, consumer groups (`XREADGROUP`), auto-acknowledgements (`XACK`), and Dead-Letter Queue (`system.dlq`).
- **Domain Schemas & Hypertables**: Provisioned TimescaleDB PostgreSQL 16 domain schemas (`market_data`, `feature_store`, `model_registry`, `signals_ledger`, `paper_execution`, `outbox`) with 30-day chunking and automatic compression.
- **Alembic Unified Runner**: One-shot migrator container with revisions `001_domain_schemas_and_tables`, `002_shadow_predictions`, and `003_experiments_table`.
- **Authoritative Signal Lifecycle**: Implemented 8-state server-authoritative state machine with database-level optimistic concurrency control (`version` column).
- **PostgreSQL Advisory Lock**: Added `SELECT pg_advisory_xact_lock(888888)` in `risk-service` to serialize portfolio margin allocations atomically.
- **Single-Owner Position Exits**: Established `paper-exec-service` as sole owner of live position TP/SL exits, removing duplicate evaluation in `signal-service`.
- **Quantitative Governance**:
  - Combinatorial Purged Cross-Validation (CPCV) with 10 testing paths, sample uniqueness weighting, and 24-bar embargo.
  - Platt scaling (`CalibratedClassifierCV`) mapping raw GBDT margins to historical base rates (~31%).
  - Dynamic per-setup break-even probability gate $p^* = \frac{\text{SL} + \text{cost}}{\text{TP} + \text{SL}}$ derived from bar ATR%.
  - Inner-fold threshold optimization strictly inside training splits (`c_tr_idx`).
  - Automated quantitative experiment tracking table (`model_registry.experiments`) dynamically powering Deflated Sharpe Ratio (DSR) trial counts ($N_{\text{trials}} = 208+$).
  - 20-seed Monte Carlo null tests (label-shuffle and random probabilities) verifying zero lookahead leakage.
  - Bitwise artifact determinism verified via SHA256 hashes across scratch training runs.
- **Historical Data Backfill**: Ingested 3+ years of continuous Binance USD-M Futures 1h and 4h klines (51,366 bars) and funding rates (6,420 records) across all 8 perpetual pairs (BTC, ETH, SOL, BNB, XRP, DOGE, LINK, TRX).
- **Comprehensive Documentation Suite**: Added `ARCHITECTURE.md`, `WORKFLOW.md`, `EVENTS.md`, `DATA_MODEL.md`, `SIGNAL_LIFECYCLE.md`, `ML_PIPELINE.md`, `RISK_AND_EXECUTION.md`, `VALIDATION_REPORT.md`, `FORWARD_TEST.md`, `DATA.md`, `API.md`, `OPERATIONS.md`, `RUNBOOK.md`, `OBSERVABILITY.md`, `SECURITY.md`, `TESTING.md`, 12 Architecture Decision Records (`docs/DECISIONS/ADR-*.md`), and `ROADMAP.md`.

### Changed
- **Model Promotion Policy**: Strict multi-criteria promotion gates (Minimum 20 holdout trades, positive Net EV with bootstrap CI lower bound $> 0$, CPCV median Sharpe $> 0$, PBO $< 0.50$, ECE $\le 0.12$, DSR $> 0.95$). Zero models promoted; live status honestly set to `"No validated model"`.
- **Friction Accounting**: Realistically modeled at 14 bps round-trip with continuous 8h funding accrual.
- **Same-Bar Disambiguation**: Enforced conservative Stop-Loss-First (SL-First) rule on dual barrier breach.
- **Frontend Presentation**: Next.js 14 dashboard converted to strictly read-only presentation client connecting to `api-gateway` via REST and SSE.

### Removed
- **Excised Prior 24-Combination Performance Table**: Retracted earlier optimistic metrics proven to originate from synthetic mock fixtures and unbackfilled 1,000-bar samples.
- **Client State Transitions**: Deleted `/api/signals/transition` proxy routes and browser-side state mutation logic.
- **Monolithic Backend**: Removed legacy monolithic structure in favor of isolated microservices.
- **15m Timeframe Signals**: Disabled 15m trading pairs across all services due to excessive cost-to-risk ratio.

---

## [v0.1.0] - 2026-10-15

### Added
- Initial proof-of-concept monolithic FastAPI backend with Next.js web UI.
- Basic Binance REST kline polling and Redis Pub/Sub messaging.
- Preliminary LightGBM classification model.
