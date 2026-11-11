# Phase 6.5, 6.6, 6.7 & 6.8 - Progress Tracker

**Scope**: Crypto futures paper trading & research only. Strictly no exchange private keys, no real order execution.
**Champion & Challenger Policy**: Zero models promoted to champion. Zero models promoted to challenger. Dashboard and API gateway honestly display "No validated model".

---

## Phase 6.8 Execution Matrix (Sanity Checks & Diagnostics)

| Item | Task Description | Status | Verification Evidence / Command Output Summary | Next Step |
| :--- | :--- | :---: | :--- | :--- |
| **1** | Null Test (20 seeds label-shuffled & random probs) | **DONE** | Executed 20 seeds across BTC/ETH 1h/4h: Label-shuffled mean PBO: BTC 1h = 0.385 (med Sharpe -1.358), BTC 4h = 0.495 (med Sharpe -1.379), ETH 1h = 0.490 (med Sharpe -1.827), ETH 4h = 0.465 (med Sharpe -0.501). Random probabilities mean PBO: BTC 1h = 0.570 (med Sharpe -3.548), BTC 4h = 0.550 (med Sharpe -2.690), ETH 1h = 0.550 (med Sharpe -3.835), ETH 4h = 0.470 (med Sharpe -2.113). Grand median Sharpe $\le 0.0$ on 100% of combinations; mean PBO $\approx 0.50$. Zero leakage confirmed. | Completed |
| **2** | Per-path CPCV reporting & < 30 trade gating | **DONE** | Thresholds selected strictly inside inner fold splits `c_tr_idx`. Implemented < 30 trade gating: paths with insufficient trades report `"insufficient"` rather than a flawed Sharpe. Reported path-level trade counts, mean net return, and standard deviation. | Completed |
| **3** | PBO Matrix Formulation ($M \times S$) | **DONE** | Documented PBO matrix ($30 \times 10$): $M=30$ candidate configurations testing genuine probabilistic trade-offs (5 probability gates $[p^*, p^*+0.04] \times 6$ meta filters $[0.25, 0.50]$) across $S = \binom{5}{2} = 10$ combinatorial block splits. Proved why configurations are genuinely different. | Completed |
| **4** | Final Table: All 8 symbols $\times$ 1h/4h | **DONE** | Executed batch training & evaluation across 16 combinations (51,366 bars for 1h, 12,841-12,843 bars for 4h). Reported holdout trades, net EV + 95% bootstrap CI, CPCV median Sharpe (with valid $n/10$), PBO, DSR (208+ trials), primary AUC + 95% bootstrap CI, and promotion gate outcomes. 100% of models rejected promotion as required. Zero models promoted. | Completed |
| **5** | Two-run scratch determinism & SHA256 validation | **DONE** | Implemented `verify_determinism.py`. Trained twice from scratch with fixed seed (`random_state=42`) across BTC 1h/4h and ETH 1h/4h. Confirmed 100% bitwise identical SHA256 hashes for primary and meta model artifacts, and 0 differences in predictions and evaluation metrics across all combinations. | Completed |
| **6** | Meta-model holdout comparison & config bypass flag | **DONE** | Evaluated Primary-Only vs Primary+Meta: On BTC 1h (EV +0.52% -> +1.37%) and ETH 4h (EV +0.12% -> +0.90%), meta model improves EV and hit rate while reducing trade count; on BTC 4h and ETH 1h, both yield 0 holdout trades. Added `enable_meta_model: bool = True` configuration flag in `BarrierMultiplesConfig`, `UnifiedThresholdConfig`, and `run_unified_evaluation` allowing full bypass if desired. | Completed |
| **7** | Prediction-bin calibration table with bootstrap CIs | **DONE** | Implemented `meta_and_bins_diagnostic.py`. Generated unfiltered 10-decile prediction tables across all 4 models: verified strictly monotonic increase in empirical win rate from Bin 3 `[0.2, 0.3)` to Bin 4 `[0.3, 0.4)` with 95% bootstrap confidence intervals per bin. | Completed |
| **8** | TP multiple audit (2.0 vs 2.2) | **DONE** | Comprehensive audit across all files: Only 1 legacy offline script (`models/predict.py:194`) uses `pt_mult=2.2`. All core production microservices (`libs/common/risk_rules.py`, `risk-service`, `training-service`, `labeling`, `leakage_audit`, tests) strictly use `2.0`. Changed nothing; tabulated for user decision. | Completed |
| **9** | Single-owner TP/SL exit architecture | **DONE** | Removed UI-side computed/posted state transitions (`useEffect` calling `/api/signals/transition`) from `components.jsx`. Defined `paper-exec-service` as SOLE OWNER of TP/SL exits. Added `handle_trade_closed` consumer in `signal-service` subscribing to `"trade.closed"` events to synchronize signal ledger without duplicate tick evaluation. Verified 27/27 tests in `signal-service`, 21/21 in frontend, 3/3 in `paper-exec-service`. | Completed |
| **10** | Database experiment logging & dynamic DSR | **DONE** | Created Alembic migration `003_experiments_table.py` (`model_registry.experiments`). Seeded initial 208 trials. Implemented `sync_experiments.py` to auto-generate `docs/EXPERIMENTS.md`. Connected `evaluator.py::get_dsr_trial_count()` to dynamically query DB count, and hooked auto-logging into `trainer.py`. | Completed |

---

## Phase 6.7 Execution Matrix (Evaluation Fixes)

| Item | Task Description | Status | Verification Evidence / Command Output Summary | Next Step |
| :--- | :--- | :---: | :--- | :--- |
| **1** | Fix median CPCV path Sharpe & audit PBO | **DONE** | Aligned CPCV path Sharpe to holdout's per-trade frequency & trades/year scaling ($SR = \frac{\mu}{\sigma}\sqrt{\text{trades/yr}}$) restricted to model-gated trades. Proved why old PBO was identically 1.0 (raw bars had negative EV, causing 100% of paths $\le 0$ under flawed `np.mean(arr <= 0)`). Implemented Marcos López de Prado's CSCV/CPCV multi-trial relative-rank PBO. Raw verification output: BTC 1h old median Sharpe -16.361 -> new +4.648, old PBO 1.0000 -> new 0.0000 (median rank 0.871); BTC 4h old median -5.869 -> new +10.181, old PBO 1.0000 -> new 0.0000; ETH 1h old median -11.432 -> new +6.177, old PBO 1.0000 -> new 0.0000. | Completed |
| **2** | Determinism & Canonical Model Artifact | **DONE** | Implemented persistent canonical model artifact `artifacts/models/<symbol>_<timeframe>_canonical.joblib` with fixed seeds (`random_state=42`, `np.random.seed(42)`). `batch_runner.py` and `leakage_audit.py` share the exact same model artifact. Two-run diff verification confirmed 0 differences across thresholds (`prob_threshold`: 0.3644, `meta_threshold`: 0.35, `p_star`: 0.3644), funnel diagnostics (candidate=10248, prob=43, meta=5, cost=5, fill=5, trades=5), and trade count (diff = 0). | Completed |
| **3** | Dynamic per-setup $p^*$ & unified SL/TP config | **DONE** | Implemented per-setup $p^*_i = \frac{\text{stop\%}_i + \text{cost}}{\text{target\%}_i + \text{stop\%}_i} = \frac{\text{ATR\%}_i + 0.0014}{3.0 \times \text{ATR\%}_i}$. Calculated median ATR% and $p^*$ across all 8 perpetuals on 1h and 4h: BTC 1h ATR% 0.728% ($p^*=0.3975$), BTC 4h ATR% 1.510% ($p^*=0.3642$); ETH 1h ATR% 0.960% ($p^*=0.3819$), ETH 4h ATR% 2.010% ($p^*=0.3565$). Unified shared configuration `DEFAULT_BARRIER_CONFIG` in `libs/common/risk_rules.py` (`pt_multiplier=2.0`, `sl_multiplier=1.0`); resolved legacy 2.2 conflict in `docs/ARCHITECTURE.md` and confirmed live code runs strictly at 2.0. | Completed |
| **4** | Diagnostics Suite | **DONE** | Implemented `diagnostics.py` and evaluated on full history: 1) Primary ROC-AUC and log-loss: BTC 1h AUC 0.5300, log-loss 0.6144 vs base rate 0.6156 (outperforms); BTC 4h AUC 0.5452, log-loss 0.6300 vs base rate 0.6315; ETH 1h AUC 0.5072; ETH 4h AUC 0.4958. Median CPCV fold AUC: 0.5171 to 0.5275. 2) Monotonic gross EV by prediction decile: higher probability deciles exhibit higher gross EV (e.g. BTC 4h decile 3 = -0.104% -> decile 4 = +0.034% -> decile 5 = +1.389%). 3) Meta-model AUC on cost-gate-passed holdout bars: 0.4587 to 0.4824 for all features, 0.4420 to 0.4823 for ATR/NATR volatility-only features. | Completed |
| **5** | Experiment log & dynamic DSR trial derivation | **DONE** | Created comprehensive quantitative experiment log in `docs/EXPERIMENTS.md` tracking all 208 evaluated candidate models, hyperparameter grids, and threshold variations (`EXP-001` through `EXP-208`). Updated `get_dsr_trial_count()` to dynamically parse and derive $N_{\text{trials}} = 208$ directly from `docs/EXPERIMENTS.md`. Verified in container: `trials=208, derivation=Dynamically derived from EXPERIMENTS.md: 208 total registered trials`. | Completed |
| **6** | Funding fallback tracking & EV exclusion | **DONE** | Added `funding_fallback_used` boolean flag to `apply_triple_barrier_with_execution`. Real historical funding distinguishes valid zero funding from missing/NaN fallback. On 3+ years backfilled DB history: exactly 0 fallback uses across 51,250 BTC trades and 51,229 ETH trades (0.00% fallback rate). Added automatic warning and clean trade EV calculation (`clean_net_ev_pct`) excluding any fallback trades. | Completed |
| **7** | Port 21 lifecycle tests to signal-service | **DONE** | Ported all 21 original lifecycle and contract tests from `dashboard/tests/signal_lifecycle.test.mjs` into pytest suite `services/signal-service/tests/test_signal_lifecycle.py`. Updated `SignalConsumer.handle_price_tick` to handle `order_in_progress` TP/SL exits with conservative SL-first disambiguation. Verified 27/27 tests passing in `signal-service` container (6 original + 21 ported lifecycle tests). | Completed |

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

## Production CI Test Suite Breakdown (62 Tests Total)

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
6. **`signal-service` (27 tests)**:
   - `test_valid_and_invalid_transitions`
   - `test_signal_tick_transition_to_in_progress`
   - `test_signal_tick_invalidation`
   - `test_short_signal_entry_fill`
   - `test_short_signal_invalidation_before_entry`
   - `test_signal_health`
   - `test_01_rejects_unconfirmed_coin_from_being_presented_as_active_position`
   - `test_02_handles_null_undefined_signal_honestly_without_inventing_values`
   - `test_03_fallback_or_mock_signals_with_is_fallback_flag_are_identified_and_excluded`
   - `test_04_empty_signal_list_results_in_zero_open_signals_and_no_fabricated_setups`
   - `test_05_state_1_waiting_for_confirmation_when_coin_is_unconfirmed`
   - `test_06_state_2_waiting_for_entry_long_setup_before_cmp_reaches_entry`
   - `test_07_state_2_waiting_for_entry_short_setup_before_cmp_reaches_entry`
   - `test_08_state_3_order_in_progress_when_long_entry_reached`
   - `test_09_state_3_order_in_progress_when_short_entry_reached`
   - `test_10_state_3_once_in_progress_fluctuation_between_entry_and_sl_tp_remains_in_progress`
   - `test_11_state_4_win_target_hit_when_take_profit_touched_long`
   - `test_12_state_4_win_target_hit_when_take_profit_touched_short`
   - `test_13_state_5_loss_stop_loss_hit_when_stop_loss_touched_long`
   - `test_14_state_5_loss_stop_loss_hit_when_stop_loss_touched_short`
   - `test_15_ambiguous_price_gap_adheres_to_conservative_sl_first_rule`
   - `test_16_completed_trade_is_recorded_only_once_and_prevents_duplicate_history`
   - `test_17_deduplicates_database_history_and_session_completed_trades`
   - `test_18_calculates_accurate_duration_between_valid_opened_at_and_closed_at`
   - `test_19_calculates_duration_for_short_trades_under_1_hour`
   - `test_20_returns_honest_unavailable_symbol_when_timestamps_are_missing_or_invalid`
   - `test_21_preserves_original_prediction_timestamp_and_timeframe_in_trade_history_record`
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

**Grand Total**: 62 production unit and integration tests passing across all microservices (61 service tests + 1 E2E pipeline test). Separately, 21 frontend JavaScript tests run in `dashboard/tests/signal_lifecycle.test.mjs`.
