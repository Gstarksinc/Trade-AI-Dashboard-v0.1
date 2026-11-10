"""Signal Service Consumer with In-Memory Per-Symbol Index for Zero-Latency Tick Processing."""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Optional, Set
from libs.common.streams import RedisStreamManager
from libs.contracts.events import (
    PriceTickEvent,
    SignalApprovedEvent,
    SignalStateChangedEvent,
    SignalStateChangedPayload,
)
try:
    from .config import settings
    from .state_machine import SignalStateMachine
except (ImportError, ValueError):
    from config import settings
    from state_machine import SignalStateMachine

log = logging.getLogger("signal-service.consumer")


class SignalConsumer:
    def __init__(self, stream_mgr: RedisStreamManager, sm: SignalStateMachine):
        self.stream_mgr = stream_mgr
        self.sm = sm
        self.running = False
        self.transitions_count = 0
        # In-memory per-symbol index of active signals: symbol -> {signal_id: signal_dict}
        self._active_by_symbol: Dict[str, Dict[int, dict]] = {}

    async def warm_active_cache(self):
        """Loads all active signals from DB into in-memory index on startup."""
        try:
            active = await self.sm.get_active_signals()
            self._active_by_symbol.clear()
            for sig in active:
                sym = sig["symbol"]
                if sym not in self._active_by_symbol:
                    self._active_by_symbol[sym] = {}
                self._active_by_symbol[sym][sig["id"]] = sig
            log.info("Warmed active signal cache: %d signals across %d symbols", len(active), len(self._active_by_symbol))
        except Exception as e:
            log.warning("Active cache warming failed: %s", e)

    async def handle_signal_approved(self, event_data: dict):
        event = SignalApprovedEvent(**event_data)
        p = event.payload
        signal_id = await self.sm.create_signal_from_approved(p.model_dump())
        if signal_id:
            sig_dict = {
                "id": signal_id,
                "symbol": p.symbol,
                "timeframe": p.timeframe,
                "direction": p.direction,
                "entry": p.entry,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit,
                "status": "waiting_for_entry",
                "version": 1,
            }
            # Update in-memory index
            if p.symbol not in self._active_by_symbol:
                self._active_by_symbol[p.symbol] = {}
            self._active_by_symbol[p.symbol][signal_id] = sig_dict

            log.info("Indexed approved signal #%d for %s (%s)", signal_id, p.symbol, p.direction)
            state_event = SignalStateChangedEvent(
                idempotency_key=f"signal_{signal_id}_created",
                producer="signal-service",
                payload=SignalStateChangedPayload(
                    signal_id=signal_id,
                    symbol=p.symbol,
                    previous_state="waiting_for_confirmation",
                    new_state="waiting_for_entry",
                    trigger_event="signal.approved",
                    version=1,
                ),
            )
            await self.stream_mgr.publish("signal.state_changed", state_event)

    async def handle_price_tick(self, event_data: dict):
        event = PriceTickEvent(**event_data)
        tick = event.payload
        symbol = tick.symbol
        mark_price = tick.mark_price

        # O(1) in-memory check — no DB queries unless active signals exist for this symbol!
        active_for_sym = self._active_by_symbol.get(symbol)
        if not active_for_sym:
            return

        for sig_id, sig in list(active_for_sym.items()):
            status = sig["status"]
            direction = sig["direction"].lower()
            entry = sig["entry"]
            sl = sig["stop_loss"]
            version = sig["version"]

            if status == "waiting_for_entry":
                if direction == "long":
                    if mark_price <= sl:
                        success = await self.sm.transition_state(sig_id, status, "invalidated", version, "price_breached_sl_before_entry")
                        if success:
                            active_for_sym.pop(sig_id, None)
                            await self._emit_state_change(sig_id, symbol, status, "invalidated", version + 1, "invalidated_by_tick")
                    elif mark_price <= entry:
                        success = await self.sm.transition_state(sig_id, status, "order_in_progress", version, "price_touched_entry")
                        if success:
                            sig["status"] = "order_in_progress"
                            sig["version"] = version + 1
                            await self._emit_state_change(sig_id, symbol, status, "order_in_progress", version + 1, "entry_touched")

                elif direction == "short":
                    # SHORT SIDE VERIFIED:
                    # Invalidation if price rallies up past stop loss (mark_price >= sl) before entry
                    if mark_price >= sl:
                        success = await self.sm.transition_state(sig_id, status, "invalidated", version, "price_breached_sl_before_entry")
                        if success:
                            active_for_sym.pop(sig_id, None)
                            await self._emit_state_change(sig_id, symbol, status, "invalidated", version + 1, "invalidated_by_tick")
                    elif mark_price >= entry:
                        # Short limit fills when price rallies up to entry
                        success = await self.sm.transition_state(sig_id, status, "order_in_progress", version, "price_touched_entry")
                        if success:
                            sig["status"] = "order_in_progress"
                            sig["version"] = version + 1
                            await self._emit_state_change(sig_id, symbol, status, "order_in_progress", version + 1, "entry_touched")

    async def _emit_state_change(self, sig_id: int, symbol: str, prev: str, new: str, version: int, trigger: str):
        self.transitions_count += 1
        event = SignalStateChangedEvent(
            idempotency_key=f"sig_{sig_id}_v{version}_{new}",
            producer="signal-service",
            payload=SignalStateChangedPayload(
                signal_id=sig_id,
                symbol=symbol,
                previous_state=prev,
                new_state=new,
                trigger_event=trigger,
                version=version,
            ),
        )
        await self.stream_mgr.publish("signal.state_changed", event)

    async def run(self):
        self.running = True
        await self.warm_active_cache()
        log.info("Starting signal consumers...")
        task_approved = asyncio.create_task(
            self.stream_mgr.consume_loop("signal.approved", settings.consumer_group, f"{settings.consumer_name}-approved", self.handle_signal_approved)
        )
        task_ticks = asyncio.create_task(
            self.stream_mgr.consume_loop("price.tick", settings.consumer_group, f"{settings.consumer_name}-ticks", self.handle_price_tick)
        )
        await asyncio.gather(task_approved, task_ticks)

    def stop(self):
        self.running = False
