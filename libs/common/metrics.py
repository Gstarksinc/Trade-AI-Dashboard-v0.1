"""Standardized Prometheus metrics for all microservices."""

from typing import Callable
from fastapi import FastAPI, Response
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# 1. Ingestion lag & Candle freshness
INGESTION_LAG_SECONDS = Gauge(
    "signals_ingestion_lag_seconds",
    "Time delta between candle close_time and ingestion completion in seconds",
    ["symbol", "timeframe"],
)
LAST_CANDLE_AGE_SECONDS = Gauge(
    "signals_last_candle_age_seconds",
    "Age in seconds of the most recent candle timestamp",
    ["symbol", "timeframe"],
)

# 2. Redis Stream & Consumer lag
STREAM_CONSUMER_LAG = Gauge(
    "signals_stream_consumer_lag",
    "Number of unacknowledged or pending messages in consumer group",
    ["stream", "group"],
)
REDIS_DLQ_SIZE = Gauge(
    "signals_redis_dlq_size",
    "Total number of dead-lettered entries in DLQ stream",
    ["stream"],
)

# 3. Model Confidence & Predictions
MODEL_CONFIDENCE = Histogram(
    "signals_model_confidence",
    "Calibrated prediction probability distribution",
    ["symbol", "timeframe", "model_version"],
    buckets=(0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.0),
)
PREDICTIONS_TOTAL = Counter(
    "signals_predictions_total",
    "Total prediction events emitted",
    ["symbol", "timeframe", "direction", "is_shadow"],
)

# 4. Signals & Lifecycles
SIGNALS_LIFECYCLE_TOTAL = Counter(
    "signals_lifecycle_total",
    "Count of signal state transitions",
    ["symbol", "state"],
)
SIGNALS_PER_DAY = Gauge(
    "signals_generated_today",
    "Signals generated in the current UTC day",
    ["symbol"],
)

# 5. Risk & Execution
RISK_DECISIONS_TOTAL = Counter(
    "signals_risk_decisions_total",
    "Count of risk evaluation approvals and rejections",
    ["symbol", "decision", "reason_category"],
)
PAPER_TRADES_TOTAL = Counter(
    "signals_paper_trades_total",
    "Paper trades executed and closed",
    ["symbol", "direction", "exit_reason"],
)

# 6. Gateway & API Latency
API_REQUEST_LATENCY = Histogram(
    "signals_api_latency_seconds",
    "API request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# 7. Infrastructure Gauges
REDIS_MEMORY_BYTES = Gauge(
    "signals_redis_memory_used_bytes",
    "Redis memory consumption in bytes",
)
DB_SIZE_BYTES = Gauge(
    "signals_db_size_bytes",
    "TimescaleDB database size in bytes",
)


def setup_metrics_endpoint(app: FastAPI) -> None:
    """Attaches standard /metrics endpoint to any FastAPI microservice."""
    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
