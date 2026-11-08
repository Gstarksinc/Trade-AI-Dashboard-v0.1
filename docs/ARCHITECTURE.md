# Architecture

```
Binance REST / WS ──► collector ──► TimescaleDB ──► features (TA-Lib + futures data)
CoinGecko (daily) ──► universe filter                       │
News feeds ──► sentiment (Phase 2) ───────────────────────► LightGBM + meta-label filter
                                                            │
                                         risk engine (entry / SL / TP / sizing) ──► signals table, Redis
                                                            │
                                      FastAPI ◄─────────────┘
                                         │            │
                                  Next.js dashboard   Telegram notifier
```

## Services

| Service | Port | Notes |
|---|---|---|
| db (TimescaleDB, PostgreSQL 16) | 127.0.0.1:5432 | candles, funding, open interest, signals, paper trades |
| redis | 127.0.0.1:6379 | latest features and signal state, password protected |
| api (FastAPI) | 127.0.0.1:8000 | `/health` now; dashboard endpoints planned |
| dashboard (Next.js) | 127.0.0.1:3000 | reads the API server-side, refreshes every 30 s |
| collector, notifier | none | profile `full`, planned |
| trainer | none | profile `train`, one-off runs |

## Modelling decisions

- **Labels:** triple-barrier (ATR-based take profit, stop loss, time limit), not next-candle up/down.
- **Primary model:** LightGBM with isotonic or Platt calibration.
- **Meta-labeling:** a second classifier decides whether to take the primary signal. XGBoost was dropped as a validator because it duplicates LightGBM's errors.
- **Features:** TA-Lib indicators plus funding rate, open interest change, long/short ratio, taker volume, BTC correlation, volatility regime and time features.
- **Validation:** walk-forward with purging and embargo; fees, slippage and funding included. Random splits leak the future and are not used.
- **Risk:** ATR stops, volatility-scaled sizing, maximum 3x simulated leverage, daily loss limit, correlation cap across open signals.
- **Training window:** rolling 12 months, retrained weekly or monthly. One pooled model across all coins.

## Data availability

Klines and funding can be backfilled for years. The REST API exposes only about 30 days of open interest, long/short ratio and taker volume (bulk metrics files cover more for some symbols). Liquidations and order book history exist only from the day recording starts, so start the collector early.

## Security

- All published ports bind to `127.0.0.1`; access is through an SSH tunnel, VPN or an authenticated reverse proxy.
- Secrets live in `.env` (mode 600, git-ignored). Use read-only Binance keys if keys are ever needed; public market data needs none.
- Order execution is intentionally not implemented.
