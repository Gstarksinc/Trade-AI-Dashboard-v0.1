# Observability, Metrics & Telemetry Specification

> **Telemetry Stack**: Prometheus v2.51.0 (`:9090`), Grafana v10.4.0 (`:3001`).
> **Scrape Frequency**: Global 15s interval across all 9 containerized Python FastAPI microservices.

---

## 1. Prometheus Scrape Configuration

Prometheus (`docker/prometheus.yml`) automatically discovers and scrapes all active services every 15 seconds:

| Service / Scrape Job | Target Address | Endpoint | Purpose |
| :--- | :--- | :---: | :--- |
| `market-collector` | `market-collector:8001` | `/metrics` | Ingestion latency, WebSocket uptime, candle lag |
| `feature-service` | `feature-service:8002` | `/metrics` | Feature computation duration, pipeline lag |
| `model-service` | `model-service:8003` | `/metrics` | Inference latency, prediction rate, confidence distribution |
| `training-service` | `training-service:8004`| `/metrics` | Training duration, memory consumption |
| `risk-service` | `risk-service:8005` | `/metrics` | Sizing duration, rejection reasons, advisory lock contention |
| `signal-service` | `signal-service:8006` | `/metrics` | State transitions count, optimistic lock collisions |
| `paper-exec-service` | `paper-exec-service:8007`| `/metrics` | Fill rate, slippage, realized PnL, duration to barrier |
| `api-gateway` | `api-gateway:8000` | `/metrics` | HTTP request throughput, P50/P95 latency, SSE client count |
| `notifier-service` | `notifier-service:8009`| `/metrics` | Notification dispatch success/failure count |

---

## 2. Core Prometheus Metric Inventory

Every custom metric follows institutional naming conventions prefixed with `signals_`:

| Metric Name | Type | Labels | Description |
| :--- | :---: | :--- | :--- |
| `signals_last_candle_age_seconds` | Gauge | `symbol`, `timeframe` | Wall-clock elapsed time since latest closed candle |
| `signals_ingestion_lag_seconds` | Gauge | `symbol`, `timeframe` | Ingestion delay between Binance candle close and DB write |
| `signals_stream_consumer_lag` | Gauge | `stream`, `group` | Unprocessed pending messages in Redis consumer group |
| `signals_redis_dlq_size` | Gauge | `stream` | Count of unhandled failed messages in `system.dlq` |
| `signals_generated_today` | Counter | `symbol`, `direction` | Total predictive signals produced during current UTC day |
| `signals_lifecycle_total` | Counter | `state`, `symbol` | Authoritative signal lifecycle transitions |
| `signals_model_confidence_bucket` | Histogram | `symbol`, `model_version` | Calibrated probability distribution of inferences |
| `signals_predictions_total` | Counter | `direction`, `model_stage`| Inferences produced partitioned by champion vs. shadow |
| `signals_api_latency_seconds_bucket`| Histogram| `method`, `endpoint` | End-to-end HTTP request processing latency |
| `signals_feature_drift_psi` | Gauge | `symbol`, `feature` | Population Stability Index against training baseline |
| `signals_daily_loss_halt` | Gauge | `symbol` | Binary flag (1/0) indicating daily loss circuit breaker trip |
| `signals_collector_heartbeat_missing`| Gauge | None | Binary flag indicating missing collector heartbeat |

---

## 3. Provisioned Grafana Dashboard (`signals_overview`)

Grafana is provisioned as code via [`docker/grafana/dashboards/signals_overview.json`](file:///docker/grafana/dashboards/signals_overview.json) and [`docker/grafana/provisioning/`](file:///docker/grafana/provisioning/).

### Dashboard Panels:
1. **Ingestion Lag & Last Candle Age**:
   - Compares `signals_ingestion_lag_seconds` and `signals_last_candle_age_seconds` across all 8 perpetual symbols.
   - Highlights any symbol whose data pipeline is delayed $>60$ seconds.
2. **Stream Consumer Lag & Dead-Letter Queue (DLQ)**:
   - Tracks consumer group backlog across `candle.closed`, `features.ready`, `prediction.ready`, and `signal.approved`.
   - Real-time gauge for `system.dlq` messages.
3. **Signals Generated & State Machine Transitions**:
   - Visualizes the transition rate across `waiting_for_entry`, `order_in_progress`, `target_hit`, and `stop_hit`.
4. **Model Prediction Confidence & Inferences/Sec**:
   - Displays rolling P90 calibrated confidence per symbol and inferences/sec split by Long/Short.
5. **API Gateway Latency (P50 & P95)**:
   - Tracks REST endpoint and SSE delivery latency percentiles.

---

## 4. Alert Routing & Thresholds

Prometheus evaluates alert rules defined in `docker/alerts.yml` every 15 seconds:

- **Critical Alerts** (Page On-Call):
  - `MarketDataStale`: Candle age $>180\text{s}$ for $>1\text{m}$.
  - `CollectorDowntime`: Heartbeat missing for $>30\text{s}$.
  - `DLQMessagesPresent`: Dead-letter queue non-empty for $>30\text{s}$.
  - `DailyLossLimitHalt`: Rolling 24h loss $>3.0\%$ equity.
  - `ModelReloadFailure`: Model artifact deserialization failure.
- **Warning Alerts** (Investigate within business hours):
  - `IngestionLagHigh`: Ingestion lag $>60\text{s}$ for $>1\text{m}$.
  - `StreamConsumerLagHigh`: Consumer group lag $>500$ messages for $>2\text{m}$.
  - `RedisMemoryHigh`: Memory usage $>80\%$ of 512MB ceiling.
  - `FeatureDriftDetected`: PSI score $>0.25$ for $>5\text{m}$.
  - `ApiLatencyHigh`: Gateway P95 latency $>500\text{ms}$ for $>2\text{m}$.
