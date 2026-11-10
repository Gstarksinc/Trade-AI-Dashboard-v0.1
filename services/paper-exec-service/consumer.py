"""Paper Execution Consumer: Listens for order_in_progress transitions and price ticks."""

import asyncio
from datetime import datetime, timezone
import logging
from sqlalchemy import text

from libs.database.connection import engine
from libs.database.outbox import OutboxRepository
from libs.common.streams import RedisStreamManager
from libs.contracts.events import (
    PriceTickEvent,
    SignalStateChangedEvent,
    TradeClosedEvent,
    TradeClosedPayload,
)
try:
    from .config import settings
    from .engine import PaperExecutionEngine
except (ImportError, ValueError):
    from config import settings
    from engine import PaperExecutionEngine

log = logging.getLogger("paper-exec-service.consumer")


class PaperExecConsumer:
    def __init__(self, stream_mgr: RedisStreamManager, outbox: OutboxRepository):
        self.stream_mgr = stream_mgr
        self.outbox = outbox
        self.running = False
        self.trades_opened = 0
        self.trades_closed = 0

    async def handle_signal_state_changed(self, event_data: dict):
        event = SignalStateChangedEvent(**event_data)
        p = event.payload

        if p.new_state == "order_in_progress":
            # Fetch signal parameters to open trade
            query = text("""
                SELECT symbol, timeframe, direction, entry
                FROM signals_ledger.signals
                WHERE id = :signal_id;
            """)
            async with engine.connect() as conn:
                res = await conn.execute(query, {"signal_id": p.signal_id})
                row = res.fetchone()
                if row:
                    sym, tf, direction, entry = row[0], row[1], row[2], float(row[3])
                    trade_id = await PaperExecutionEngine.open_trade(
                        signal_id=p.signal_id,
                        symbol=sym,
                        timeframe=tf,
                        direction=direction,
                        entry_price=entry,
                        leverage=2.0,
                    )
                    if trade_id:
                        self.trades_opened += 1

    async def handle_price_tick(self, event_data: dict):
        event = PriceTickEvent(**event_data)
        tick = event.payload
        symbol = tick.symbol
        mark_price = tick.mark_price

        closed_trades = await PaperExecutionEngine.evaluate_tick_exits(symbol=symbol, mark_price=mark_price)
        for c in closed_trades:
            self.trades_closed += 1
            # Publish trade.closed event
            closed_event = TradeClosedEvent(
                idempotency_key=f"trade_{c['trade_id']}_closed",
                producer="paper-exec-service",
                payload=TradeClosedPayload(
                    trade_id=c["trade_id"],
                    signal_id=c["signal_id"],
                    symbol=c["symbol"],
                    direction=c["direction"],
                    entry_price=c["entry_price"],
                    exit_price=c["exit_price"],
                    exit_reason=c["exit_reason"],
                    duration_seconds=c["duration_seconds"],
                    gross_pnl_usd=c["net_pnl_usd"],  # Approximate
                    net_pnl_usd=c["net_pnl_usd"],
                    funding_fees=0.0,
                ),
            )
            await self.stream_mgr.publish("trade.closed", closed_event)
            # Transactional Outbox write
            await self.outbox.save_event("trade.closed", closed_event)

    async def run(self):
        self.running = True
        log.info("Starting paper execution consumers...")
        task_states = asyncio.create_task(
            self.stream_mgr.consume_loop("signal.state_changed", settings.consumer_group, f"{settings.consumer_name}-states", self.handle_signal_state_changed)
        )
        task_ticks = asyncio.create_task(
            self.stream_mgr.consume_loop("price.tick", settings.consumer_group, f"{settings.consumer_name}-ticks", self.handle_price_tick)
        )
        await asyncio.gather(task_states, task_ticks)

    def stop(self):
        self.running = False

