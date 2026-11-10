"""Paper Execution Service Main Application."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from sqlalchemy import text

from libs.database.connection import engine
from libs.database.outbox import OutboxRepository
from libs.common.logging import setup_structured_logging
from libs.common.streams import RedisStreamManager
from libs.common.metrics import setup_metrics_endpoint
try:
    from .config import settings
    from .consumer import PaperExecConsumer
    from .engine import PaperExecutionEngine
except (ImportError, ValueError):
    from config import settings
    from consumer import PaperExecConsumer
    from engine import PaperExecutionEngine

log = setup_structured_logging("paper-exec-service")

stream_mgr = RedisStreamManager(redis_url=settings.redis_url, service_name=settings.service_name)
outbox = OutboxRepository()
consumer = PaperExecConsumer(stream_mgr=stream_mgr, outbox=outbox)
consumer_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    log.info("Starting paper-exec-service...")
    await stream_mgr.connect()
    consumer_task = asyncio.create_task(consumer.run())
    yield
    log.info("Stopping paper-exec-service...")
    consumer.stop()
    if consumer_task:
        consumer_task.cancel()
    await stream_mgr.close()
    log.info("paper-exec-service stopped.")


app = FastAPI(title="paper-exec-service", lifespan=lifespan)
setup_metrics_endpoint(app)


@app.get("/health")
async def health():
    open_trades = await PaperExecutionEngine.get_open_trades()
    return {
        "service": "paper-exec-service",
        "status": "healthy",
        "open_trades_count": len(open_trades),
        "trades_opened_total": consumer.trades_opened,
        "trades_closed_total": consumer.trades_closed,
    }


@app.get("/positions/open")
async def get_open_positions():
    trades = await PaperExecutionEngine.get_open_trades()
    return {"open_positions": trades, "count": len(trades)}


@app.get("/trades/history")
async def get_trade_history(limit: int = 50):
    query = text("""
        SELECT id, signal_id, opened_at, closed_at, symbol, timeframe, direction,
               entry, exit_price, pnl_pct, pnl_usd, exit_reason
        FROM paper_execution.paper_trades
        WHERE closed_at IS NOT NULL
        ORDER BY closed_at DESC LIMIT :limit;
    """)
    async with engine.connect() as conn:
        res = await conn.execute(query, {"limit": limit})
        rows = res.fetchall()
        trades = [
            {
                "id": r[0],
                "signal_id": r[1],
                "opened_at": r[2].isoformat() if r[2] else None,
                "closed_at": r[3].isoformat() if r[3] else None,
                "symbol": r[4],
                "timeframe": r[5],
                "direction": r[6],
                "entry": float(r[7]),
                "exit_price": float(r[8]) if r[8] else None,
                "pnl_pct": float(r[9]) if r[9] else 0.0,
                "pnl_usd": float(r[10]) if r[10] else 0.0,
                "exit_reason": r[11],
            }
            for r in rows
        ]
    return {"history": trades, "count": len(trades)}


@app.get("/equity")
async def get_equity(days: int = 30):
    query = text("""
        SELECT timestamp, total_equity, closed_equity, unrealized_pnl
        FROM paper_execution.equity_curve
        WHERE timestamp >= now() - (:days || ' days')::interval
        ORDER BY timestamp ASC;
    """)
    try:
        async with engine.connect() as conn:
            res = await conn.execute(query, {"days": days})
            rows = res.fetchall()
            return [
                {
                    "timestamp": r[0].isoformat() if r[0] else None,
                    "total_equity": float(r[1]),
                    "closed_equity": float(r[2]),
                    "unrealized_pnl": float(r[3]),
                }
                for r in rows
            ]
    except Exception:
        return []
