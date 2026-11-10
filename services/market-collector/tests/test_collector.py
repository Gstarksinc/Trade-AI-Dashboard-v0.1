"""Unit & integration tests for market-collector service."""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from rate_limiter import RateLimitBudgeter
from gap_detector import parse_kline_row, GapDetector
from binance_ws import BinanceWsClient
from main import app


@pytest.mark.asyncio
async def test_rate_limit_budgeter():
    budgeter = RateLimitBudgeter(max_weight_per_min=50)
    assert budgeter.used_weight == 0

    await budgeter.acquire(weight=10)
    assert budgeter.used_weight == 10

    # Header update simulation
    budgeter.update_from_headers({"x-mbx-used-weight-1m": "25"})
    assert budgeter.used_weight == 25


def test_parse_kline_row():
    # Binance kline payload format:
    # [open_time, open, high, low, close, volume, close_time, quote_vol, trades, taker_base, taker_quote, ignore]
    raw = [
        1700000000000, "50000.0", "50500.0", "49500.0", "50200.0", "123.45",
        1700000899999, "6200000.0", 1500, "60.0", "3000000.0", "0"
    ]
    parsed = parse_kline_row("BTCUSDT", "15m", raw)
    assert parsed["symbol"] == "BTCUSDT"
    assert parsed["timeframe"] == "15m"
    assert parsed["open"] == 50000.0
    assert parsed["high"] == 50500.0
    assert parsed["low"] == 49500.0
    assert parsed["close"] == 50200.0
    assert parsed["volume"] == 123.45
    assert parsed["trades_count"] == 1500
    assert parsed["is_closed"] is True
    assert isinstance(parsed["open_time"], datetime)


@pytest.mark.asyncio
async def test_ws_mark_price_handling():
    mock_stream_mgr = AsyncMock()
    mock_gap = AsyncMock()
    mock_storage = AsyncMock()

    ws_client = BinanceWsClient(
        symbols=["BTCUSDT"],
        timeframes=["15m"],
        stream_mgr=mock_stream_mgr,
        gap_detector=mock_gap,
        storage=mock_storage,
    )

    mark_price_msg = json.dumps({
        "stream": "btcusdt@markPrice@1s",
        "data": {
            "e": "markPriceUpdate",
            "E": 1700000000000,
            "s": "BTCUSDT",
            "p": "50100.50",
            "i": "50095.00",
            "r": "0.0001",
            "T": 1700003600000,
        }
    })

    await ws_client.handle_message(mark_price_msg)

    # Verifies fast Redis cache set was called
    mock_stream_mgr.set_latest_price.assert_called_with("BTCUSDT", 50100.50)
    # Verifies price.tick event was published
    assert mock_stream_mgr.publish.called
    stream_name, event = mock_stream_mgr.publish.call_args[0]
    assert stream_name == "price.tick"
    assert event.payload.mark_price == 50100.50


@pytest.mark.asyncio
async def test_ws_kline_unclosed_vs_closed():
    mock_stream_mgr = AsyncMock()
    mock_gap = AsyncMock()
    mock_storage = AsyncMock()

    ws_client = BinanceWsClient(
        symbols=["BTCUSDT"],
        timeframes=["15m"],
        stream_mgr=mock_stream_mgr,
        gap_detector=mock_gap,
        storage=mock_storage,
    )

    # 1. Unclosed candle (k.x = False) -> should be ignored
    unclosed_msg = json.dumps({
        "stream": "btcusdt@kline_15m",
        "data": {
            "s": "BTCUSDT",
            "k": {
                "t": 1700000000000,
                "T": 1700000899999,
                "i": "15m",
                "o": "50000.0",
                "c": "50100.0",
                "h": "50200.0",
                "l": "49900.0",
                "v": "10.0",
                "x": False,  # Not closed!
            }
        }
    })
    await ws_client.handle_message(unclosed_msg)
    assert not mock_storage.insert_candles.called
    assert not mock_stream_mgr.publish.called

    # 2. Closed candle (k.x = True) -> should be stored and published
    closed_msg = json.dumps({
        "stream": "btcusdt@kline_15m",
        "data": {
            "s": "BTCUSDT",
            "k": {
                "t": 1700000000000,
                "T": 1700000899999,
                "i": "15m",
                "o": "50000.0",
                "c": "50100.0",
                "h": "50200.0",
                "l": "49900.0",
                "v": "10.0",
                "q": "500000.0",
                "n": 50,
                "V": "6.0",
                "Q": "300000.0",
                "x": True,  # Closed!
            }
        }
    })
    await ws_client.handle_message(closed_msg)
    assert mock_storage.insert_candles.called
    assert mock_stream_mgr.publish.called
    stream_name, event = mock_stream_mgr.publish.call_args[0]
    assert stream_name == "candle.closed"
    assert event.payload.close == 50100.0
    assert event.payload.timeframe == "15m"


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "market-collector"
        assert data["status"] == "healthy"
        assert "symbols_tracked" in data
