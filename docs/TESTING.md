# Testing Strategy & Automated Test Suite

> **CI Test Count**: **62 Automated Tests Total** (41 Backend Python Tests + 21 Frontend Node Tests).
> **Execution Environment**: Tests execute inside isolated Docker containers or via local pytest/npm runners.

---

## 1. Test Suite Breakdown by Microservice

### Backend Python Tests (41 Tests):
1. **`market-collector` (5 tests)**:
   - `test_rate_limit_budgeter`: Verifies IP weight budget tracking under load.
   - `test_parse_kline_row`: Confirms correct numeric casting of Binance kline arrays.
   - `test_ws_mark_price_handling`: Validates mark price tick ingestion.
   - `test_ws_kline_unclosed_vs_closed`: Ensures unclosed candles are filtered out.
   - `test_health_endpoint`: Checks `/health` probe response.
2. **`feature-service` (5 tests)**:
   - `test_ta_indicators`: Verifies numerical accuracy of EMA, RSI, MACD, ATR, Bollinger Bands.
   - `test_derivatives_and_cross_asset`: Validates BTC rolling correlation and volatility regimes.
   - `test_unified_pipeline_no_lookahead`: Confirms feature matrix is strictly causal.
   - `test_feature_consumer_handles_candle_closed`: Verifies stream consumption.
   - `test_feature_service_health`: Checks `/health` probe.
3. **`model-service` (3 tests)**:
   - `test_inference_execution`: Tests LightGBM forward inference and Platt scaling.
   - `test_consumer_champion_and_shadow_challenger`: Tests dual champion/shadow prediction routing.
   - `test_model_service_health`: Checks `/health` probe.
4. **`training-service` (1 test)**:
   - `test_training_pipeline_gates`: Evaluates promotion gate logic on positive/negative metrics.
5. **`risk-service` (3 tests)**:
   - `test_risk_sizing_calculation`: Validates fixed-fractional ATR sizing and leverage cap.
   - `test_cost_to_risk_gate`: Verifies rejection when friction exceeds 20% of stop distance.
   - `test_risk_service_health`: Checks `/health` probe.
6. **`signal-service` (8 tests + 21 lifecycle tests ported)**:
   - `test_create_signal_from_approved`: Inserts signal with status `waiting_for_entry`.
   - `test_optimistic_locking_version_increment`: Validates atomic `version` column increments.
   - `test_optimistic_lock_collision_rejection`: Confirms collision returns False on stale version.
   - `test_invalid_transition_rejected`: Verifies state machine rejects forbidden transitions.
   - `test_get_active_signals`: Verifies filtering of non-terminal signals.
   - `test_handle_trade_closed_syncs_ledger`: Verifies single-owner synchronization with paper-exec.
   - `test_signal_service_health`: Checks `/health` probe.
7. **`paper-exec-service` (3 tests)**:
   - `test_order_fill_simulation`: Verifies limit order fill mechanics at entry price $C_t$.
   - `test_sl_first_ambiguity_rule`: Confirms Stop Loss is strictly executed on dual-barrier touch.
   - `test_paper_exec_health`: Checks `/health` probe.
8. **`api-gateway` (6 tests)**:
   - `test_health_endpoint`: Verifies gateway `/health` and Redis connection flag.
   - `test_status_endpoint_no_champion`: Confirms honest "No validated model" state banner.
   - `test_signals_endpoint_waiting_states`: Confirms unconfirmed waiting placeholders.
   - `test_summary_endpoint`: Validates virtual paper balance calculations.
   - `test_history_endpoint`: Tests trade history retrieval.
   - `test_sse_heartbeat_and_headers`: Verifies SSE stream format and 15s heartbeats.
9. **`notifier-service` (1 test)**:
   - `test_notifier_service_health`: Checks `/health` probe.
10. **End-to-End Recorded Fixture Integration Pipeline (1 test)**:
    - `tests/test_e2e_pipeline.py`: Traces an end-to-end signal from prediction -> risk sizing -> state transition -> paper limit fill -> SL-first mark price exit.

### Frontend Node Tests (21 Tests):
- **`dashboard/tests/signal_lifecycle.test.mjs`**: 21 unit and contract tests verifying signal card rendering, optimistic UI state updates, formatters, and SSE event handlers.

---

## 2. Test Execution Commands

### Running Microservice Tests via Docker:

**PowerShell (Windows)**:
```powershell
docker compose run --rm market-collector pytest services/market-collector/tests
docker compose run --rm feature-service pytest services/feature-service/tests
docker compose run --rm model-service pytest services/model-service/tests
docker compose run --rm training-service pytest services/training-service/tests
docker compose run --rm risk-service pytest services/risk-service/tests
docker compose run --rm signal-service pytest services/signal-service/tests
docker compose run --rm paper-exec-service pytest services/paper-exec-service/tests
docker compose run --rm api-gateway pytest services/api-gateway/tests
docker compose run --rm notifier-service pytest services/notifier-service/tests

# End-to-End Integration Pipeline Test
docker compose run --rm training-service pytest tests/test_e2e_pipeline.py

# Frontend Contract Tests
docker compose run --rm dashboard npm test
```

---

## 3. Specialized Quantitative & Concurrency Tests

### 1. Leakage & Robustness Audit Suite:
Executes the 5-step institutional audit (Platt calibration, label shuffle, 1-bar lag, 2x cost stress, lookahead verification):
```powershell
docker compose run --rm -v ${PWD}:/app -w /app/services/training-service training-service python leakage_audit.py
```

### 2. Scratch Determinism & Checksum Verification:
Trains models twice from scratch with fixed seed (`42`) and verifies bitwise identical SHA256 hashes:
```powershell
docker compose run --rm -v ${PWD}:/app -w /app/services/training-service training-service python verify_determinism.py
```

### 3. Null Test (20 Seeds Label-Shuffle & Random Probs):
Runs the Monte Carlo null pipeline across 20 seeds to confirm expected median $\text{Sharpe} \le 0.0$ and $\text{PBO} \approx 0.50$:
```powershell
docker compose run --rm -v ${PWD}:/app -w /app/services/training-service training-service python null_test.py
```

### 4. Advisory Lock Concurrency Test:
Simulates concurrent risk evaluations across parallel coroutines to verify `pg_advisory_xact_lock`:
```powershell
docker compose run --rm risk-service pytest services/risk-service/tests/test_concurrency.py
```

