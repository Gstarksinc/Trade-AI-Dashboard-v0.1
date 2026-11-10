"""Feature store persistence and historical market data retrieval."""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy import text
from libs.database.connection import engine

log = logging.getLogger("feature-service.storage")


class FeatureStorage:
    @staticmethod
    async def load_closed_candles(symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        """Fetch closed candles for symbol and timeframe, ordered chronologically ascending."""
        query = text("""
            SELECT open_time, open, high, low, close, volume, taker_buy_base
            FROM market_data.candles
            WHERE symbol = :symbol AND timeframe = :timeframe AND is_closed = TRUE
            ORDER BY open_time DESC LIMIT :limit;
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"symbol": symbol, "timeframe": timeframe, "limit": limit})
            rows = result.fetchall()
            if not rows:
                return pd.DataFrame()
            cols = ["open_time", "open", "high", "low", "close", "volume", "taker_buy_base"]
            df = pd.DataFrame(rows, columns=cols)
            df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
            df = df.sort_values("open_time").reset_index(drop=True)
            for c in ["open", "high", "low", "close", "volume", "taker_buy_base"]:
                df[c] = df[c].astype(float)
            return df

    @staticmethod
    async def load_funding(symbol: str, limit: int = 50) -> pd.DataFrame:
        """Fetch historical funding rates."""
        query = text("""
            SELECT funding_time AS open_time, funding_rate, mark_price
            FROM market_data.funding_rates
            WHERE symbol = :symbol
            ORDER BY funding_time DESC LIMIT :limit;
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"symbol": symbol, "limit": limit})
            rows = result.fetchall()
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=["open_time", "funding_rate", "mark_price"])
            df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
            df = df.sort_values("open_time").set_index("open_time")
            df["funding_rate"] = df["funding_rate"].astype(float)
            return df

    @staticmethod
    async def load_open_interest(symbol: str, timeframe: str = "15m", limit: int = 100) -> pd.DataFrame:
        """Fetch historical open interest."""
        query = text("""
            SELECT timestamp AS open_time, open_interest AS sum_open_interest, open_interest_value
            FROM market_data.open_interest
            WHERE symbol = :symbol AND timeframe = :timeframe
            ORDER BY timestamp DESC LIMIT :limit;
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"symbol": symbol, "timeframe": timeframe, "limit": limit})
            rows = result.fetchall()
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows, columns=["open_time", "sum_open_interest", "open_interest_value"])
            df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
            df = df.sort_values("open_time").set_index("open_time")
            df["sum_open_interest"] = df["sum_open_interest"].astype(float)
            return df

    @staticmethod
    async def save_features(
        symbol: str,
        timeframe: str,
        candle_open_time: datetime,
        feature_set_version: str,
        features: Dict[str, float],
    ):
        """Save computed features into feature_store.features."""
        query = text("""
            INSERT INTO feature_store.features (
                symbol, timeframe, candle_open_time, feature_set_version, features
            ) VALUES (
                :symbol, :timeframe, :candle_open_time, :feature_set_version, :features
            )
            ON CONFLICT (symbol, timeframe, candle_open_time, feature_set_version)
            DO UPDATE SET features = EXCLUDED.features;
        """)
        async with engine.begin() as conn:
            await conn.execute(query, {
                "symbol": symbol,
                "timeframe": timeframe,
                "candle_open_time": candle_open_time,
                "feature_set_version": feature_set_version,
                "features": json.dumps(features),
            })

