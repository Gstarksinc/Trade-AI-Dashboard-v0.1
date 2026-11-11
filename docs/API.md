# API Gateway Specification & Reference

> **Gateway Port**: `:8000` (binds `0.0.0.0:8000`)
> **OpenAPI Schema**: Serialized in [`docs/openapi.json`](file:///docs/openapi.json) and available interactively at `http://localhost:8000/docs`.
> **Scope**: Crypto futures paper trading & research only. Read-only client gateway. Zero order placement endpoints exist.

---

## 1. REST Endpoints Overview

All responses return standard JSON envelopes with UTC timestamps.

### 1. `GET /health`
Returns gateway health and Redis connectivity.
```json
{
  "service": "api-gateway",
  "status": "healthy",
  "redis": "connected",
  "timestamp": "2026-11-11T12:00:00.123456Z"
}
```

---

### 2. `GET /status`
Returns live market feed status, champion model presence, and the per-symbol / per-timeframe status matrix:
- **`market_feed_status`**: `"live"` (if `collector:heartbeat` received within 15s) or `"degraded"`.
- **`has_active_champion`**: `boolean`.
- **`champion_status_notice`**: Human-readable status banner. Currently: `"No validated model. Zero models promoted to champion or challenger."`.
- **`model_matrix`**: Status breakdown for all 8 perpetual pairs across `15m`, `1h`, and `4h`:
  - `15m`: Always `"disabled"` (suppressed by risk policy).
  - `1h` / `4h`: `"champion"`, `"shadow"`, or `"no_validated_model"`.

#### Example Response:
```json
{
  "market_feed_status": "live",
  "has_active_champion": false,
  "has_active_challenger": false,
  "champion_status_notice": "No validated model. Zero models promoted to champion or challenger.",
  "model_matrix": {
    "BTCUSDT": {
      "15m": { "status": "disabled", "label": "Disabled", "reason": "15m timeframe disabled by risk policy", "active_model": null },
      "1h": { "status": "no_validated_model", "label": "No validated model", "reason": "Promotion gates failed on historical empirical audit", "active_model": null },
      "4h": { "status": "no_validated_model", "label": "No validated model", "reason": "Promotion gates failed on historical empirical audit", "active_model": null }
    }
  }
}
```

---

### 3. `GET /signals`
Fetches active trading signals from `signal-service`. If a symbol has no active confirmed signal, it populates a neutral `"waiting_for_confirmation"` placeholder.

#### Example Response:
```json
{
  "active_signals": [],
  "waiting_confirmation": [
    {
      "symbol": "BTCUSDT",
      "timeframe": "1h",
      "direction": "neutral",
      "status": "waiting_for_confirmation",
      "is_genuine": true,
      "entry": 0.0,
      "stop_loss": 0.0,
      "take_profit": 0.0
    }
  ],
  "is_fallback": false
}
```

---

### 4. `GET /history?limit=50`
Queries `paper-exec-service` for completed paper trade records.
- **Parameters**: `limit` (integer, default `50`, max `500`).
- **Response**: Array of trade objects (`id`, `symbol`, `direction`, `entry`, `exit_price`, `pnl_usd`, `pnl_pct`, `fees`, `funding`, `exit_reason`, `opened_at`, `closed_at`).

---

### 5. `GET /summary`
Returns virtual paper trading account summary.
```json
{
  "account_type": "PAPER TRADING / RESEARCH",
  "virtual_balance_usd": 10000.0,
  "total_equity_usd": 10000.0,
  "used_margin_usd": 0.0,
  "available_margin_usd": 10000.0,
  "daily_pnl_usd": 0.0,
  "total_pnl_usd": 0.0,
  "open_trades_count": 0
}
```

---

### 6. `GET /equity?days=30`
Returns historical paper portfolio equity data points for chart rendering.

---

### 7. `GET /metrics`
Scraped by Prometheus on port `8000`. Exposes standard FastAPI and custom HTTP request latency metrics (`api_request_duration_seconds`).

---

## 2. Server-Sent Events (SSE) Stream

### Endpoint: `GET /events/stream`
Multiplexed event stream powering the Next.js live ticker bar, active positions, and signal cards.

#### Client Request Headers:
```http
GET /events/stream HTTP/1.1
Host: localhost:8000
Accept: text/event-stream
Last-Event-ID: 1731326400000-0
```

#### Protocol Features:
1. **Keep-Alive Heartbeat**: Sends a comment `: heartbeat\n\n` every 15 seconds to prevent intermediate proxy timeouts.
2. **Throttled Price Ticks**: Real-time prices from the fast Redis cache `price:{symbol}` are streamed at a maximum frequency of **1 tick per second per symbol**, reducing frontend DOM thrashing.
3. **Event Replay via `Last-Event-ID`**: When reconnecting after a network drop, the client can pass `Last-Event-ID`. The gateway replays missed `signal.state_changed` messages from the Redis Stream history.

#### Stream Format Example:
```text
: heartbeat

event: price.tick
data: {"symbol": "BTCUSDT", "mark_price": 50001.0, "timestamp": "2026-11-11T12:00:01.050Z"}

event: signal.state_changed
id: 1731326402150-0
data: {"signal_id": 999, "symbol": "BTCUSDT", "new_state": "order_in_progress", "version": 2}
```

---

## 3. Error Handling & Security

- **Status Codes**: Standard HTTP codes (`400 Bad Request`, `404 Not Found`, `502 Bad Gateway`, `503 Service Unavailable`).
- **No Mutating Endpoints**: There are zero POST/PUT/DELETE endpoints exposed on the public gateway for trade placement, limit order modification, or state transitions. The API is strictly read-only.
- **CORS Configuration**: Gateway permits CORS from `*` for local development, allowing the Next.js frontend on port 3000 to consume REST and SSE streams seamlessly.

