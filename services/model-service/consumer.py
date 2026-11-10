"""Consumer loop with shadow prediction persistence, deterministic idempotency, and feature hashing."""

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Dict
from sqlalchemy import text

from libs.database.connection import engine
from libs.common.streams import RedisStreamManager
from libs.contracts.events import FeaturesReadyEvent, PredictionReadyEvent, PredictionReadyPayload
try:
    from .config import settings
    from .inference import run_inference
    from .registry_loader import ModelRegistryManager
except (ImportError, ValueError):
    from config import settings
    from inference import run_inference
    from registry_loader import ModelRegistryManager

log = logging.getLogger("model-service.consumer")


def compute_feature_hash(features: Dict[str, float]) -> str:
    """Computes SHA256 hash of sorted feature dictionary for audit and parity tracking."""
    dumped = json.dumps(features, sort_keys=True)
    return hashlib.sha256(dumped.encode()).hexdigest()[:16]


class ModelConsumer:
    def __init__(self, stream_mgr: RedisStreamManager, registry_mgr: ModelRegistryManager):
        self.stream_mgr = stream_mgr
        self.registry_mgr = registry_mgr
        self.running = False
        self.predictions_count = 0
        self.shadow_predictions_count = 0

    async def persist_prediction(
        self,
        symbol: str,
        timeframe: str,
        candle_open_time: datetime,
        direction: str,
        raw_prob: float,
        cal_prob: float,
        meta_conf: float,
        model_version: str,
        feature_set_version: str,
        feature_hash: str,
        is_shadow: bool,
    ):
        """Persists predictions to model_registry.shadow_predictions for historical challenger evaluation."""
        try:
            query = text("""
                INSERT INTO model_registry.shadow_predictions (
                    symbol, timeframe, candle_open_time, direction,
                    raw_probability, calibrated_probability, meta_confidence,
                    model_version, feature_set_version, feature_hash, is_shadow
                ) VALUES (
                    :symbol, :timeframe, :candle_open_time, :direction,
                    :raw_prob, :cal_prob, :meta_conf,
                    :model_version, :feature_set_version, :feature_hash, :is_shadow
                )
                ON CONFLICT (model_version, symbol, timeframe, candle_open_time, is_shadow)
                DO NOTHING;
            """)
            async with engine.begin() as conn:
                await conn.execute(query, {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "candle_open_time": candle_open_time,
                    "direction": direction,
                    "raw_prob": raw_prob,
                    "cal_prob": cal_prob,
                    "meta_conf": meta_conf,
                    "model_version": model_version,
                    "feature_set_version": feature_set_version,
                    "feature_hash": feature_hash,
                    "is_shadow": is_shadow,
                })
        except Exception as e:
            log.warning("Failed persisting prediction to DB: %s", e)

    async def handle_features_ready(self, event_data: dict):
        event = FeaturesReadyEvent(**event_data)
        payload = event.payload
        symbol = payload.symbol
        timeframe = payload.timeframe
        bar_timestamp = payload.bar_timestamp
        feature_set_version = payload.feature_set_version
        features = payload.features

        feat_hash = compute_feature_hash(features)

        # 1. Champion Model Inference
        ts_str = bar_timestamp.isoformat() if hasattr(bar_timestamp, "isoformat") else str(bar_timestamp)
        champ = self.registry_mgr.champion
        if champ:
            pred = run_inference(champ, features)
            if pred:
                # Deterministic deduplication idempotency key
                idem_key = f"{champ.version}:{symbol}:{timeframe}:{ts_str}:live"
                pred_event = PredictionReadyEvent(
                    idempotency_key=idem_key,
                    producer="model-service",
                    payload=PredictionReadyPayload(
                        symbol=symbol,
                        timeframe=timeframe,
                        candle_open_time=bar_timestamp,
                        direction=pred["direction"],
                        raw_probability=pred["raw_probability"],
                        calibrated_probability=pred["calibrated_probability"],
                        meta_confidence=pred["meta_confidence"],
                        model_version=champ.version,
                        is_shadow=False,
                    ),
                )
                await self.stream_mgr.publish("prediction.ready", pred_event)
                await self.persist_prediction(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_open_time=bar_timestamp,
                    direction=pred["direction"],
                    raw_prob=pred["raw_probability"],
                    cal_prob=pred["calibrated_probability"],
                    meta_conf=pred["meta_confidence"],
                    model_version=champ.version,
                    feature_set_version=feature_set_version,
                    feature_hash=feat_hash,
                    is_shadow=False,
                )
                self.predictions_count += 1

        # 2. Challenger Model Inference (Shadow Mode)
        chal = self.registry_mgr.challenger
        if chal and chal.version != (champ.version if champ else None):
            shadow_pred = run_inference(chal, features)
            if shadow_pred:
                shadow_idem_key = f"{chal.version}:{symbol}:{timeframe}:{ts_str}:shadow"
                shadow_event = PredictionReadyEvent(
                    idempotency_key=shadow_idem_key,
                    producer="model-service",
                    payload=PredictionReadyPayload(
                        symbol=symbol,
                        timeframe=timeframe,
                        candle_open_time=bar_timestamp,
                        direction=shadow_pred["direction"],
                        raw_probability=shadow_pred["raw_probability"],
                        calibrated_probability=shadow_pred["calibrated_probability"],
                        meta_confidence=shadow_pred["meta_confidence"],
                        model_version=chal.version,
                        is_shadow=True,
                    ),
                )
                await self.stream_mgr.publish("prediction.ready", shadow_event)
                await self.persist_prediction(
                    symbol=symbol,
                    timeframe=timeframe,
                    candle_open_time=bar_timestamp,
                    direction=shadow_pred["direction"],
                    raw_prob=shadow_pred["raw_probability"],
                    cal_prob=shadow_pred["calibrated_probability"],
                    meta_conf=shadow_pred["meta_confidence"],
                    model_version=chal.version,
                    feature_set_version=feature_set_version,
                    feature_hash=feat_hash,
                    is_shadow=True,
                )
                self.shadow_predictions_count += 1

    async def run(self):
        self.running = True
        log.info("Starting model inference consumer on stream 'features.ready'...")
        try:
            await self.stream_mgr.consume_loop(
                stream_name="features.ready",
                group_name=settings.consumer_group,
                consumer_name=settings.consumer_name,
                handler=self.handle_features_ready,
            )
        except asyncio.CancelledError:
            log.info("Model inference consumer cancelled.")
        except Exception:
            log.exception("Model inference consumer loop error")

    def stop(self):
        self.running = False
