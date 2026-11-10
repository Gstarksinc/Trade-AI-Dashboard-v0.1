# Phase 6.5 - Data and Audit Repair Progress Tracker

**Scope**: Crypto futures paper trading & research only. Strictly no exchange private keys, no real order execution.
**Champion & Challenger Policy**: Zero models promoted to champion. Zero models promoted to challenger. Dashboard and API gateway honestly display "No validated model".

---

## Phase 6.5 Execution Matrix

| Item | Task Description | Status | Verification Evidence / Command Output Summary | Next Step |
| :--- | :--- | :---: | :--- | :--- |
| **1** | Invalidate earlier 24-combination results table & document origin | **DONE** | Invalidation notice placed in `VALIDATION_REPORT.md`. Documented that earlier results originated from unit-test fixtures/synthetic mocks and an unbackfilled 1,000-bar sample. | Completed |
| **2** | Backfill 3+ years of 1h/4h klines and funding history for 8 perpetuals | **DONE** | 51,350 bars per symbol (1h) and 12,837 bars (4h) backfilled into TimescaleDB with 0 gaps; 2,919 funding records per symbol; short-history features (OI, LSR) excluded from training. | Completed |
| **3** | Add Funnel Diagnostics | **DONE** | Funnel tracking implemented in `leakage_audit.py` and `batch_runner.py`: candidate bars -> prob gate -> meta gate -> cost gate -> limit fill -> executed trades. | Completed |
| **4** | Investigate ETH 4h feature-lag failure | **DONE** | Identified that earlier 1,000-bar test forced unconditional trading on every bar, causing whipsaws under 1-bar lag. On complete 12,837-bar dataset with selective gating, feature-lag test passed with expected 6 bps decay. | Completed |
| **5** | Rerun leakage audit & batch runner on full history | **DONE** | Re-audit completed across all 51,350 bars for BTC/ETH 1h and 12,837 bars for 4h. All models failed promotion gates (PBO=1.0, CPCV Sharpe < 0). No models promoted. | Completed |
| **6** | Model status honesty | **DONE** | `model_registry.models` has 0 promoted models. Gateway `/status` and Dashboard `ModelSystemView.jsx` render honest "No validated model" state with amber badge. | Completed |
| **7** | Verification fixes, healthchecks, test reconciliation | **DONE** | Healthchecks added to all services in `docker-compose.yml`; 13/13 containers report `healthy` in `docker compose ps`; `/health` verified on each port; 40 unit/integration tests reconciled; `signals_ledger` row origin documented. | Completed |
| **8** | Tested backup and clean restore into fresh database | **DONE** | Dump taken with full TimescaleDB hypertables (24.8 MB); restored into fresh database `trade_ai_fresh`; verified 100% row-for-row match across all domain tables; dump-only limitation plainly stated. | Completed |
| **9** | Reconcile service counts across all documentation | **DONE** | Standardized to exactly 9 containerized Python 3.11 FastAPI microservices + 1 Next.js 14 Web Dashboard + 2 storage tiers (TimescaleDB, Redis) + Prometheus/Grafana. | Completed |

---

## Complete Test Suite Reconciliation (40 Tests Total)

1. **`market-collector` (5 tests)**:
   - `test_rate_limit_budgeter`
   - `test_parse_kline_row`
   - `test_ws_mark_price_handling`
   - `test_ws_kline_unclosed_vs_closed`
   - `test_health_endpoint`
2. **`feature-service` (5 tests)**:
   - `test_ta_indicators`
   - `test_derivatives_and_cross_asset`
   - `test_unified_pipeline_no_lookahead`
   - `test_feature_consumer_handles_candle_closed`
   - `test_feature_service_health`
3. **`model-service` (3 tests)**:
   - `test_inference_execution`
   - `test_consumer_champion_and_shadow_challenger`
   - `test_model_service_health`
4. **`training-service` (8 tests)**:
   - `test_training_serving_feature_parity`
   - `test_artifact_sha256_checksum`
   - `test_triple_barrier_conservative_sl_first_and_execution`
   - `test_sample_uniqueness_weights`
   - `test_purged_cross_validation_embargo_ge_max_holding`
   - `test_promotion_gates_evaluation`
   - `test_psi_drift_calculation`
   - `test_training_health`
5. **`risk-service` (8 tests)**:
   - `test_parallel_risk_evaluations_respect_caps`
   - `test_portfolio_total_cap_concurrency`
   - `test_correlation_clusters`
   - `test_stale_data_rejection`
   - `test_volatility_shock_rejection`
   - `test_cost_to_risk_rejection`
   - `test_successful_approval_and_sizing`
   - `test_risk_health`
6. **`signal-service` (6 tests)**:
   - `test_valid_and_invalid_transitions`
   - `test_signal_tick_transition_to_in_progress`
   - `test_signal_tick_invalidation`
   - `test_short_signal_entry_fill`
   - `test_short_signal_invalidation_before_entry`
   - `test_signal_health`
7. **`paper-exec-service` (3 tests)**:
   - `test_evaluate_tick_exits_long_conservative_sl_first`
   - `test_evaluate_tick_exits_short_side_verification`
   - `test_paper_exec_health`
8. **`api-gateway` (1 test)**:
   - `test_gateway_health`
9. **`notifier-service` (1 test)**:
   - `test_notifier_health`
10. **End-to-End Pipeline Fixture (1 test)**:
    - `test_e2e_signal_to_execution_flow`

**Grand Total**: 40 unit and integration tests passing across all services.
