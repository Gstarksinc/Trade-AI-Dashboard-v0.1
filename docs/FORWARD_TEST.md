# Forward Testing & Shadow Execution Specification

> **Scope**: Crypto futures paper trading & research only.
> **Current Status**: ⚠️ **FORWARD TESTING NOT STARTED**.
> **Precondition Status**: Zero models passed historical promotion gates. Active forward testing is disengaged.

---

## 1. Forward Testing Entry Criteria

Before any candidate model can be activated for paper-trading forward testing, it must satisfy all institutional entry requirements:

1. **Gatekeeper Clearance**: Passed all six empirical promotion gates on the untouched historical holdout window (Minimum 20 trades, positive Net EV with bootstrap CI lower bound $> 0$, CPCV median Sharpe $> 0$, PBO $< 0.50$, ECE $\le 0.12$, DSR $> 0.95$).
2. **Leakage Audit Certification**: Verified zero-leakage certification across label shuffling, random probability baseline tests, and 1-bar feature lag degradation tests.
3. **Artifact Integrity**: Deterministic training reproducibility confirmed with matching SHA256 artifact checksums.
4. **Registry Enrollment**: Explicitly enrolled in `model_registry.models` with `stage = 'challenger'` or `stage = 'champion'`.

---

## 2. Shadow Execution Tracking Architecture

Once a model achieves Challenger promotion, forward testing is executed via **Shadow Execution Mode**:

```
[Binance WS Tick Feed] ──► market-collector ──► feature-service
                                                       │
                                                       ▼
                                                 model-service
                                                       │
                           ┌───────────────────────────┴───────────────────────────┐
                           ▼                                                       ▼
                    Champion Model                                          Challenger Model
                    (Paper Capital Allocated)                               (Shadow Execution)
                    Stream: prediction.ready                                Table: model_registry.shadow_predictions
                    Executes via risk-service                               ZERO CAPITAL RISK
```

### Shadow Tracking Methodology:
1. **Zero Capital Allocation**: Shadow models produce predictions on live closed candles, but their predictions are tagged `is_shadow = True` and never routed to `risk-service` for margin reservation.
2. **Persistence**: Every shadow prediction is logged to `model_registry.shadow_predictions` with columns:
   - `model_version`, `symbol`, `timeframe`, `candle_open_time`, `direction`, `probability`, `meta_probability`, `current_price`, `created_at`.
3. **Synthetic PnL Tracking**: A dedicated background evaluator tracks subsequent price ticks over 24 bars, recording whether Take Profit or Stop Loss would have triggered.
4. **Comparison Horizon**: A challenger must run in shadow mode for a minimum of **30 consecutive days** and execute at least **50 shadow trades** while maintaining a positive Net Sharpe ratio before being eligible for champion replacement.

---

## 3. Current Operational Status: DISENGAGED

```
================================================================================
FORWARD TESTING ENGAGEMENT STATUS: DISENGAGED
================================================================================
Active Champions in Registry:    0
Active Challengers in Registry:  0
Live Forward Test Instances:     None
Shadow Predictions Log:          0 active streams
API Gateway Status Notice:       "No validated model. Zero models promoted."
================================================================================
```

### Next Steps to Activate Forward Testing:
1. Refine quantitative feature engineering (e.g. order-book imbalance, funding rate term structure, cross-sectional momentum).
2. Execute a new training run via `training-service` with logged experiment tracking.
3. Once a candidate passes all six promotion gates, enroll the artifact into `model_registry.models` as `'challenger'`, triggering automatic shadow execution.
