"""Consumer loop for closed candles to generate point-in-time features."""

import asyncio
from datetime import datetime, timezone
import logging
import math
from typing import Dict
from libs.common.streams import RedisStreamManager
from libs.contracts.events import CandleClosedEvent, FeaturesReadyEvent, FeaturesReadyPayload
try:
    from .config import settings
    from .indicators.pipeline import build_point_in_time_features
    from .storage import FeatureStorage
except (ImportError, ValueError):
    from config import settings
    from indicators.pipeline import build_point_in_time_features
    from storage import FeatureStorage

log = logging.getLogger("feature-service.consumer")


class FeatureConsumer:
    def __init__(self, stream_mgr: RedisStreamManager, storage: FeatureStorage):
        self.stream_mgr = stream_mgr
        self.storage = storage
        self.running = False
        self.processed_count = 0

    def sanitize_features(self, feat_dict: Dict[str, float]) -> Dict[str, float]:
        clean = {}
        for k, v in feat_dict.items():
            try:
                val = float(v)
                if math.isnan(val) or math.isinf(val):
                    val = 0.0
                clean[k] = round(val, 6)
            except (ValueError, TypeError):
                clean[k] = 0.0
        return clean

    async def handle_candle_closed(self, event_data: dict):
        event = CandleClosedEvent(**event_data)
        payload = event.payload
        symbol = payload.symbol
        timeframe = payload.timeframe
        open_time = payload.open_time

        log.debug("Processing candle.closed for %s %s at %s", symbol, timeframe, open_time)

        # 1. Load closed candle history
        candles_df = await self.storage.load_closed_candles(symbol, timeframe, limit=settings.lookback_bars)
        if candles_df.empty or len(candles_df) < 20:
            log.warning("Insufficient candle history for %s %s (%d bars)", symbol, timeframe, len(candles_df))
            return

        # 2. Load BTC reference if not BTC
        btc_candles_df = None
        if symbol != settings.btc_symbol:
            btc_candles_df = await self.storage.load_closed_candles(settings.btc_symbol, timeframe, limit=settings.lookback_bars)

        # 3. Load funding & OI
        funding_df = await self.storage.load_funding(symbol, limit=50)
        oi_df = await self.storage.load_open_interest(symbol, timeframe=timeframe, limit=50)

        # 4. Build feature matrix
        feature_matrix = build_point_in_time_features(
            candles=candles_df,
            funding=funding_df,
            oi=oi_df,
            btc_candles=btc_candles_df,
        )

        if feature_matrix.empty:
            log.warning("Feature matrix empty for %s %s", symbol, timeframe)
            return

        # 5. Extract point-in-time features for the latest closed candle
        latest_row = feature_matrix.iloc[-1].to_dict()
        clean_features = self.sanitize_features(latest_row)

        # 6. Save to feature store
        await self.storage.save_features(
            symbol=symbol,
            timeframe=timeframe,
            candle_open_time=open_time,
            feature_set_version=settings.feature_set_version,
            features=clean_features,
        )

        # 7. Publish features.ready event
        open_time_str = open_time if isinstance(open_time, str) else open_time.isoformat()
        features_event = FeaturesReadyEvent(
            idempotency_key=f"feat-{symbol}-{timeframe}-{open_time_str}",
            producer="feature-service",
            payload=FeaturesReadyPayload(
                symbol=symbol,
                timeframe=timeframe,
                candle_open_time=open_time_str,
                bar_timestamp=open_time_str,
                feature_set_version=settings.feature_set_version,
                features=clean_features,
                close_price=payload.close,
            ),
        )
        await self.stream_mgr.publish("features.ready", features_event)
        self.processed_count += 1
        log.info(
            "Emitted features.ready for %s %s (version=%s, %d features, close=%.2f)",
            symbol,
            timeframe,
            settings.feature_set_version,
            len(clean_features),
            payload.close,
        )

    async def run(self):
        self.running = True
        log.info("Starting feature consumer loop on stream 'candle.closed'...")
        try:
            await self.stream_mgr.consume_loop(
                stream_name="candle.closed",
                group_name=settings.consumer_group,
                consumer_name=settings.consumer_name,
                handler=self.handle_candle_closed,
            )
        except asyncio.CancelledError:
            log.info("Feature consumer loop cancelled.")
        except Exception:
            log.exception("Feature consumer loop error")

    def stop(self):
        self.running = False

