"""Feature Service Main Application."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from libs.common.logging import setup_structured_logging
from libs.common.streams import RedisStreamManager
from libs.common.metrics import setup_metrics_endpoint
try:
    from .config import settings
    from .consumer import FeatureConsumer
    from .storage import FeatureStorage
except (ImportError, ValueError):
    from config import settings
    from consumer import FeatureConsumer
    from storage import FeatureStorage

log = setup_structured_logging("feature-service")

storage = FeatureStorage()
stream_mgr = RedisStreamManager(redis_url=settings.redis_url, service_name=settings.service_name)
consumer = FeatureConsumer(stream_mgr=stream_mgr, storage=storage)
consumer_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    log.info("Starting feature-service...")
    await stream_mgr.connect()
    consumer_task = asyncio.create_task(consumer.run())
    yield
    log.info("Stopping feature-service...")
    consumer.stop()
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    await stream_mgr.close()
    log.info("feature-service stopped.")


app = FastAPI(title="feature-service", lifespan=lifespan)
setup_metrics_endpoint(app)


@app.get("/health")
async def health():
    return {
        "service": "feature-service",
        "status": "healthy",
        "feature_set_version": settings.feature_set_version,
        "redis": "connected" if stream_mgr.client else "disconnected",
        "consumer_running": consumer.running,
        "processed_count": consumer.processed_count,
    }


@app.get("/features/latest")
async def get_latest_features(
    symbol: str = Query(..., example="BTCUSDT"),
    timeframe: str = Query("15m", example="15m"),
):
    df = await storage.load_closed_candles(symbol, timeframe, limit=5)
    if df.empty:
        raise HTTPException(status_code=404, detail="No closed candles found")
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "latest_candle_time": df.iloc[-1]["open_time"].isoformat(),
        "close": float(df.iloc[-1]["close"]),
    }
