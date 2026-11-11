# System Workflow & End-to-End Event Lifecycle

> **Scope**: Crypto futures paper trading & quantitative research only.
> **Integrity Rule**: Real production data and recorded test fixtures are clearly differentiated.

---

## 1. Numbered End-to-End Operational Workflow

The real-time live trading pipeline progresses through nine coordinated phases across the event bus:

```
[Binance Futures WS/REST]
        │
   (1)  ▼
 market-collector (:8001)
        │
        │ Event: candle.closed
   (2)  ▼
 feature-service (:8002)
        │
        │ Event: features.ready
   (3)  ▼
 model-service (:8003)
        │
        │ Event: prediction.ready
   (4)  ▼
 risk-service (:8005) ──(Acquires RISK_ADVISORY_LOCK_ID: 888888)
        │
        │ Event: signal.approved (or signal.rejected)
   (5)  ▼
 signal-service (:8006) ──(Optimistic Lock Version Update)
        │
        │ Event: signal.state_changed (waiting_for_entry)
   (6)  ▼
 paper-exec-service (:8007) ──(Evaluates Limit Entry & SL-First Exits)
        │
        │ Event: trade.closed
   (7)  ▼
 signal-service (:8006) ──(Transitions to win_target_hit / loss_stop_loss_hit)
        │
   (8)  ▼
 api-gateway (:8000) ──(Multiplexed SSE Stream)
        │
   (9)  ▼
 Next.js 14 Dashboard (:3000) [Browser Client]
```

### Step 1: Market Data Ingestion (`market-collector`)
- Maintains public WebSocket connections to Binance USD-M Futures (`wss://fstream.binance.com/ws/!miniTicker@arr`).
- When a candle closes (e.g. `1h` or `4h`), pulls historical confirmation via Binance REST `/fapi/v1/klines`.
- Persists closed candle to hypertable `market_data.candles`.
- Emits event: `candle.closed` to Redis Stream `candle.closed`.
- Emits live price ticks to Redis Stream `price.tick` and caches `price:{symbol}` in Redis for zero-latency lookups.

### Step 2: Point-in-Time Feature Computation (`feature-service`)
- Consumes `candle.closed` from group `feature-service-group`.
- Loads closed historical bars strictly prior to or equal to candle close time (strictly causal, zero lookahead bias).
- Computes 48 features across technical indicators (EMA, RSI, MACD, ATR, NATR, Bollinger Bands, ADX) and cross-asset correlations (BTC rolling correlation).
- Persists feature vector into hypertable `feature_store.features`.
- Emits event: `features.ready` to Redis Stream `features.ready`.

### Step 3: Real-Time Model Inference (`model-service`)
- Consumes `features.ready` from group `model-service-group`.
- Queries `model_registry.models` for active models:
  - **Champion Model**: Evaluated for live paper trading.
  - **Shadow / Challenger Models**: Evaluated out-of-sample and logged to `model_registry.shadow_predictions` for continuous forward auditing.
- Computes calibrated primary probability $p \in [0, 1]$ via Platt scaling / isotonic calibration.
- Computes secondary Random Forest meta-confidence score $m \in [0, 1]$.
- Emits event: `prediction.ready` to Redis Stream `prediction.ready`.
- *Note: If no model is promoted to champion in `model_registry.models`, inference skips signal generation and the gateway renders "No validated model".*

### Step 4: Serialized Risk Evaluation & Capital Allocation (`risk-service`)
- Consumes `prediction.ready` from group `risk-service-group`.
- Begins a database transaction and acquires the PostgreSQL advisory lock:
  ```sql
  SELECT pg_advisory_xact_lock(888888);
  ```
- Evaluates risk checks atomically:
  1. **Cost-to-Risk Gate**: Rejects signal if round-trip friction (14 bps) exceeds 20% of stop-loss distance ($\frac{\text{friction}}{\text{SL distance}} > 0.20$).
  2. **Threshold Gate**: Compares calibrated $p$ against mathematically derived break-even $p^* = \frac{\text{SL} + \text{cost}}{\text{TP} + \text{SL}}$ and inner-fold probability threshold.
  3. **Circuit Breakers**: Verifies portfolio daily loss ceiling ($\le 3.0\%$) and trailing max drawdown ($\le 10.0\%$).
  4. **Portfolio & Cluster Caps**: Caps total portfolio margin exposure ($\le 100\%$) and correlated asset cluster exposure ($\le 30\%$).
  5. **Position Sizing**: Applies fixed-fractional ATR risk sizing (default 0.5% account equity risk, capped at 3.0x leverage).
  6. **Barrier Multiples**: Sets Take Profit at $+2.0 \times \text{ATR}$ and Stop Loss at $-1.0 \times \text{ATR}$ (1:2 R:R ratio).
- If approved, reserves virtual margin and emits `signal.approved`.
- If rejected, commits rejection reason and emits `signal.rejected`. Advisory lock is automatically released upon transaction commit.

### Step 5: Signal Ledger Registration (`signal-service`)
- Consumes `signal.approved` from group `signal-service-group`.
- Inserts an authoritative record into `signals_ledger.signals` with `status = 'waiting_for_entry'` and initial optimistic lock `version = 1`.
- Emits event: `signal.state_changed` (`from_state: null, to_state: 'waiting_for_entry'`).

### Step 6: Paper Order Execution & Live Position Exit Monitoring (`paper-exec-service`)
- Consumes `signal.state_changed` from group `paper-exec-group`.
- **Entry Phase**: Monitors live price ticks against limit entry price ($C_t$). When filled within the 2-bar timeout window:
  - Creates simulated trade in `paper_execution.paper_trades` (`status: 'open'`).
  - Calls `signal-service` to transition signal from `'waiting_for_entry'` to `'order_in_progress'` (`version: 1 -> 2`).
  - Emits event: `signal.state_changed`.
- **Exit Phase (Sole Owner)**: Monitors live mark price ticks against Take Profit and Stop Loss barriers:
  - Applies conservative **SL-first rule**: If a bar penetrates both TP and SL, Stop Loss is strictly assumed.
  - Requires a 5 bps (0.05%) price penetration buffer beyond the barrier price to simulate realistic book liquidity.
  - Computes net PnL deducting 14 bps round-trip maker/taker fees and funding accrual.
  - Emits event: `trade.closed` to Redis Stream `trade.closed`.

### Step 7: Signal Ledger Finalization (`signal-service`)
- Consumes `trade.closed` from group `signal-service-group`.
- Transitions signal in `signals_ledger.signals` from `'order_in_progress'` to `'target_hit'` (`win_target_hit`) or `'stop_hit'` (`loss_stop_loss_hit`) using optimistic locking (`version: 2 -> 3`).
- Emits event: `signal.state_changed`.

### Step 8 & 9: Real-Time Client Delivery (`api-gateway` -> `dashboard`)
- API Gateway multiplexes `price.tick` and `signal.state_changed` streams into an SSE stream at `GET /events/stream`.
- Next.js 14 client browser receives SSE events, updating the live ticker tape, active signals table, and paper trading position log without page reloads or local state computations.

---

## 2. Worked BTCUSDT Long Trade Walkthrough

*(Based on the verified E2E Integration Fixture: `tests/test_e2e_pipeline.py`)*

| Lifecycle Phase | Field / Parameter | Exact Value | Source / Formula |
| :--- | :--- | :--- | :--- |
| **Candle Close** | Symbol / Timeframe | `BTCUSDT` / `1h` | Binance Futures `market_data.candles` |
| | Close Price ($C_t$) | `50,000.00 USD` | Closed candle open time: `2026-11-11T12:00:00Z` |
| | Candle ATR (`14`) | `1,000.00 USD` ($2.0\%$) | `feature_store.features` |
| **ML Inference** | Calibrated Prob ($p$) | `0.7000` ($70.0\%$) | LightGBM + Platt Scaling |
| | Meta Confidence ($m$) | `0.7800` ($78.0\%$) | Random Forest Meta-Classifier |
| | Direction | `long` | Directional classifier output |
| **Risk Approval** | Virtual Portfolio Equity | `10,000.00 USD` | `paper_execution` account balance |
| | Risk per Trade | `0.5%` (\$50.00) | `DEFAULT_BARRIER_CONFIG.risk_per_trade_pct` |
| | Stop Distance | `1.0 x ATR` (\$1,000.00 = 2.0%) | `DEFAULT_BARRIER_CONFIG.sl_multiplier` |
| | Stop Loss Price | `49,000.00 USD` | $\text{Entry} - 1.0 \times \text{ATR}$ |
| | Take Profit Price | `52,000.00 USD` | $\text{Entry} + 2.0 \times \text{ATR}$ |
| | Position Size | `2,500.00 USD` (0.05 BTC) | $\frac{\text{Risk USD}}{\text{Stop Distance \%}} = \frac{\$50}{0.02} = \$2,500$ |
| | Effective Leverage | `0.25x` (Cap $\le 3.0\text{x}$) | $\frac{\$2,500}{\$10,000} = 0.25$ |
| | Cost-to-Risk Ratio | `7.0%` (Cap $\le 20.0\%$) | $\frac{14 \text{ bps}}{200 \text{ bps}} = 0.070$ (Approved) |
| **Signal Ledger** | Signal ID | `#999` | `signals_ledger.signals` (`version = 1`) |
| | Initial Status | `waiting_for_entry` | Optimistic lock initial state |
| **Paper Fill** | Limit Entry Price | `50,000.00 USD` | Filled on bar $t+1$ within 2 bars |
| | Status Transition | `order_in_progress` | `version = 1 -> 2` |
| **Position Exit** | Live Mark Price Tick | `52,050.00 USD` | Exceeds $52,000 \times 1.0005 = 52,026.00$ |
| | Exit Price | `52,000.00 USD` | Filled at limit Take Profit price |
| | Exit Reason | `target_hit` | Evaluated by `paper-exec-service` |
| | Gross Return | `+4.000%` (+\$100.00) | $\frac{52,000 - 50,000}{50,000} \times \$2,500$ |
| | Round-Trip Fees | `-$3.50 USD` (14 bps) | $0.0014 \times \$2,500$ |
| | Funding Accrual | `-$0.20 USD` | Accrued 8h funding rate |
| | Net PnL USD | `+$96.30 USD` | $\$100.00 - \$3.50 - \$0.20$ |
| | Net Return on Risk | `+192.6%` | $\frac{\$96.30}{\$50.00}$ (1 : 1.93 R:R net of all friction) |
| | Final Signal Status | `target_hit` | `version = 2 -> 3` (`signals_ledger.signals`) |

---

## 3. Explicit Failure Paths & Guardrails

### 1. Stale-Data Halt / Collector Downtime
- **Detection**: `market-collector` writes a Redis heartbeat key `collector:heartbeat` every 5 seconds.
- **Action**: If `collector:heartbeat` is missing for $>15$ seconds, `api-gateway` flags feed status as `"degraded"`. `risk-service` immediately halts new signal approvals:
  ```python
  if (now - last_tick_time).total_seconds() > 15.0:
      return False, {}, "Stale market data: tick feed latency exceeds 15s"
  ```

### 2. Risk Rejection Paths
- If `friction / sl_distance > 0.20` -> Rejected: `"Cost-to-risk ratio exceeds 20% limit"`.
- If rolling 24h realized loss exceeds 3.0% -> Rejected: `"Daily loss limit (3.0%) reached. Trading paused until reset"`.
- If trailing portfolio drawdown exceeds 10.0% -> Rejected: `"Max portfolio drawdown (10.0%) exceeded. Circuit breaker tripped"`.
- If symbol's correlated cluster exposure exceeds 30.0% -> Rejected: `"Cluster exposure cap (30.0%) reached"`.

### 3. Expired Entry (Unfilled Limit Order)
- A signal in `waiting_for_entry` must be filled within `limit_wait_bars = 2` bars.
- If market price moves away without touching entry price $C_t$ within 2 bars, `signal-service` transitions signal to `'expired'` (`cancel_reason: "Entry timeout unfulfilled after 2 bars"`). No trade is opened.

### 4. Invalidated Signal
- If an opposing extreme regime spike or catastrophic market event occurs before entry, `signal-service` transitions the signal to `'invalidated'`.

### 5. Duplicate Event Handling (Idempotency Guard)
- Every event payload contains `idempotency_key` (e.g. `pred-BTCUSDT-1h-20261111120000`).
- Database tables utilize unique constraints (e.g., `CONSTRAINT uq_signal_instance UNIQUE (symbol, timeframe, candle_open_time, direction)`).
- Duplicate events are trapped by `ON CONFLICT DO NOTHING`, discarding redundant processing safely.

### 6. No Active Model State
- If `model_registry.models` contains zero champion models (our current verified production state):
  - `model-service` logs `"No champion model registered"`.
  - Zero signals are generated.
  - Gateway returns `"has_active_champion": false` and `"champion_status_notice": "No validated model. Zero models promoted to champion or challenger."`.
  - Frontend renders honest amber badge: `"No validated model"`.

### 7. Historical Gap Detection & Automated Backfill
- On startup, `market-collector` verifies candle continuity:
  $$\Delta t = t_{k} - t_{k-1}$$
- If $\Delta t > 1 \text{ period}$ (e.g., missed 1h or 4h candle due to container restart), it queries Binance REST `/fapi/v1/klines` with pagination (1,500 bars/request) to backfill missing bars before resuming the WebSocket stream.

