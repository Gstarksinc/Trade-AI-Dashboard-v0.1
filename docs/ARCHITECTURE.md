# System Architecture & Technical Specification

> **Trade AI Dashboard v0.1**  
> High-Frequency Algorithmic Signals, Risk Management & Paper Trading Architecture

---

## 1. High-Level System Architecture

```
                                      ┌─────────────────────────────────────────────────────────────┐
                                      │              BINANCE FUTURES (USD-M PERP)                   │
                                      │   • WebSocket: wss://fstream.binance.com/ws/!miniTicker@arr │
                                      │   • Public REST: /fapi/v1/ticker/24hr, /fapi/v1/klines      │
                                      └──────────────────────┬──────────────────────┬───────────────┘
                                                             │                      │
                                           1s MiniTicker     │                      │ 15m/1h/4h OHLCV
                                           Live Price Stream │                      │ Funding & OI
                                                             ▼                      ▼
┌────────────────────────────────┐         ┌─────────────────────────┐    ┌─────────────────────────┐
│     CLIENT BROWSER             │         │   NEXT.JS DASHBOARD     │    │   DATA COLLECTOR DAEMON │
│  • Multi-View Navigation       │◄───────►│   (Next.js 14 / SSR)    │    │   (Python / Asyncio)    │
│  • High-Contrast Light/Dark    │         │  • Dynamic SSR & Client │    └────────────┬────────────┘
│  • Interactive SVG Candles     │         │  • High-Freq Price API  │                 │
│  • Local Lifecycle Cache       │         │  • Transition Proxy     │                 ▼
└────────────────────────────────┘         └────────────┬────────────┘    ┌─────────────────────────┐
                 ▲                                      │                 │   TIMESCALEDB (PG 16)   │
                 │                                      │                 │  • candles (30d chunks) │
                 │ REST (/signals, /history, /summary)  │                 │  • funding_rates        │
                 └──────────────────────────────────────┼────────────────►│  • open_interest        │
                                                        ▼                 │  • signals (hypertable) │
                                           ┌─────────────────────────┐    │  • paper_trades         │
                                           │   FASTAPI BACKEND       │    └────────────▲────────────┘
                                           │   (Python 3.11 / Uvicorn)│                 │
                                           │  • Signal Ingestion     │                 │
                                           │  • Lifecycle Transition │◄────────────────┘
                                           │  • Genuine Data Guard   │
                                           └────────────┬────────────┘
                                                        │
                                                        ▼
                                           ┌─────────────────────────┐
                                           │   REDIS CACHE (v7)      │
                                           │  • Pub/Sub: signals:new │
                                           │  • Active Model Config  │
                                           └─────────────────────────┘
```

---

## 2. Complete End-to-End Mermaid Workflow

```mermaid
flowchart TD
    subgraph DataIngestion ["1. Real-Time Data Ingestion"]
        BF[Binance Futures REST & WebSocket]
        COL[Collector Daemon]
        TS[(TimescaleDB Candles & Funding)]
        BF -->|Raw Klines & Tickers| COL
        COL -->|Normalized Hypertables| TS
    end

    subgraph FeatureML ["2. Quantitative Feature Pipeline & Modeling"]
        FEAT[Technical Analysis & Feature Builder]
        LGBM[Stage 1: Calibrated LightGBM Classifier]
        META[Stage 2: Random Forest Meta-Labeling Filter]
        RISK[Adaptive Risk Engine ATR Sizing & Correlation]
        TS --> FEAT
        FEAT --> LGBM
        LGBM -->|P >= 0.55| META
        META -->|Meta Score >= 0.60| RISK
    end

    subgraph SignalLifecycle ["3. Signal State Machine & Paper Trading"]
        SIG[(signals table)]
        PAPER[(paper_trades table)]
        RISK -->|Approved Signal 'open'| SIG
        SIG -->|Limit Trigger| PIP[Order in Progress]
        PIP -->|Take Profit Hit| WIN[Win — Target Hit]
        PIP -->|Stop Loss Hit| LOSS[Loss — Stop Loss Hit]
        PIP -.->|opened_at recorded| PAPER
        WIN -.->|closed_at & exit_price| PAPER
        LOSS -.->|closed_at & exit_price| PAPER
    end

    subgraph APILayer ["4. API & Real-Time Distribution"]
        API[FastAPI Backend :8000]
        TRANS[/signals/transition Endpoint]
        REDIS[(Redis 7 Pub/Sub)]
        SIG --> API
        PAPER --> API
        RISK -->|Publish signals:new| REDIS
        WIN --> TRANS
        LOSS --> TRANS
        TRANS -->|Idempotent Update| SIG
        TRANS -->|Idempotent Record| PAPER
    end

    subgraph Presentation ["5. High-Frequency Frontend Dashboard"]
        DASH[Next.js 14 Dashboard :3000]
        TAPE[Ticker Tape & Watchlist]
        CHART[SVG Candlestick Chart]
        HIST[Performance & Trade History]
        WS[Direct MiniTicker WS Stream]
        API --> DASH
        WS --> TAPE
        TRANS -.-> DASH
        DASH --> CHART
        DASH --> HIST
    end
```

---

## 3. Core Component Architecture

### 3.1 Market Ingestion Layer (Binance USD-M Perpetuals)
- **Primary Source**: Binance USD-M Futures public REST API (`https://fapi.binance.com`) and direct WebSocket streams (`wss://fstream.binance.com/ws/!miniTicker@arr`).
- **Monitored Pairs (8 Core Perpetuals)**:
  - `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `LINKUSDT`, `TRXUSDT`.
- **Ingestion Timeframes**:
  - `15m` (Tactical momentum entries)
  - `1h` (Trend continuation & swing setups)
  - `4h` (Macro regime & multi-day structure)
- **Hypertables Captured**:
  - `candles`: Open, High, Low, Close, Volume, Quote Volume, Trades, Taker Buy Base Volume. Compressed after 30 days.
  - `funding_rates`: 8-hour funding rates and mark price baselines.
  - `open_interest` & `taker_volume`: Aggregated derivative participation metrics.

### 3.2 Quantitative ML & Meta-Labeling Architecture
- **Primary Predictor (Stage 1)**:
  - Multi-feature LightGBM gradient-boosted decision trees trained with triple-barrier event labeling (ATR-based Take Profit, Stop Loss, and time expiration limits).
  - Platt / Isotonic probability calibration to map raw tree margins into true empirical probabilities.
  - Entry gate: Requires probability $P \ge 0.55$.
- **Meta-Labeling Filter (Stage 2)**:
  - Secondary classification layer based on Marcos López de Prado's meta-labeling methodology.
  - Filters out false breakouts by predicting whether the primary model's position will hit target before stop loss.
  - Eliminates model bias without altering the primary direction.
- **Strict Anti-Leakage Protocol**:
  - Purged and embargoed walk-forward cross-validation.
  - All features calculated strictly on completed historical candle boundaries (`open_time`). No future data is accessible.

### 3.3 Risk Management Engine
- **ATR Dynamic Volatility Stops**:
  - Long Stop Loss: $\text{Entry} - (1.0 \times \text{ATR}_{14})$
  - Long Take Profit: $\text{Entry} + (2.2 \times \text{ATR}_{14})$
  - Short Stop Loss: $\text{Entry} + (1.0 \times \text{ATR}_{14})$
  - Short Take Profit: $\text{Entry} - (2.2 \times \text{ATR}_{14})$
  - Minimum Risk-to-Reward ratio: $1 : 2.2$.
- **Capital Protection & Leverage Constraints**:
  - Maximum leverage cap: $3.0\times$.
  - Maximum correlated positions: 3 open positions simultaneously.
  - Daily loss limit: $3.0\%$ of virtual capital (halts new setup generation if breached).
  - Simulated margin per trade: \$500 margin (\$1,500 notional at 3x).

### 3.4 Signal Lifecycle State Machine & Idempotent Persistence
The dashboard enforces 5 distinct states in strict chronological order:

```
[1. Waiting for confirmation]
       │
       ▼ (Model confirms breakout P >= 0.55 + Meta Gate)
[2. Waiting for entry]
       │
       ▼ (Market CMP touches Expected Entry price)
[3. Order in progress]
       │
       ├─────────────────────────────────────────┐
       ▼ (Market CMP touches TP)                 ▼ (Market CMP touches SL)
[4. Win — Target hit]                     [5. Loss — Stop loss hit]
       │                                         │
       └────────────────────┬────────────────────┘
                            │
                            ▼
              [POST /signals/transition]
              • Idempotent DB Write: signals.status = 'target_hit' | 'stop_hit'
              • paper_trades closed_at & exit_price committed
              • Signal moved from Active Signals to Performance & Trade History
```

1. **`Waiting for confirmation`**:
   - Displayed for tracked coins where no genuine active setup currently meets quantitative confirmation criteria.
   - All levels (`entry`, `stop_loss`, `take_profit`, `rr`) display `—` honestly.
2. **`Waiting for entry`**:
   - Confirmed signal approved by Risk Engine, but current market price has not yet reached the entry price.
3. **`Order in progress`**:
   - Entry price reached. The paper trade is opened and timestamped with `opened_at`.
   - Normal market fluctuations between entry and SL/TP remain in `Order in progress`.
4. **`Win — Target hit`**:
   - Current market price reaches the Take Profit target.
   - Logged with `closed_at`, `exit_price = take_profit`, `exit_reason = 'Target Hit'`.
5. **`Loss — Stop loss hit`**:
   - Current market price reaches the Stop Loss limit.
   - Logged with `closed_at`, `exit_price = stop_loss`, `exit_reason = 'Stop Loss Hit'`.

---

## 4. API Endpoints & Data Contracts

All endpoints are hosted by FastAPI on `:8000` and proxied or queried by Next.js on `:3000`.

### `GET /health`
- **Purpose**: System health monitoring for API, Database, and Redis connections.
- **Response**:
  ```json
  { "api": "ok", "db": "ok", "redis": "ok" }
  ```

### `GET /signals?limit=25&active_only=true`
- **Purpose**: Retrieves genuine active predictive signals from the `signals` table.
- **Contract**:
  - Filters `WHERE s.status IN ('open', 'in_progress')`.
  - Returns `[]` honestly when no genuine active signals exist (strictly no fallback/sample signals).
  - Response object contains `id`, `symbol`, `timeframe`, `direction`, `entry`, `stop_loss`, `take_profit`, `probability`, `meta_probability`, `current_price`, `opened_at`, `is_fallback: false`.

### `POST /signals/transition`
- **Purpose**: Idempotently commits signal lifecycle transitions and records trade history into PostgreSQL.
- **Request Body**:
  ```json
  {
    "signal_id": 105,
    "status": "target_hit",
    "opened_at": "2026-11-09T18:00:00Z",
    "closed_at": "2026-11-09T19:35:15Z",
    "exit_price": 76000.0,
    "pnl_pct": 2.70,
    "exit_reason": "Target Hit",
    "symbol": "BTCUSDT",
    "direction": "long",
    "entry": 74000.0
  }
  ```
- **Behavior**:
  - Updates `signals SET status = %s WHERE id = %s`.
  - Updates existing open trade in `paper_trades` with `closed_at`, `exit_price`, and `pnl_pct`.
  - If already closed, ignores duplicate requests to guarantee that history is never duplicated.

### `GET /history?days=30`
- **Purpose**: Retrieves completed paper trades where target or stop loss has been reached.
- **Contract**:
  - Enforces `WHERE p.closed_at IS NOT NULL`.
  - Joins `signals` on `s.id = p.signal_id` to preserve original `predicted_at` (`s.created_at`) and `timeframe`.
  - Never filters out losing trades.

### `GET /summary`
- **Purpose**: Provides aggregate performance KPIs for the dashboard header cards.
- **Contract**:
  - Returns genuine `open_signals` count, `symbols_scanned`, `win_rate_30d`, `closed_30d`, `net_pnl_30d`, `max_drawdown`.
  - If `closed_30d == 0`, returns `win_rate_30d: 0.0` (zero fake fallbacks).

### `GET /equity?days=30`
- **Purpose**: Returns cumulative equity curve derived from closed paper trade outcomes.
- **Contract**:
  - Returns array of `{ "ts": string, "equity": number }` starting from 100.0 base. Returns `[]` if no closed trades exist.

---

## 5. Frontend Dashboard Architecture (Next.js 14)

### 5.1 Multi-View Navigation Router
The dashboard features an integrated top navigation bar supporting 7 dedicated application views:
1. **Overview View**: Paper trading portfolio summary, dual status alert strip, 4 KPI hero cards, market highlights, active signals preview, and equity curve.
2. **Markets View**: Searchable, sortable futures watchlist for the 8 monitored perpetuals with live 24h ticker cards, mark prices, funding rates, and 24h volumes.
3. **Signals View**: Full active signals table/cards with live trade level visualizer, expected entries, stops, targets, R:R badges, and status filters.
4. **Positions View**: Dedicated open positions tracker showing unrealized P&L in USDT and percentage, margin allocation, leverage, liquidation distance, and simulated exit action.
5. **Trade History View**: Complete performance ledger with trade duration, elapsed time to target, prediction timestamps, win rate analytics, and pagination.
6. **Candlestick Chart View**: Pure SVG interactive candlestick chart with timeframe controls (15m, 1h, 4h, 1D), volume histogram, 20/50 EMAs, Entry/SL/TP/CMP overlays, and crosshair inspection.
7. **Backtest & Model View**: Machine learning pipeline architecture, feature importance, confidence distribution, infrastructure health grid, and walk-forward verification.

### 5.2 Real-Time Dual Status Architecture
- **Market Price Feed Status**: Directly tracks the Binance WebSocket stream / REST polling connection with millisecond precision and tick directions (`tick-up`, `tick-down`).
- **Signal Collector Status**: Evaluates the freshness of the latest hypertable candle (`last_candle_age_min <= 20 min` = Active & Ingesting; `> 20 min` = Collector Waiting).

### 5.3 Theme & Accessibility Architecture
- High-contrast CSS variable tokens supporting instant toggle between **Dark Mode** and **Light Mode** (WCAG AA compliant contrast ratios).
- Text/icon pairings on all metrics (`▲ LONG`, `▼ SHORT`, `✓ Win — Target hit`, `✕ Loss — Stop loss hit`) ensuring no state relies on color alone.

---

## 6. Database Schema Specifications

### `signals` (Hypertable on `created_at`)
```sql
CREATE TABLE signals (
  id               bigserial PRIMARY KEY,
  created_at       timestamptz NOT NULL DEFAULT now(),
  symbol           text NOT NULL,
  timeframe        text NOT NULL,
  direction        text NOT NULL,
  probability      double precision,
  meta_probability double precision,
  entry            double precision,
  stop_loss        double precision,
  take_profit      double precision,
  atr              double precision,
  model_version    text,
  status           text DEFAULT 'open',
  features         jsonb
);
CREATE INDEX ON signals (symbol, created_at DESC);
```

### `paper_trades`
```sql
CREATE TABLE paper_trades (
  id          bigserial PRIMARY KEY,
  signal_id   bigint REFERENCES signals(id),
  opened_at   timestamptz NOT NULL,
  closed_at   timestamptz,
  symbol      text NOT NULL,
  direction   text NOT NULL,
  entry       double precision,
  exit_price  double precision,
  leverage    double precision,
  fees        double precision,
  funding     double precision,
  pnl_pct     double precision,
  exit_reason text
);
```

---

## 7. Security & Operational Boundaries

1. **Port Bindings**: All internal services (`5432` PostgreSQL, `6379` Redis, `8000` FastAPI) bind to `127.0.0.1` inside Docker networks. External access is routed through authenticated reverse proxy or SSH tunnels.
2. **Zero Order Execution**: The system is engineered strictly for predictive research, quantitative validation, and paper trading. No order placement or exchange API private keys are permitted in execution paths.
3. **Data Integrity**: Genuine signals only. Mock, synthetic, or fallback signals are never substituted for real market setups.
