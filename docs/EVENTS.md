# Event Contracts & Redis Streams Specification

> **Contract Enforcement**: All event schemas inherit from `BaseEvent` and are defined in [`libs/contracts/events.py`](file:///libs/contracts/events.py).
> **Bus Technology**: Redis 7 Streams with persistent consumer groups, approximate stream trimming (`MAXLEN ~ 10000`), automatic acknowledgement (`XACK`), and Dead-Letter Queue (`system.dlq`).

---

## 1. Stream & Consumer Group Topology

| Redis Stream Name | Producing Service | Consuming Services & Consumer Groups | MAXLEN | DLQ Enabled |
| :--- | :--- | :--- | :---: | :---: |
| `price.tick` | `market-collector` | `paper-exec-service` (`paper-exec-group`), `api-gateway` (Direct read) | `10000` | Yes |
| `candle.closed` | `market-collector` | `feature-service` (`feature-service-group`) | `10000` | Yes |
| `features.ready` | `feature-service` | `model-service` (`model-service-group`) | `10000` | Yes |
| `prediction.ready` | `model-service` | `risk-service` (`risk-service-group`) | `10000` | Yes |
| `signal.approved` | `risk-service` | `signal-service` (`signal-service-group`), `notifier-service` (`notifier-group`) | `10000` | Yes |
| `signal.rejected` | `risk-service` | `notifier-service` (`notifier-group`) | `10000` | Yes |
| `signal.state_changed`| `signal-service` | `paper-exec-service` (`paper-exec-group`), `api-gateway` (SSE stream) | `10000` | Yes |
| `trade.closed` | `paper-exec-service` | `signal-service` (`signal-service-group`), `notifier-service` (`notifier-group`) | `10000` | Yes |
| `system.dlq` | Any Service Client | Operations Monitoring / SRE Alerts | `10000` | N/A |

---

## 2. Common Event Envelope (`BaseEvent`)

Every event published to Redis Streams wraps its payload in a standardized envelope:

```json
{
  "event_id": "c1f7b702-8d9e-4e4c-83b6-123456789abc",
  "event_type": "candle.closed",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:00:00.123456Z",
  "idempotency_key": "kline-BTCUSDT-1h-1731326400000",
  "producer": "market-collector",
  "payload": { ... }
}
```

### Envelope Fields:
- `event_id` (`str`, UUID4): Unique identifier generated for every message occurrence.
- `event_type` (`str`): Dot-separated event type string.
- `event_version` (`str`): Semantic version of the event schema (default `"1.0"`).
- `timestamp` (`str` / `int`, ISO-8601 UTC): Creation timestamp.
- `idempotency_key` (`str`): Deterministic key derived from domain parameters (e.g. `{symbol}-{timeframe}-{open_time}`) preventing duplicate execution.
- `producer` (`str`): Name of the microservice producing the event.
- `payload` (`dict`): Strongly typed domain payload.

---

## 3. Event Specifications & JSON Schemas

### 1. `price.tick` (`PriceTickEvent`)
High-frequency market price tick published by `market-collector`. Also updates Redis key `price:{symbol}`.
```json
{
  "event_id": "4b68e987-9755-46b5-827b-272da5ef7bb1",
  "event_type": "price.tick",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:00:01.050Z",
  "idempotency_key": "tick-BTCUSDT-1731326401050",
  "producer": "market-collector",
  "payload": {
    "symbol": "BTCUSDT",
    "price": 50000.50,
    "high_24h": 51200.00,
    "low_24h": 49100.00,
    "volume_24h": 18452.12,
    "quote_volume_24h": 922606000.00,
    "price_change_24h": 1.25,
    "mark_price": 50001.00,
    "index_price": 50000.80,
    "bid_price": 50000.40,
    "ask_price": 50000.60,
    "funding_rate": 0.0001,
    "tick_dir": "up",
    "ts": 1731326401050
  }
}
```

### 2. `candle.closed` (`CandleClosedEvent`)
Emitted by `market-collector` immediately after an OHLCV candle bar closes and is persisted to `market_data.candles`.
```json
{
  "event_id": "3e9b1102-4f32-4e0a-bf47-975a6be4e3f1",
  "event_type": "candle.closed",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:00:00.250Z",
  "idempotency_key": "candle-BTCUSDT-1h-20261111120000",
  "producer": "market-collector",
  "payload": {
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "open_time": "2026-11-11T11:00:00Z",
    "close_time": "2026-11-11T11:59:59.999Z",
    "open": 49500.00,
    "high": 50200.00,
    "low": 49400.00,
    "close": 50000.00,
    "volume": 1250.45,
    "quote_volume": 62522500.00,
    "trades": 45210,
    "taker_buy_base": 650.20,
    "taker_buy_quote": 32510000.00
  }
}
```

### 3. `features.ready` (`FeaturesReadyEvent`)
Emitted by `feature-service` after computing all 48 point-in-time features on a closed candle.
```json
{
  "event_id": "99c89e22-6b3a-4efb-8664-8841da3d5402",
  "event_type": "features.ready",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:00:01.120Z",
  "idempotency_key": "feat-BTCUSDT-1h-20261111120000",
  "producer": "feature-service",
  "payload": {
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "candle_open_time": "2026-11-11T11:00:00Z",
    "feature_set_version": "v1.0.0",
    "close_price": 50000.00,
    "features": {
      "ema_9": 49800.5,
      "ema_21": 49600.2,
      "rsi_14": 56.4,
      "macd": 120.5,
      "macd_signal": 105.2,
      "macd_hist": 15.3,
      "atr_14": 1000.0,
      "natr_14": 2.0,
      "bb_width": 0.045,
      "adx_14": 26.8,
      "btc_correlation_48": 1.0,
      "hour_sin": 0.0,
      "hour_cos": 1.0
    }
  }
}
```

### 4. `prediction.ready` (`PredictionReadyEvent`)
Emitted by `model-service` containing the calibrated probability and meta-model confidence score.
```json
{
  "event_id": "18c73491-9251-46bb-864c-b17b62e49c71",
  "event_type": "prediction.ready",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:00:01.850Z",
  "idempotency_key": "pred-BTCUSDT-1h-20261111120000",
  "producer": "model-service",
  "payload": {
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "candle_open_time": "2026-11-11T11:00:00Z",
    "direction": "long",
    "probability": 0.70,
    "meta_probability": 0.78,
    "raw_probability": 0.72,
    "calibrated_probability": 0.70,
    "meta_confidence": 0.78,
    "current_price": 50000.00,
    "atr": 1000.00,
    "model_version": "LGBM-V31-BTCUSDT-1h-20261111120000",
    "feature_set_version": "v1.0.0",
    "is_shadow": false
  }
}
```

### 5. `signal.approved` (`SignalApprovedEvent`)
Emitted by `risk-service` after advisory-locked risk checks, margin reservation, and position sizing pass.
```json
{
  "event_id": "673d3210-2ab1-46c5-8490-252da3f848ab",
  "event_type": "signal.approved",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:00:02.050Z",
  "idempotency_key": "sigapp-BTCUSDT-1h-20261111120000",
  "producer": "risk-service",
  "payload": {
    "prediction_event_id": "18c73491-9251-46bb-864c-b17b62e49c71",
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "direction": "long",
    "entry": 50000.00,
    "stop_loss": 49000.00,
    "take_profit": 52000.00,
    "atr": 1000.00,
    "position_size_usd": 2500.00,
    "leverage": 0.25,
    "risk_pct": 0.50,
    "reward_pct": 1.00,
    "rr_ratio": 2.0,
    "regime": "trending",
    "model_version": "LGBM-V31-BTCUSDT-1h-20261111120000",
    "feature_set_version": "v1.0.0",
    "candle_open_time": "2026-11-11T11:00:00Z",
    "expires_at": "2026-11-11T13:00:00Z"
  }
}
```

### 6. `signal.rejected` (`SignalRejectedEvent`)
Emitted by `risk-service` when a candidate prediction fails risk gates, circuit breakers, or exposure caps.
```json
{
  "event_id": "78fa1b20-843e-4ba0-a7d1-12c8b9d31122",
  "event_type": "signal.rejected",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:00:02.040Z",
  "idempotency_key": "sigrej-ETHUSDT-1h-20261111120000",
  "producer": "risk-service",
  "payload": {
    "prediction_event_id": "99f84812-74c1-4822-b9e1-2248ab48c1a1",
    "symbol": "ETHUSDT",
    "timeframe": "1h",
    "direction": "long",
    "rejection_reason": "Cost-to-risk ratio (22.5%) exceeds maximum threshold (20.0%)",
    "details": {
      "friction_pct": 0.0014,
      "sl_distance_pct": 0.0062,
      "cost_to_risk": 0.2258
    }
  }
}
```

### 7. `signal.state_changed` (`SignalStateChangedEvent`)
Emitted by `signal-service` upon every authoritative state machine transition. Includes the optimistic locking sequence `version`.
```json
{
  "event_id": "99120485-a741-48e0-bb12-8874125da982",
  "event_type": "signal.state_changed",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:00:02.150Z",
  "idempotency_key": "state-999-waiting_for_entry-v1",
  "producer": "signal-service",
  "payload": {
    "signal_id": 999,
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "direction": "long",
    "from_state": null,
    "to_state": "waiting_for_entry",
    "previous_state": null,
    "new_state": "waiting_for_entry",
    "trigger_event": "signal.approved",
    "entry": 50000.00,
    "stop_loss": 49000.00,
    "take_profit": 52000.00,
    "predicted_at": "2026-11-11T12:00:00Z",
    "version": 1
  }
}
```

### 8. `trade.closed` (`TradeClosedEvent`)
Emitted by `paper-exec-service` (sole exit owner) when Take Profit or Stop Loss barriers are breached on live price ticks.
```json
{
  "event_id": "91ba2045-812e-4b61-9c88-14238ab90124",
  "event_type": "trade.closed",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:45:00.120Z",
  "idempotency_key": "tradeclosed-888-999-target_hit",
  "producer": "paper-exec-service",
  "payload": {
    "trade_id": 888,
    "signal_id": 999,
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "direction": "long",
    "entry": 50000.00,
    "exit_price": 52000.00,
    "leverage": 2.0,
    "fees": 3.50,
    "funding": 0.20,
    "pnl_pct": 3.86,
    "pnl_usd": 96.30,
    "exit_reason": "target_hit",
    "opened_at": "2026-11-11T12:05:00Z",
    "closed_at": "2026-11-11T12:45:00Z",
    "predicted_at": "2026-11-11T12:00:00Z",
    "duration_sec": 2400,
    "time_to_target_sec": 2400,
    "high_low_reconciled": false
  }
}
```

### 9. `system.dlq` (`SystemDLQEvent`)
Dead-Letter Queue event emitted when a consumer group exhausts retry attempts on a poisoned or unparseable message.
```json
{
  "event_id": "ff012841-3841-470a-bd44-998811223344",
  "event_type": "system.dlq",
  "event_version": "1.0",
  "timestamp": "2026-11-11T12:00:05.100Z",
  "idempotency_key": "dlq-c1f7b702-1731326405100",
  "producer": "feature-service",
  "payload": {
    "failed_service": "feature-service",
    "original_stream": "candle.closed",
    "consumer_group": "feature-service-group",
    "error_type": "ValueError",
    "error_message": "Invalid OHLCV candle: close price <= 0",
    "raw_payload": "{\"symbol\": \"BTCUSDT\", \"close\": -1.0}",
    "retry_count": 3,
    "first_failed_at": "2026-11-11T12:00:02.100Z"
  }
}
```
