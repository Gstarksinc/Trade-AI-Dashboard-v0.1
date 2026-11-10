"""Market Collector Service Main Application."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from typing import Dict, Optional
from fastapi import FastAPI, BackgroundTasks, Response
from libs.common.logging import setup_structured_logging
from libs.common.streams import RedisStreamManager
from libs.common.metrics import (
    setup_metrics_endpoint,
    INGESTION_LAG_SECONDS,
    LAST_CANDLE_AGE_SECONDS,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
try:
    from .config import settings
    from .binance_rest import BinanceRestClient
    from .binance_ws import BinanceWsClient
    from .gap_detector import GapDetector
    from .rate_limiter import RateLimitBudgeter
    from .storage import MarketDataStorage
except (ImportError, ValueError):
    from config import settings
    from binance_rest import BinanceRestClient
    from binance_ws import BinanceWsClient
    from gap_detector import GapDetector
    from rate_limiter import RateLimitBudgeter
    from storage import MarketDataStorage

log = setup_structured_logging("market-collector")

budgeter = RateLimitBudgeter(max_weight_per_min=settings.rate_limit_weight_limit)
rest_client = BinanceRestClient(base_url=settings.binance_fapi_url, budgeter=budgeter)
storage = MarketDataStorage()
gap_detector = GapDetector(rest_client=rest_client, storage=storage)
stream_mgr = RedisStreamManager(redis_url=settings.redis_url, service_name=settings.service_name)
ws_client = BinanceWsClient(
    symbols=settings.symbols,
    timeframes=settings.timeframes,
    stream_mgr=stream_mgr,
    gap_detector=gap_detector,
    storage=storage,
)

bg_tasks = []


async def poll_funding_and_oi():
    """Periodic job for funding rates and open interest."""
    while True:
        try:
            for sym in settings.symbols:
                try:
                    # Funding rates
                    rates = await rest_client.funding_rates(sym, limit=5)
                    rows = []
                    for r in rates:
                        rows.append({
                            "symbol": sym,
                            "funding_time": datetime.fromtimestamp(int(r["fundingTime"]) / 1000.0, tz=timezone.utc),
                            "funding_rate": float(r["fundingRate"]),
                            "mark_price": float(r.get("markPrice", 0.0)),
                        })
                    await storage.insert_funding_rates(rows)

                    # Open interest
                    oi_records = await rest_client.open_interest_hist(sym, period="15m", limit=5)
                    oi_rows = []
                    for oi in oi_records:
                        oi_rows.append({
                            "symbol": sym,
                            "timeframe": "15m",
                            "timestamp": datetime.fromtimestamp(int(oi["timestamp"]) / 1000.0, tz=timezone.utc),
                            "open_interest": float(oi["sumOpenInterest"]),
                            "open_interest_value": float(oi["sumOpenInterestValue"]),
                        })
                    await storage.insert_open_interest(oi_rows)
                except Exception as e:
                    log.warning("Metric poll error for %s: %s", sym, e)
        except Exception as e:
            log.exception("Funding/OI poll loop error: %s", e)

        await asyncio.sleep(settings.oi_poll_seconds)


async def heartbeat_loop():
    """Periodically publish heartbeat into Redis for monitoring."""
    while True:
        try:
            if stream_mgr.client:
                now_iso = datetime.now(timezone.utc).isoformat()
                await stream_mgr.client.set("collector:heartbeat", now_iso)
        except Exception:
            pass
        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting market-collector service...")
    await stream_mgr.connect()

    # Cold start backfill on startup if enabled
    if settings.enable_backfill_on_startup:
        try:
            log.info("Running startup backfill...")
            await gap_detector.run_full_backfill(settings.symbols, settings.timeframes)
        except Exception as e:
            log.warning("Startup backfill failed (will retry in background): %s", e)

    # Launch WebSocket ingest
    if settings.enable_ws:
        bg_tasks.append(asyncio.create_task(ws_client.run()))

    # Launch background polling tasks
    bg_tasks.append(asyncio.create_task(poll_funding_and_oi()))
    bg_tasks.append(asyncio.create_task(heartbeat_loop()))

    yield

    log.info("Stopping market-collector...")
    ws_client.stop()
    for t in bg_tasks:
        t.cancel()
    await rest_client.close()
    await stream_mgr.close()
    log.info("market-collector stopped cleanly.")


app = FastAPI(title="market-collector", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "service": "market-collector",
        "status": "healthy",
        "ws_running": ws_client.running,
        "redis": "connected" if stream_mgr.client else "disconnected",
        "used_rate_weight": budgeter.used_weight,
        "symbols_tracked": len(settings.symbols),
        "timeframes": settings.timeframes,
    }


@app.get("/metrics")
async def metrics():
    now = datetime.now(timezone.utc)
    for sym in settings.symbols:
        for tf in settings.timeframes:
            t = await storage.get_latest_candle_time(sym, tf)
            if t:
                age = max(0.0, (now - t).total_seconds())
                LAST_CANDLE_AGE_SECONDS.labels(symbol=sym, timeframe=tf).set(age)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/backfill")
async def trigger_backfill(background_tasks: BackgroundTasks):
    background_tasks.add_task(gap_detector.run_full_backfill, settings.symbols, settings.timeframes)
    return {"status": "backfill_started"}
