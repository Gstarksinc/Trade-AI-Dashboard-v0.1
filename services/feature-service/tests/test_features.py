"""Unit & integration tests for feature-service."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch
import numpy as np
import pandas as pd
import pytest
from httpx import AsyncClient, ASGITransport

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

try:
    from indicators.ta import rsi, macd, atr, adx, bollinger_bands, compute_all_ta
    from indicators.derivatives import compute_derivatives_features
    from indicators.cross_asset import compute_cross_asset_features, compute_btc_correlation
    from indicators.pipeline import build_point_in_time_features
    from consumer import FeatureConsumer
    from main import app
except ImportError:
    from services.feature_service.indicators.ta import rsi, macd, atr, adx, bollinger_bands, compute_all_ta
    from services.feature_service.indicators.derivatives import compute_derivatives_features
    from services.feature_service.indicators.cross_asset import compute_cross_asset_features, compute_btc_correlation
    from services.feature_service.indicators.pipeline import build_point_in_time_features
    from services.feature_service.consumer import FeatureConsumer
    from services.feature_service.main import app


def make_dummy_candles(n: int = 100) -> pd.DataFrame:
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    dates = [base_time + timedelta(minutes=15 * i) for i in range(n)]
    np.random.seed(42)
    close_prices = 50000.0 + np.cumsum(np.random.randn(n) * 100)
    high_prices = close_prices + np.random.uniform(50, 150, n)
    low_prices = close_prices - np.random.uniform(50, 150, n)
    open_prices = close_prices + np.random.uniform(-50, 50, n)
    volumes = np.random.uniform(10, 50, n)
    taker_buy = volumes * np.random.uniform(0.4, 0.6, n)

    df = pd.DataFrame({
        "open_time": dates,
        "open": open_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volumes,
        "taker_buy_base": taker_buy,
    })
    return df


def test_ta_indicators():
    df = make_dummy_candles(100)
    c = pd.Series(df["close"].values)
    h = pd.Series(df["high"].values)
    l = pd.Series(df["low"].values)

    # RSI
    rsi_vals = rsi(c, 14)
    assert len(rsi_vals) == 100
    assert 0 <= rsi_vals.iloc[-1] <= 100

    # MACD
    m, s, hist = macd(c, 12, 26, 9)
    assert len(m) == 100
    assert len(s) == 100

    # ATR
    atr_vals = atr(h, l, c, 14)
    assert len(atr_vals) == 100
    assert (atr_vals.dropna() > 0).all()

    # ADX
    adx_vals = adx(h, l, c, 14)
    assert len(adx_vals) == 100
    assert (adx_vals.dropna() >= 0).all()

    # All TA
    df_indexed = df.set_index("open_time")
    all_ta = compute_all_ta(df_indexed)
    expected_cols = ["rsi_14", "rsi_7", "macd", "atr_14", "adx_14", "bb_width", "ret_1", "ret_4"]
    for col in expected_cols:
        assert col in all_ta.columns


def test_derivatives_and_cross_asset():
    df = make_dummy_candles(100).set_index("open_time")
    
    # Derivatives
    deriv = compute_derivatives_features(df)
    assert "funding_rate" in deriv.columns
    assert "taker_buy_sell_ratio" in deriv.columns
    assert "oi_zscore" in deriv.columns

    # Cross asset
    btc_df = make_dummy_candles(100).set_index("open_time")
    cross = compute_cross_asset_features(df, btc_df, atr_series=atr(pd.Series(df["high"].values, index=df.index), pd.Series(df["low"].values, index=df.index), pd.Series(df["close"].values, index=df.index)))
    assert "hour_sin" in cross.columns
    assert "hour_cos" in cross.columns
    assert "btc_corr_48" in cross.columns
    assert "volatility_regime" in cross.columns


def test_unified_pipeline_no_lookahead():
    candles = make_dummy_candles(250)
    features = build_point_in_time_features(candles)
    assert not features.empty
    assert len(features) == 250
    # Confirm no NaN values in final output
    assert not features.isna().any().any()
    # Confirm key feature categories exist
    assert "rsi_14" in features.columns
    assert "adx_14" in features.columns
    assert "natr_14" in features.columns
    assert "taker_buy_sell_ratio" in features.columns
    assert "volatility_regime" in features.columns


@pytest.mark.asyncio
async def test_feature_consumer_handles_candle_closed():
    mock_stream_mgr = AsyncMock()
    mock_storage = AsyncMock()

    # Setup dummy candle dataframe returned by storage
    dummy_df = make_dummy_candles(100)
    mock_storage.load_closed_candles.return_value = dummy_df
    mock_storage.load_funding.return_value = pd.DataFrame()
    mock_storage.load_open_interest.return_value = pd.DataFrame()

    consumer = FeatureConsumer(stream_mgr=mock_stream_mgr, storage=mock_storage)

    event_payload = {
        "event_id": "11111111-1111-1111-1111-111111111111",
        "event_type": "candle.closed",
        "event_version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "idempotency_key": "BTCUSDT:15m:1700000000000",
        "producer": "market-collector",
        "payload": {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "open_time": datetime.now(timezone.utc).isoformat(),
            "close_time": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            "open": 50000.0,
            "high": 50500.0,
            "low": 49800.0,
            "close": 50250.0,
            "volume": 100.0,
            "taker_volume": 55.0,
            "trades_count": 200,
        }
    }

    await consumer.handle_candle_closed(event_payload)

    # Verifies feature persistence to database
    assert mock_storage.save_features.called
    # Verifies features.ready event publication
    assert mock_stream_mgr.publish.called
    stream_name, event = mock_stream_mgr.publish.call_args[0]
    assert stream_name == "features.ready"
    assert event.payload.symbol == "BTCUSDT"
    assert event.payload.feature_set_version == "v1.0.0"
    assert "rsi_14" in event.payload.features
    assert "adx_14" in event.payload.features


@pytest.mark.asyncio
async def test_feature_service_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "feature-service"
        assert data["status"] == "healthy"
        assert data["feature_set_version"] == "v1.0.0"
