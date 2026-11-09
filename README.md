# Trade AI Dashboard v0.1

A self-hosted, high-frequency cryptocurrency algorithmic signal platform and institutional-grade trading dashboard: Binance Futures live streaming market data, LightGBM prediction model with meta-labeling, adaptive ATR risk management, Next.js 14 multi-view dashboard, and paper trading execution.

> **Disclaimer**: This is an engineering research and paper-trading platform, not financial advice. All orders and portfolio balances are simulated with zero financial risk. It does not place real exchange orders.

---

## Current Status & Verification Checklist

| Milestone | Area | Status | Notes |
|---|---|---|---|
| **01** | Docker Compose Stack | **Completed** | PostgreSQL 16 (TimescaleDB), Redis 7, FastAPI, Next.js 14 |
| **02** | Hypertables & TimescaleDB Schema | **Completed** | 6 hypertables (`candles`, `funding_rates`, `open_interest`, etc.) |
| **03** | Data Ingestion Pipeline | **Completed** | Direct Binance MiniTicker WS (`!miniTicker@arr`) + REST polling |
| **04** | Feature Pipeline & Triple-Barrier | **Completed** | TA-Lib momentum, derivatives metrics, volatility regimes |
| **05** | ML Model & Meta-Labeling | **Completed** | Calibrated LightGBM (Stage 1) + Random Forest Meta-Gate (Stage 2) |
| **06** | Adaptive Risk Engine | **Completed** | ATR stops ($1 : 2.2$ R:R), 3x max leverage, daily loss limits |
| **07** | FastAPI Core Services | **Completed** | `/health`, `/summary`, `/signals`, `/history`, `/equity`, `/status` |
| **08** | Signal Lifecycle Transitions | **Completed** | 5 states: *Waiting confirmation*, *Waiting entry*, *Order in progress*, *Win*, *Loss* |
| **09** | Idempotent Persistence | **Completed** | `/signals/transition` persists status & records paper trades without duplication |
| **10** | Performance & Trade History | **Completed** | Duration, time-to-target, prediction timestamps, win/loss analytics |
| **11** | Next.js Multi-View Dashboard | **Completed** | 7 views: Overview, Markets, Signals, Positions, History, Chart, System |
| **12** | SVG Candlestick Chart | **Completed** | 15m/1h/4h/1D controls, volume histogram, 20/50 EMAs, signal overlays |
| **13** | Theme & Accessibility | **Completed** | High-contrast Dark & Light modes with WCAG AA compliance |
| **14** | Automated Unit Test Suite | **Completed** | 21 focused tests passing in `dashboard/tests/signal_lifecycle.test.mjs` |

See [docs/ROADMAP.md](docs/ROADMAP.md) for detailed phase breakdowns and forward roadmap items.

---

## Technical Stack

| Layer | Technology |
|---|---|
| **Language & Backend API** | Python 3.11, FastAPI, Uvicorn, Pydantic |
| **Market Data Feed** | Binance USD-M Futures Public REST & WebSocket API |
| **Technical Indicators** | TA-Lib (C library wrapped via Python) |
| **Machine Learning** | LightGBM (Platt-calibrated) + Meta-Labeling Classifier |
| **Database & Caching** | PostgreSQL 16 with TimescaleDB extension, Redis 7 |
| **Frontend Framework** | Next.js 14 (React 18, Server Components & Dynamic SSR) |
| **Containerization** | Docker Compose with multi-stage production builds |

---

## Architecture Diagram

```
Binance Futures REST / WS ──► collector ──► TimescaleDB ──► features (TA-Lib + derivatives data)
                                                                    │
                                                            LightGBM + Meta-Filter
                                                                    │
                                                        risk engine (entry / SL / TP / sizing)
                                                                    │
                                            FastAPI ◄───────────────┴────► Redis (pub/sub)
                                               │
                                    ┌──────────┴──────────┐
                                    ▼                     ▼
                             Next.js Dashboard     /signals/transition
                              (Port :3000)          (Idempotent DB writes)
```

Full architectural specifications, data flows, and state machine diagrams are detailed in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Monitored Futures Universe

The system actively tracks 8 liquid Binance USD-M perpetual contracts:
`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `LINKUSDT`, `TRXUSDT`.

All tracked coins adhere strictly to the 5-stage lifecycle:
1. **Waiting for confirmation**: Monitoring market structure; no confirmed breakout setup.
2. **Waiting for entry**: Breakout confirmed ($P \ge 0.55$ + Meta-Gate); limit entry pending.
3. **Order in progress**: Market price touched entry; paper trade actively open with live floating P&L.
4. **Win — Target hit**: Take-profit target reached; trade closed with positive return.
5. **Loss — Stop loss hit**: Stop-loss touched; trade closed with controlled risk limit.

Completed trades immediately transition into **Performance & Trade History** with trade duration, time-to-target, and exact entry/exit prices.

---

## Deployment & Server Commands

### Quick Start (Debian 12/13 Host)

```bash
git clone https://github.com/Gstarksinc/Trade-AI-Dashboard-v0.1.git /opt/signals
cd /opt/signals
bash scripts/gen_env.sh            # creates .env with secure random passwords
docker compose up -d --build       # starts db, redis, api, collector, dashboard
```

### Apply Latest Repository Updates

```bash
cd /opt/signals
git pull origin main
docker compose build --no-cache dashboard api
docker compose up -d dashboard api
docker logs --tail 30 -f signals-dashboard-1
```

Access the dashboard at `http://SERVER_IP:3000` (or via SSH tunnel: `ssh -L 3000:127.0.0.1:3000 user@SERVER_IP`).

---

## Documentation Index

- [Comprehensive Architecture & Technical Specification](docs/ARCHITECTURE.md)
- [Dashboard API Contract & Endpoints](docs/DASHBOARD_API.md)
- [Project Roadmap & Checklist](docs/ROADMAP.md)
- [Debian Server Host Setup Guide](docs/SETUP_DEBIAN.md)
- [Data Collector Technical Guide](docs/COLLECTOR.md)
