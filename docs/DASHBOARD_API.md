# Dashboard API contract

The dashboard (`dashboard/lib/data.js`) fetches these endpoints from `API_URL` (default `http://api:8000`). Each endpoint falls back to sample data independently when it is missing or fails; the **Sample data** chip disappears when all four respond. `/health` is already implemented.

| Endpoint | Response |
|---|---|
| `GET /health` | `{"api":"ok","db":"ok","redis":"ok"}` |
| `GET /summary` | `open_signals`, `symbols_scanned`, `win_rate_30d`, `closed_30d`, `net_pnl_30d`, `max_drawdown`, `drawdown_limit` (percentages as plain numbers, for example `54.2`) |
| `GET /signals?limit=20` | List of `{symbol, timeframe, direction, created_at, probability, entry, stop_loss, take_profit, status}`; `direction` is `long` or `short`; `status` is `open`, `target_hit` or `stopped` |
| `GET /equity?days=30` | List of `{ts, equity}`, oldest first |
| `GET /status` | `last_candle_age_min`, `model_version`, `next_retrain`, `daily_loss_used`, `daily_loss_limit`, `max_leverage`, `correlated_open`, `correlated_cap` |

Timestamps (`created_at` on signals, `next_retrain`) must be ISO 8601 in UTC; the dashboard converts them to UTC or IST. Prices (`entry`, `stop_loss`, `take_profit`) are in USDT; the dashboard converts them to USD or INR using the CoinGecko USDT rate (`COINGECKO_API_KEY`, cached 5 minutes; optional `USDT_INR_FALLBACK`). Percent values are not converted.

Sources: `/signals` reads the `signals` table; `/summary` and `/equity` derive from `paper_trades`; `/status` combines the newest 15m candle in `candles`, the active model version and the risk engine state.
