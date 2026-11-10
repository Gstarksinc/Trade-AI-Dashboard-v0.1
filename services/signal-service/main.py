"""Signal Service Main Application."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

from libs.common.logging import setup_structured_logging
from libs.common.streams import RedisStreamManager
from libs.common.metrics import setup_metrics_endpoint
try:
    from .config import settings
    from .consumer import SignalConsumer
    from .state_machine import SignalStateMachine
except (ImportError, ValueError):
    from config import settings
    from consumer import SignalConsumer
    from state_machine import SignalStateMachine

log = setup_structured_logging("signal-service")

stream_mgr = RedisStreamManager(redis_url=settings.redis_url, service_name=settings.service_name)
sm = SignalStateMachine()
consumer = SignalConsumer(stream_mgr=stream_mgr, sm=sm)
consumer_task: Optional[asyncio.Task] = None


class TransitionRequest(BaseModel):
    current_status: str
    new_status: str
    current_version: int
    trigger_event: str = "manual_api"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    log.info("Starting signal-service...")
    await stream_mgr.connect()
    consumer_task = asyncio.create_task(consumer.run())
    yield
    log.info("Stopping signal-service...")
    consumer.stop()
    if consumer_task:
        consumer_task.cancel()
    await stream_mgr.close()
    log.info("signal-service stopped.")


app = FastAPI(title="signal-service", lifespan=lifespan)
setup_metrics_endpoint(app)


@app.get("/health")
async def health():
    active = await sm.get_active_signals()
    return {
        "service": "signal-service",
        "status": "healthy",
        "active_signals_count": len(active),
        "state_transitions_count": consumer.transitions_count,
    }


@app.get("/signals/active")
async def get_active(symbol: Optional[str] = Query(None)):
    signals = await sm.get_active_signals(symbol=symbol)
    return {"signals": signals, "count": len(signals)}


@app.post("/signals/{signal_id}/transition")
async def transition_signal(signal_id: int, req: TransitionRequest):
    success = await sm.transition_state(
        signal_id=signal_id,
        current_status=req.current_status,
        new_status=req.new_status,
        current_version=req.current_version,
        trigger_event=req.trigger_event,
    )
    if not success:
        raise HTTPException(status_code=409, detail="Transition rejected (version collision or invalid transition)")

    await consumer._emit_state_change(
        sig_id=signal_id,
        symbol="N/A",
        prev=req.current_status,
        new=req.new_status,
        version=req.current_version + 1,
        trigger=req.trigger_event,
    )
    return {"status": "transitioned", "new_version": req.current_version + 1}
