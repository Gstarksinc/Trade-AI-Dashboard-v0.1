# Project Roadmap & Implementation Checklist

## Phase 1: Core Engine, Signals Pipeline & Dashboard

- [x] **Infrastructure & Orchestration**
  - [x] Docker Compose stack (TimescaleDB, Redis 7, FastAPI, Next.js 14).
  - [x] TimescaleDB schema with 6 hypertables, compression policies, chunk retention intervals.
  - [x] Health check endpoint (`GET /health`).
- [x] **Data Ingestion (Binance USD-M Perpetuals)**
  - [x] Collector daemon for 15m, 1h, 4h klines, funding rates, open interest, and taker volume.
  - [x] Direct MiniTicker WebSocket feed (`wss://fstream.binance.com/ws/!miniTicker@arr`) for sub-second live price streaming.
  - [x] Public REST fallback polling (`/fapi/v1/ticker/24hr`, `/fapi/v1/premiumIndex`).
  - [x] CoinGecko disabled; 100% pure Binance perpetual feed integration.
- [x] **Quantitative Feature Pipeline & Risk Management**
  - [x] Feature builder (TA-Lib momentum, ATR volatility, long/short ratio, funding regime).
  - [x] Triple-barrier event labeling (ATR take profit, stop loss, time limits).
  - [x] Primary classifier: Calibrated LightGBM model.
  - [x] Secondary classifier: Meta-labeling filter to prune false breakouts.
  - [x] Risk Engine: ATR stops, dynamic sizing, 3x leverage cap, daily loss limit, correlation limits.
- [x] **API Services & Data Contracts**
  - [x] `GET /signals` with genuine active signals query (`WHERE s.status IN ('open', 'in_progress')`).
  - [x] `POST /signals/transition` for idempotent lifecycle transitions and paper trade logging.
  - [x] `GET /history` for closed trades with preserved prediction times and actual durations.
  - [x] `GET /summary` with genuine counts and denominators (0.0% win rate when 0 closed trades).
  - [x] `GET /equity` and `GET /status`.
  - [x] Removal of mock/dummy fallback data from all API routes.
- [x] **Next.js 14 Dashboard Presentation & UI/UX**
  - [x] Multi-view router (Overview, Markets, Signals, Positions, Trade History, Candlestick Chart, Model & System).
  - [x] Universal high-contrast themes (Dark & Light modes with WCAG AA compliance).
  - [x] Pure SVG interactive candlestick chart with timeframe controls (15m, 1h, 4h, 1D), 20/50 EMAs, volume bars, and crosshair overlays.
  - [x] Searchable, sortable futures watchlist with BTC & ETH hero cards.
  - [x] Active signal lifecycle state machine with 5 distinct states:
    1. *Waiting for confirmation*
    2. *Waiting for entry*
    3. *Order in progress*
    4. *Win — Target hit*
    5. *Loss — Stop loss hit*
  - [x] Performance & Trade History viewer with trade duration, time-to-target, and pagination.
  - [x] Paper trading account summary ($10,000 base, total equity, available/used margin, daily/total P&L).
  - [x] Dual status alerts: Market Price Feed stream vs Signal Collector freshness.
  - [x] Position size calculator modal and session restart controls.
- [x] **Testing & Verification**
  - [x] 21 focused unit tests for genuine signals, lifecycle transitions, idempotency, and duration calculations ([`dashboard/tests/signal_lifecycle.test.mjs`](../dashboard/tests/signal_lifecycle.test.mjs)).
  - [x] Next.js production build (`npm run build`) compiling with 0 errors across all static and dynamic routes.

---

## Phase 2: Advanced Quant & Production Scale

- [ ] FinBERT / CryptoBERT news sentiment integration (only if verified out-of-sample).
- [ ] Secondary model architecture (TCN / Temporal Convolutional Network or LSTM) for ensemble diversity.
- [ ] Hidden Markov Model (HMM) market regime detector.
- [ ] Telegram alert bot for verified breakout signals.
- [ ] Prometheus metrics exporter and Grafana monitoring dashboard.
- [ ] Universe expansion from 8 to 25+ liquid perpetuals.
