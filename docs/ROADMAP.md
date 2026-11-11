# Project Roadmap, Known Limitations & Quantitative Research Directions

> **Operational Scope**: Crypto futures paper trading & research only.
> **Current Champion Status**: No validated model. All models rejected under strict promotion gates.

---

## 1. Completed Engineering Milestones

### Phase 1–3: Core Distributed Infrastructure
- [x] Decomposed monolithic backend into 9 containerized Python 3.11 FastAPI microservices.
- [x] Established Redis 7 Streams message bus with consumer groups, automatic acknowledgements, and Dead-Letter Queue (`system.dlq`).
- [x] Provisioned TimescaleDB PostgreSQL 16 hypertables with 30-day chunking and automatic compression across 6 domain schemas.
- [x] Unified Alembic database migrations runner (`libs/database/migrations/`).
- [x] Implemented Next.js 14 read-only web dashboard with dark/light themes, pure SVG candlestick charts, and multiplexed SSE live ticker streaming.

### Phase 4–6: Quantitative Governance & Verification
- [x] Integrated Marcos López de Prado's Combinatorial Purged Cross-Validation (CPCV) with sample uniqueness weighting.
- [x] Implemented Platt scaling (`CalibratedClassifierCV`) mapping raw GBDT outputs to empirical base rates.
- [x] Backfilled 3+ years of continuous Binance USD-M Futures 1h and 4h klines (51,366 bars) and funding rates (6,420 records) across 8 perpetual pairs.
- [x] Implemented dynamic per-setup break-even probability gate $p^* = \frac{\text{SL} + \text{cost}}{\text{TP} + \text{SL}}$ derived from bar ATR%.
- [x] Enforced inner-fold threshold optimization to eliminate holdout leakage.
- [x] Built the quantitative trial registry in `model_registry.experiments` for dynamic Deflated Sharpe Ratio ($N_{\text{trials}} = 208+$).
- [x] Executed 20-seed Monte Carlo null tests (label-shuffle and random probabilities), proving zero leakage ($\text{Sharpe} \le 0$, $\text{PBO} \approx 0.50$).
- [x] Established single-owner position exit architecture in `paper-exec-service` with conservative Stop-Loss-first rule.
- [x] Maintained honest "No validated model" state across all systems after 100% of candidate models were rejected by promotion gates.

---

## 2. Current Known Limitations

1. **Zero Promoted Models**: No candidate model has satisfied all six promotion criteria on the untouched historical holdout window. As a consequence, live paper trading signal execution remains disengaged.
2. **Dump-Only Backups**: Database disaster recovery relies on logical snapshots (`pg_dump -Fc`). Continuous WAL archiving and Point-in-Time Recovery (PITR) are not configured.
3. **Restricted Scope**: System is constrained strictly to 8 Binance USD-M perpetual futures pairs (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `LINKUSDT`, `TRXUSDT`) on `1h` and `4h` timeframes. The `15m` timeframe is formally suppressed due to excessive fee-to-risk drag.
4. **Network Exposure Finding**: `dashboard` (:3000) and `api-gateway` (:8000) bind to `0.0.0.0` rather than `127.0.0.1` by default.

---

## 3. Quantitative Research Directions (Edge Discovery)

Because the current technical indicator feature set failed to produce a statistically verifiable holdout edge under conservative friction accounting (14 bps) and realistic limit-order fills, quantitative research must explore new feature spaces:

### 1. Order Flow Imbalance & Microstructure
- Ingest Binance Futures Depth streams (`@depth20@100ms`).
- Compute Level-2 order book bid/ask volume imbalance, cumulative volume delta (CVD), and micro-price drift.
- Explore whether high-frequency order flow imbalance signals can predict short-term directional pressure on 1h bars.

### 2. Cross-Sectional Momentum & Relative Value
- Shift from single-asset time-series prediction to cross-sectional rank models:
  - Rank the 8 perpetuals by 24h/72h relative momentum and funding rate basis.
  - Long the highest-momentum asset while hedging against the lowest-momentum asset (market-neutral crypto statistical arbitrage).

### 3. Alternative Labeling Horizons & Targets
- Triple-barrier with 2.0x ATR targets may be too wide for mean-reverting regimes.
- Research volatility-normalized continuous return targets or fixed 12-bar forward returns with Ridge regression / Huber loss.

### 4. Continuous Shadow Forward Monitoring
- Enroll candidate models into `model_registry.shadow_predictions` to record out-of-sample forward predictions on live incoming market ticks for 60+ days without capital allocation.
