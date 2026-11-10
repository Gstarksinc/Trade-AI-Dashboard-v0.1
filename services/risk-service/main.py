"""Risk Service Main Application."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from libs.common.logging import setup_structured_logging
from libs.common.streams import RedisStreamManager
from libs.common.metrics import setup_metrics_endpoint
try:
    from .config import settings
    from .consumer import RiskConsumer
    from .evaluator import RiskEvaluator
except (ImportError, ValueError):
    from config import settings
    from consumer import RiskConsumer
    from evaluator import RiskEvaluator

log = setup_structured_logging("risk-service")

stream_mgr = RedisStreamManager(redis_url=settings.redis_url, service_name=settings.service_name)
consumer = RiskConsumer(stream_mgr=stream_mgr)
consumer_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    log.info("Starting risk-service...")
    await stream_mgr.connect()
    consumer_task = asyncio.create_task(consumer.run())
    yield
    log.info("Stopping risk-service...")
    consumer.stop()
    if consumer_task:
        consumer_task.cancel()
    await stream_mgr.close()
    log.info("risk-service stopped.")


app = FastAPI(title="risk-service", lifespan=lifespan)
setup_metrics_endpoint(app)


@app.get("/health")
async def health():
    equity = await RiskEvaluator.get_current_equity()
    open_pos = await RiskEvaluator.get_open_positions()
    return {
        "service": "risk-service",
        "status": "healthy",
        "current_equity": equity,
        "open_positions_count": len(open_pos),
        "approved_count": consumer.approved_count,
        "rejected_count": consumer.rejected_count,
        "max_leverage": settings.max_leverage,
    }
