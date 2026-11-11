# Phase 6.5 & Phase 6.6 - Progress Tracker

**Scope**: Crypto futures paper trading & research only. Strictly no exchange private keys, no real order execution.
**Champion & Challenger Policy**: Zero models promoted to champion. Zero models promoted to challenger. Dashboard and API gateway honestly display "No validated model".

---

## Phase 6.6 Execution Matrix (Evaluation Reconciliation)

| Item | Task Description | Status | Verification Evidence / Command Output Summary | Next Step |
| :--- | :--- | :---: | :--- | :--- |
| **0** | Clean up jobs, backup DB, remove seeded test rows, scratch DB setup | **DONE** | Removed exited container `signals-migrator-1`; created `backups/signals_20261110_165241.dump`; queried & showed 1 row in `models`, 3 in `signals`, 2 in `paper_trades`, 2 in `outbox`; deleted only those test rows; created `trade_ai_scratch` database for isolated restore testing. | Completed |
| **1** | Unified evaluation function & threshold config | **DONE** | Unified into `run_unified_evaluation` and `UnifiedThresholdConfig` in `evaluator.py`, shared identically by funnel, `batch_runner.py`, and `leakage_audit.py`. Explained 0.52/0.50 vs 0.55/0.60 discrepancy: uncalibrated raw GBDT probabilities reached 0.52-0.70 producing 16/65/183/15 trades, whereas `CalibratedClassifierCV` correctly maps to empirical base rate (~31%), where probabilities never reach 0.55. | Completed |
| **2** | Detailed reporting & Sharpe audit for BTC/ETH 1h/4h | **DONE** | Empirical base rates documented: TP hit first (+2 ATR) = 31.4-32.2%, SL hit first (-1 ATR) = 66.8-67.9%, Time exits = 0.4-1.4%. Probability histogram: 100% of calibrated holdout probabilities lie within [0.20, 0.40). Audited Sharpe: proved earlier -7 to -16 values resulted from multiplying per-trade returns by $\sqrt{8760}$ (assuming 8,760 trades/year instead of actual ~1-5 trades/year). Implemented proper per-trade and annualized frequency Sharpe. | Completed |
| **3** | Break-even derived probability gate | **DONE** | Derived mathematical gate $p^* = \frac{\text{SL} + \text{friction}}{\text{TP} + \text{SL}} = \frac{0.015 + 0.0014}{0.030 + 0.015} = 0.3644$. Implemented `select_thresholds_inner_fold` centered around $p^*$; evaluated on holdout strictly once, reporting untouched results. | Completed |
| **4** | Holdout window specification | **DONE** | Standardized to exactly 20% most recent bars after 200-bar warmup and 24-bar embargo across both `trainer.py` / `batch_runner.py` and `leakage_audit.py`. | Completed |
| **5** | Re-audit full history | **DONE** | Executed `leakage_audit.py` and `batch_runner.py` on all 51,366 bars (1h) and 12,841 bars (4h). Label shuffle passed (EV collapsed to -0.10% to -0.12%, matching -friction). 1-bar lag test noted base EV <= 0 (no positive predictive edge; confirmed no lookahead leak). 2x cost stress tested at 28 bps. DSR computed with 100 true trials. All models failed promotion gates; zero models promoted. | Completed |
| **6** | Funding history & Binance onboarding audit | **DONE** | Backfilled 6,420 funding records per symbol (6,495 for SOL) from 2021-01-01 to present with `startTime` pagination; audited all 8 symbols against `onboardDate` via Binance exchangeInfo (all onboarded 2019-2020); verified 0 zero-volume bars and 0 flat bars across 51,352 (1h) and 12,838 (4h) candles; fixed labeling funding accrual to scale by timeframe (8 bars/8h for 1h, 2 bars/8h for 4h) with 1 bp/8h fallback for unprovided/flat funding. | Completed |
| **7** | Reconcile test count (40 vs 41) | **DONE** | Exact audit: 40 service unit/integration tests across 9 microservices + 1 E2E pipeline integration test (`test_e2e_pipeline.py`) = 41 total production CI tests. Explained the earlier off-by-one arithmetic slip where the heading said 40 while the itemized list actually contained 41 tests (1+5+5+3+1+3+8+6+8+1 = 41). Root legacy unit tests (21 tests) accounted for separately. | Completed |
| **8** | Migrator cleanup & single sequential invocation | **DONE** | Root-cause found: 9 microservices depend on `migrator: condition: service_completed_successfully`, accumulating log lines across repeated compose triggers on an already-migrated database. Fixed `env.py` to retrieve and print `current revision: <id>` at migration completion; verified single sequential invocation, single `alembic_version` table, and non-zero exit on error. | Completed |

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

## Complete Test Suite Reconciliation (41 Tests Total)

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

**Grand Total**: 41 production unit and integration tests passing across all services (40 service tests + 1 E2E pipeline test). Separately, 21 standalone prototype unit tests exist in root `tests/`.
