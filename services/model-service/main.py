"""Model Service Main Application."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from libs.common.logging import setup_structured_logging
from libs.common.streams import RedisStreamManager
from libs.common.metrics import setup_metrics_endpoint
try:
    from .config import settings
    from .consumer import ModelConsumer
    from .registry_loader import ModelRegistryManager
except (ImportError, ValueError):
    from config import settings
    from consumer import ModelConsumer
    from registry_loader import ModelRegistryManager

log = setup_structured_logging("model-service")

stream_mgr = RedisStreamManager(redis_url=settings.redis_url, service_name=settings.service_name)
registry_mgr = ModelRegistryManager()
consumer = ModelConsumer(stream_mgr=stream_mgr, registry_mgr=registry_mgr)
consumer_task: Optional[asyncio.Task] = None
poll_task: Optional[asyncio.Task] = None


async def registry_poll_loop():
    """Periodically check model registry for newly promoted models."""
    while True:
        try:
            await registry_mgr.refresh_models()
        except Exception as e:
            log.warning("Periodic registry poll error: %s", e)
        await asyncio.sleep(settings.poll_registry_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task, poll_task
    log.info("Starting model-service...")
    await stream_mgr.connect()
    await registry_mgr.refresh_models()
    poll_task = asyncio.create_task(registry_poll_loop())
    consumer_task = asyncio.create_task(consumer.run())
    yield
    log.info("Stopping model-service...")
    consumer.stop()
    if consumer_task:
        consumer_task.cancel()
    if poll_task:
        poll_task.cancel()
    await stream_mgr.close()
    log.info("model-service stopped.")


app = FastAPI(title="model-service", lifespan=lifespan)
setup_metrics_endpoint(app)


@app.get("/health")
async def health():
    return {
        "service": "model-service",
        "status": "healthy",
        "redis": "connected" if stream_mgr.client else "disconnected",
        "champion_version": registry_mgr.champion.version if registry_mgr.champion else None,
        "challenger_version": registry_mgr.challenger.version if registry_mgr.challenger else None,
        "predictions_emitted": consumer.predictions_count,
        "shadow_predictions_emitted": consumer.shadow_predictions_count,
    }


@app.get("/models/active")
async def get_active_models():
    return {
        "champion": {
            "version": registry_mgr.champion.version,
            "metrics": registry_mgr.champion.metrics,
        } if registry_mgr.champion else None,
        "challenger": {
            "version": registry_mgr.challenger.version,
            "metrics": registry_mgr.challenger.metrics,
        } if registry_mgr.challenger else None,
    }


@app.post("/registry/reload")
async def reload_registry():
    await registry_mgr.refresh_models()
    return {
        "status": "reloaded",
        "champion": registry_mgr.champion.version if registry_mgr.champion else None,
        "challenger": registry_mgr.challenger.version if registry_mgr.challenger else None,
    }
