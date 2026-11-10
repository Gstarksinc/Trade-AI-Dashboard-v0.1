"""Unit tests for paper-exec-service with Long and Short side verification."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from services.paper_exec_service.engine import PaperExecutionEngine


@pytest.mark.asyncio
async def test_evaluate_tick_exits_long_conservative_sl_first():
    mock_trade = [
        {
            "id": 101,
            "signal_id": 501,
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "direction": "long",
            "entry": 50000.0,
            "leverage": 2.0,
            "opened_at": datetime.now(timezone.utc) - timedelta(minutes=30),
            "fees": 2.0,
            "funding": 0.5,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
            "signal_version": 2,
        }
    ]

    with patch.object(PaperExecutionEngine, "get_open_trades", AsyncMock(return_value=mock_trade)):
        with patch("services.paper_exec_service.engine.engine") as mock_db:
            mock_conn = AsyncMock()
            mock_db.begin.return_value.__aenter__.return_value = mock_conn

            # Both touched: SL wins
            closed = await PaperExecutionEngine.evaluate_tick_exits(
                symbol="BTCUSDT",
                mark_price=51000.0,
                high_price=53000.0,
                low_price=48500.0,
            )
            assert len(closed) == 1
            assert closed[0]["exit_reason"] == "stop_loss_hit"
            assert closed[0]["exit_price"] == 49000.0


@pytest.mark.asyncio
async def test_evaluate_tick_exits_short_side_verification():
    """Explicit verification of Short-side trade execution and profit/loss calculations."""
    mock_short_trade = [
        {
            "id": 201,
            "signal_id": 601,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "direction": "short",
            "entry": 50000.0,
            "leverage": 2.0,
            "opened_at": datetime.now(timezone.utc) - timedelta(hours=1),
            "fees": 2.0,
            "funding": 0.0,
            "stop_loss": 51000.0,  # Above entry
            "take_profit": 48000.0,  # Below entry
            "signal_version": 1,
        }
    ]

    with patch.object(PaperExecutionEngine, "get_open_trades", AsyncMock(return_value=mock_short_trade)):
        with patch("services.paper_exec_service.engine.engine") as mock_db:
            mock_conn = AsyncMock()
            mock_db.begin.return_value.__aenter__.return_value = mock_conn

            # Case 1: Short Take-Profit Hit (price trades down to 47,950 <= 48,000 * 0.9995 = 47,976)
            closed_tp = await PaperExecutionEngine.evaluate_tick_exits(
                symbol="BTCUSDT",
                mark_price=47950.0,
                high_price=48500.0,
                low_price=47950.0,
            )
            assert len(closed_tp) == 1
            assert closed_tp[0]["exit_reason"] == "target_hit"
            assert closed_tp[0]["exit_price"] == 48000.0
            assert closed_tp[0]["net_pnl_pct"] > 0.0  # Profitable short!

            # Case 2: Short Stop-Loss Hit (price rallies up to 51,200 >= 51,000)
            closed_sl = await PaperExecutionEngine.evaluate_tick_exits(
                symbol="BTCUSDT",
                mark_price=51200.0,
                high_price=51200.0,
                low_price=50100.0,
            )
            assert len(closed_sl) == 1
            assert closed_sl[0]["exit_reason"] == "stop_loss_hit"
            assert closed_sl[0]["exit_price"] == 51000.0
            assert closed_sl[0]["net_pnl_pct"] < 0.0  # Loss on short


@pytest.mark.asyncio
async def test_paper_exec_health():
    import importlib
    main_mod = importlib.import_module("services.paper-exec-service.main")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "paper-exec-service"
        assert data["status"] == "healthy"
