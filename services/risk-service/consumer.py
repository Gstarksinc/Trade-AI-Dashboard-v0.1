"""Risk Service Stream Consumer."""

import asyncio
from datetime import datetime, timezone
import logging
from sqlalchemy import text

from libs.database.connection import engine
from libs.common.streams import RedisStreamManager
from libs.contracts.events import (
    PredictionReadyEvent,
    SignalApprovedEvent,
    SignalRejectedEvent,
    SignalRiskDecisionPayload,
)
try:
    from .config import settings
    from .evaluator import RiskEvaluator
except (ImportError, ValueError):
    from config import settings
    from evaluator import RiskEvaluator

log = logging.getLogger("risk-service.consumer")


class RiskConsumer:
    def __init__(self, stream_mgr: RedisStreamManager):
        self.stream_mgr = stream_mgr
        self.running = False
        self.approved_count = 0
        self.rejected_count = 0

    async def get_latest_atr(self, symbol: str, timeframe: str) -> float:
        """Loads latest ATR from feature store."""
        try:
            query = text("""
                SELECT features->>'atr_14' FROM feature_store.features
                WHERE symbol = :symbol AND timeframe = :timeframe
                ORDER BY candle_open_time DESC LIMIT 1;
            """)
            async with engine.connect() as conn:
                res = await conn.execute(query, {"symbol": symbol, "timeframe": timeframe})
                row = res.fetchone()
                if row and row[0]:
                    return float(row[0])
        except Exception:
            pass
        return 0.0

    async def handle_prediction_ready(self, event_data: dict):
        event = PredictionReadyEvent(**event_data)
        payload = event.payload

        # Ignore shadow mode predictions from challenger models
        if payload.is_shadow:
            log.debug("Skipping shadow prediction for %s (%s)", payload.symbol, payload.model_version)
            return

        symbol = payload.symbol
        timeframe = payload.timeframe
        direction = payload.direction
        candle_open_time = payload.candle_open_time

        # Retrieve latest price from Redis fast cache
        current_price = await self.stream_mgr.get_latest_price(symbol)
        if not current_price or current_price <= 0:
            log.warning("No price tick available for %s", symbol)
            return

        atr = await self.get_latest_atr(symbol, timeframe)
        if atr <= 0:
            atr = current_price * 0.01

        approved, sizing, reason = await RiskEvaluator.evaluate_and_reserve(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            calibrated_probability=payload.calibrated_probability,
            meta_confidence=payload.meta_confidence,
            current_price=current_price,
            atr=atr,
        )

        idempotency_key = f"{symbol}:{timeframe}:{candle_open_time.isoformat()}:{direction}"

        if approved and sizing:
            decision_payload = SignalRiskDecisionPayload(
                symbol=symbol,
                timeframe=timeframe,
                candle_open_time=candle_open_time,
                direction=direction,
                probability=payload.calibrated_probability,
                meta_probability=payload.meta_confidence,
                entry=sizing["entry_price"],
                stop_loss=sizing["stop_loss"],
                take_profit=sizing["take_profit"],
                position_size_usd=sizing["notional_usd"],
                leverage=sizing["effective_leverage"],
                risk_reason=reason,
            )
            approved_event = SignalApprovedEvent(
                idempotency_key=idempotency_key,
                producer="risk-service",
                payload=decision_payload,
            )
            await self.stream_mgr.publish("signal.approved", approved_event)
            self.approved_count += 1
            log.info("APPROVED signal for %s %s (%s): entry=%.2f, sl=%.2f, tp=%.2f, lev=%.1fx",
                     symbol, timeframe, direction, sizing["entry_price"], sizing["stop_loss"], sizing["take_profit"], sizing["effective_leverage"])
        else:
            rejected_payload = SignalRiskDecisionPayload(
                symbol=symbol,
                timeframe=timeframe,
                candle_open_time=candle_open_time,
                direction=direction,
                probability=payload.calibrated_probability,
                meta_probability=payload.meta_confidence,
                entry=current_price,
                stop_loss=current_price * 0.99,
                take_profit=current_price * 1.02,
                position_size_usd=0.0,
                leverage=1.0,
                risk_reason=reason,
            )
            rejected_event = SignalRejectedEvent(
                idempotency_key=idempotency_key,
                producer="risk-service",
                payload=rejected_payload,
            )
            await self.stream_mgr.publish("signal.rejected", rejected_event)
            self.rejected_count += 1
            log.info("REJECTED signal for %s %s: %s", symbol, timeframe, reason)

    async def run(self):
        self.running = True
        log.info("Starting risk consumer on stream 'prediction.ready'...")
        try:
            await self.stream_mgr.consume_loop(
                stream_name="prediction.ready",
                group_name=settings.consumer_group,
                consumer_name=settings.consumer_name,
                handler=self.handle_prediction_ready,
            )
        except asyncio.CancelledError:
            log.info("Risk consumer cancelled.")
        except Exception:
            log.exception("Risk consumer loop error")

    def stop(self):
        self.running = False

