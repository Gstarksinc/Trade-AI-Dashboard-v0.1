# Operational Runbook & Alert Remediation

> **Monitoring Stack**: Prometheus (`:9090`), Grafana (`:3001`), Docker alert definitions in [`docker/alerts.yml`](file:///docker/alerts.yml).
> **Target Audience**: SRE / Quant Operations engineers.

---

## Alert Remediation Matrix

### 1. `MarketDataStale` (Critical)
- **Symptom**: Prometheus metric `signals_last_candle_age_seconds > 180` for $>1\text{m}$. Live kline ingestion stopped.
- **Confirm**:
  ```powershell
  docker compose logs --tail=50 market-collector
  curl -s http://localhost:8001/health
  ```
- **Fix**:
  1. Verify public internet access to `fstream.binance.com` and `fapi.binance.com`.
  2. If WebSocket connection stalled, restart collector:
     ```powershell
     docker compose restart market-collector
     ```
  3. The collector automatically runs gap backfill on startup.
- **Escalate**: If Binance REST returns HTTP 429/418, verify IP rate limits in `RateLimitBudgeter` logs.

---

### 2. `CollectorDowntime` (Critical)
- **Symptom**: `signals_collector_heartbeat_missing > 0` for $>30\text{s}$. Redis key `collector:heartbeat` absent.
- **Confirm**:
  ```powershell
  docker compose ps market-collector
  docker compose exec redis redis-cli -a redis_local_pass get collector:heartbeat
  ```
- **Fix**:
  ```powershell
  docker compose up -d market-collector
  ```
- **Escalate**: Inspect container exit code via `docker inspect signals-market-collector-1 --format='{{.State.ExitCode}}'`.

---

### 3. `StreamConsumerLagHigh` (Warning)
- **Symptom**: `signals_stream_consumer_lag > 500` for $>2\text{m}$. Consumer group is processing slower than producer stream throughput.
- **Confirm**:
  ```powershell
  docker compose exec redis redis-cli -a redis_local_pass xinfo groups candle.closed
  docker compose exec redis redis-cli -a redis_local_pass xinfo groups prediction.ready
  ```
- **Fix**:
  1. Identify lagging consumer group (e.g. `feature-service-group` or `risk-service-group`).
  2. Inspect container resource consumption:
     ```powershell
     docker stats
     ```
  3. Restart the bogged consumer service:
     ```powershell
     docker compose restart feature-service
     ```
- **Escalate**: If CPU utilization is at 100%, consider scaling worker replicas or increasing host CPU allocation in `.wslconfig`.

---

### 4. `DLQMessagesPresent` (Critical)
- **Symptom**: `signals_redis_dlq_size > 0` for $>30\text{s}$. Messages routed to `system.dlq` stream after repeated processing failures.
- **Confirm**:
  ```powershell
  docker compose exec redis redis-cli -a redis_local_pass xrange system.dlq - + COUNT 5
  ```
- **Fix**:
  1. Inspect `error_type` and `error_message` inside the DLQ event envelope.
  2. Common causes: schema mismatch, division by zero on illiquid candle, or database connection timeout.
  3. Fix root cause, deploy code fix, and replay DLQ messages if necessary.
- **Escalate**: If DLQ growth exceeds 100 messages/min, halt upstream producer to prevent poison message amplification.

---

### 5. `RedisMemoryHigh` (Warning)
- **Symptom**: `signals_redis_memory_used_bytes > 429496729` (80% of 512MB ceiling) for $>1\text{m}$.
- **Confirm**:
  ```powershell
  docker compose exec redis redis-cli -a redis_local_pass info memory
  ```
- **Fix**:
  1. Check stream lengths:
     ```powershell
     docker compose exec redis redis-cli -a redis_local_pass xlen price.tick
     docker compose exec redis redis-cli -a redis_local_pass xlen candle.closed
     ```
  2. Verify approximate trimming (`MAXLEN ~ 10000`) is executing properly.
  3. Manually trim oversized streams:
     ```powershell
     docker compose exec redis redis-cli -a redis_local_pass xtrim price.tick MAXLEN ~ 5000
     ```
- **Escalate**: If memory leaks persist, inspect unexpired key allocations with `redis-cli --bigkeys`.

---

### 6. `DailyLossLimitHalt` (Critical)
- **Symptom**: `signals_daily_loss_halt > 0`. Circuit breaker tripped due to rolling 24h realized loss exceeding 3.0% equity ceiling.
- **Confirm**:
  ```powershell
  docker compose exec db psql -U postgres -d trade_ai -c "SELECT sum(pnl_usd) FROM paper_execution.paper_trades WHERE closed_at >= now() - interval '24 hours';"
  ```
- **Fix**:
  1. Trading approvals are automatically suspended by `risk-service`.
  2. Verify all open positions have closed or have valid active stop-losses.
  3. Review recent trades for unexpected slippage or adverse selection.
  4. Trading resumes automatically once the rolling 24h loss window clears below 3.0%.

---

### 7. `FeatureDriftDetected` (Warning)
- **Symptom**: `signals_feature_drift_psi > 0.25` for $>5\text{m}$. Population Stability Index indicates feature distribution has shifted significantly from training baseline.
- **Confirm**:
  ```powershell
  docker compose exec db psql -U postgres -d trade_ai -c "SELECT * FROM model_registry.drift_reports ORDER BY detected_at DESC LIMIT 1;"
  ```
- **Fix**:
  1. Review which features exhibit highest drift (e.g., extreme volatility expansion or regime break).
  2. If the current market regime is abnormal, shadow models should be evaluated.
  3. Schedule a model retraining pipeline run in `training-service` with updated market data.

---

### 8. `ModelReloadFailure` (Critical)
- **Symptom**: `signals_model_reload_errors_total > 0`. `model-service` failed to deserialize or validate a newly enrolled champion artifact.
- **Confirm**:
  ```powershell
  docker compose logs --tail=50 model-service
  ```
- **Fix**:
  1. Verify joblib artifact existence and file permissions in `artifacts/models/`.
  2. Verify Python `lightgbm` and `scikit-learn` version compatibility between `training-service` and `model-service`.
  3. `model-service` automatically retains previous champion in memory as fallback until resolved.

---

### 9. `ApiLatencyHigh` (Warning)
- **Symptom**: P95 latency on `api-gateway` exceeds 500ms for $>2\text{m}$.
- **Confirm**:
  ```powershell
  curl -w "%{time_total}\n" -o /dev/null -s http://localhost:8000/status
  ```
- **Fix**:
  1. Check database query performance in `signals_ledger` and `model_registry`.
  2. Verify SSE client count on `GET /events/stream`.
  3. Restart API Gateway:
     ```powershell
     docker compose restart api-gateway
     ```
