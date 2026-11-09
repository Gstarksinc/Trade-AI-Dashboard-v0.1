# Dashboard API Specification & Data Contract

The Next.js dashboard (`dashboard/lib/data.js` and server routes) interfaces with the FastAPI backend on `API_URL` (default `http://api:8000`).

---

## 1. Endpoints Overview

| Method | Endpoint | Description | Status |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Service connectivity check (API, TimescaleDB, Redis) | **Active** |
| `GET` | `/summary` | Aggregate 30-day KPIs with genuine counts & denominators | **Active** |
| `GET` | `/signals` | Genuine active predictive signals (`open`, `in_progress`) | **Active** |
| `POST`| `/signals/transition` | Idempotent signal lifecycle transition & paper trade recorder | **Active** |
| `GET` | `/history` | Closed trade performance records with timestamps and durations | **Active** |
| `GET` | `/equity` | Closed trade cumulative equity curve | **Active** |
| `GET` | `/status` | Infrastructure status, candle ingestion freshness, and risk limits | **Active** |
| `GET` | `/prices` | Latest close price for all tracked symbols from TimescaleDB | **Active** |

---

## 2. Detailed Data Contracts

### `GET /health`
Returns connection status for all critical infrastructure backends.
```json
{
  "api": "ok",
  "db": "ok",
  "redis": "ok"
}
```

### `GET /signals?limit=25&active_only=true`
Retrieves genuine active predictive signals from the `signals` hypertable.
- **Query Parameters**:
  - `limit` (int, default `25`, max `100`): Maximum active signals to return.
  - `active_only` (bool, default `true`): When true, filters `WHERE s.status IN ('open', 'in_progress')`.
- **Response**: Array of genuine signal objects:
  ```json
  [
    {
      "id": 14,
      "symbol": "BTCUSDT",
      "timeframe": "1h",
      "direction": "long",
      "created_at": "2026-11-09T18:45:00.000000+00:00",
      "probability": 0.64,
      "meta_probability": 0.76,
      "current_price": 74518.8,
      "entry": 74200.0,
      "stop_loss": 73200.0,
      "take_profit": 76400.0,
      "atr": 820.0,
      "model_version": "LightGBM-v0.1 + Meta-Filter",
      "status": "open",
      "opened_at": null,
      "closed_at": null,
      "is_fallback": false
    }
  ]
  ```
- **Empty / Unavailable State**: When no active signals exist in the database, returns `[]`. Strictly no mock or fallback signals are synthesized.

### `POST /signals/transition`
Idempotently persists state changes as signals transition through their lifecycle.
- **Request Body**:
  ```json
  {
    "signal_id": 14,
    "status": "target_hit",
    "opened_at": "2026-11-09T19:00:00Z",
    "closed_at": "2026-11-09T20:15:30Z",
    "exit_price": 76400.0,
    "pnl_pct": 2.96,
    "exit_reason": "Target Hit",
    "symbol": "BTCUSDT",
    "direction": "long",
    "entry": 74200.0
  }
  ```
- **Response**:
  ```json
  {
    "status": "persisted",
    "signal_id": 14,
    "lifecycle_status": "target_hit"
  }
  ```
- **Guarantees**:
  - Updates `signals.status` to `target_hit` or `stop_hit`, ensuring the signal transitions out of Active Signals into History.
  - Commits `paper_trades` with entry price, exit price, timestamps, and realized P&L.
  - Prevents duplicate insertions or updates if the request is resent.

### `GET /history?days=30`
Returns closed paper trade history for the specified lookback window.
- **Query Parameters**:
  - `days` (int, default `30`, max `365`): Historical span in days.
- **Response**: Array of completed trade records:
  ```json
  [
    {
      "id": 105,
      "signal_id": 14,
      "symbol": "BTCUSDT",
      "timeframe": "1h",
      "direction": "long",
      "entry": 74200.0,
      "exit_price": 76400.0,
      "pnl_pct": 2.96,
      "exit_reason": "Target Hit",
      "opened_at": "2026-11-09T19:00:00+00:00",
      "closed_at": "2026-11-09T20:15:30+00:00",
      "predicted_at": "2026-11-09T18:45:00+00:00"
    }
  ]
  ```
- **Guarantees**:
  - Enforces `WHERE p.closed_at IS NOT NULL`.
  - Preserves original prediction timestamp (`predicted_at`) and timeframe from `signals`.
  - Records both wins (`Target Hit`) and losses (`Stop Loss Hit`). Never filters out losing trades.

### `GET /summary`
Returns honest performance KPIs.
- **Response**:
  ```json
  {
    "open_signals": 1,
    "symbols_scanned": 8,
    "win_rate_30d": 50.0,
    "closed_30d": 2,
    "net_pnl_30d": 1.8,
    "max_drawdown": -2.1,
    "drawdown_limit": 8.0
  }
  ```
- **Zero Fallback**: If `closed_30d == 0`, returns `win_rate_30d: 0.0` and `net_pnl_30d: 0.0`.

### `GET /equity?days=30`
Returns cumulative closed-trade equity curve points.
- **Response**:
  ```json
  [
    { "ts": "2026-10-10T19:00:00Z", "equity": 100.0 },
    { "ts": "2026-11-09T20:15:30Z", "equity": 102.96 }
  ]
  ```
- If no closed paper trades exist, returns `[]`.
