# Phase 6 & Microservices Architecture Refactor Progress Tracker

**Scope**: Crypto futures paper trading & research only. Strictly no exchange private keys, no real order execution.
**Champion Policy**: No model promoted to champion until leakage audit passes and forward paper observation window is completed. Currently all eligible models (BTC/ETH 1h/4h) operate strictly in Challenger Shadow Mode. 15m timeframe remains suppressed.

---

## Interrupted Task Item Status Table

| Item | Description | Status | Verification Evidence / Command Output | Next Step |
| :--- | :--- | :---: | :--- | :--- |
| **Item V** | Clean `down -v` + migrate + `up -d` + `ps`, all service pytests, E2E test, Real data leakage audit | **DONE** | 13/13 containers Up & healthy; Pytest passed on all 9 services + E2E fixture pipeline passed; Leakage audit completed on real Binance 1h/4h data. | Completed |
| **Item 1** | Prometheus `/metrics` on all services, Grafana dashboards, alert rules | **DONE** | Prometheus active targets up & scraping every 15s; Alert rules configured in `docker/alerts.yml`; Grafana dashboard provisioned in `docker/grafana/`. | Completed |
| **Item 2** | GitHub Actions CI workflow | **DONE** | `.github/workflows/ci.yml` with Ruff, Mypy, Mermaid syntax validator, Markdown link checker, Pytest matrix, E2E pipeline, and Docker build/Trivy scan. | Completed |
| **Item 3** | Backup & restore scripts + tested procedure | **DONE** | `scripts/backup.sh` and `scripts/restore.sh` executed via bash; SHA256 validated; pg_restore executed and row counts across all domain schemas verified. | Completed |
| **Item 4** | Advisory lock id as config, atomic check+reservation, concurrency test | **DONE** | `advisory_lock_id` configurable via `RISK_ADVISORY_LOCK_ID`; advisory lock & check & reservation serialized in single transaction; `test_concurrency.py` passed (2/2). | Completed |
| **Item 5** | Short-side fill and invalidation tests in signal-service | **DONE** | `test_short_signal_entry_fill` and `test_short_signal_invalidation_before_entry` implemented in `services/signal-service/tests/test_signal.py` (6/6 passed). | Completed |
| **Item 6** | Configurable DSR trial count with logged derivation | **DONE** | `get_dsr_trial_count()` in `services/training-service/evaluator.py` supports `DSR_TRIALS` env var with explicit derivation logging in leakage audit & evaluator. | Completed |
| **Item 7** | Dashboard reading from gateway API with honest empty states | **DONE** | `dashboard/lib/data.js` connects to gateway endpoints with fallback elimination; `PositionsView.jsx` and `OverviewView.jsx` render honest empty states; `ModelSystemView.jsx` displays model matrix with explicit Shadow / Disabled status. | Completed |

---

## Verification Test Summary

1. **Market Collector**: 5 passed (`tests/test_collector.py`)
2. **Feature Service**: 5 passed (`tests/test_features.py`)
3. **Model Service**: 3 passed (`tests/test_model.py`)
4. **Training Service**: 8 passed (`tests/test_training.py`, `tests/test_feature_parity.py`)
5. **Risk Service**: 8 passed (`tests/test_risk.py`, `tests/test_concurrency.py`)
6. **Signal Service**: 6 passed (`tests/test_signal.py`)
7. **Paper Execution Service**: 3 passed (`tests/test_paper_exec.py`)
8. **API Gateway**: 1 passed (`tests/test_gateway.py`)
9. **Notifier Service**: 1 passed (`tests/test_notifier.py`)
10. **End-to-End Pipeline**: 1 passed (`tests/test_e2e_pipeline.py`)
11. **Leakage Audit on Real Binance Data**: Completed on real 1h and 4h historical bars for BTCUSDT and ETHUSDT. All gates respected (zero promotion to champion).
