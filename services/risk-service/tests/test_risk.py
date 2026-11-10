"""Unit tests for risk-service."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

try:
    from evaluator import RiskEvaluator
    from correlation_clusters import get_cluster
    from main import app
except ImportError:
    from services.risk_service.evaluator import RiskEvaluator
    from services.risk_service.correlation_clusters import get_cluster
    from services.risk_service.main import app


def test_correlation_clusters():
    assert get_cluster("BTCUSDT") == "majors"
    assert get_cluster("ETHUSDT") == "majors"
    assert get_cluster("SOLUSDT") == "l1_platform"
    assert get_cluster("DOGEUSDT") == "high_beta_alt"


@pytest.mark.asyncio
async def test_stale_data_rejection():
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=90)
    approved, sizing, reason = await RiskEvaluator.evaluate_prediction(
        symbol="BTCUSDT",
        timeframe="15m",
        direction="long",
        calibrated_probability=0.70,
        meta_confidence=0.75,
        current_price=50000.0,
        atr=500.0,
        last_tick_time=stale_time,
    )
    assert approved is False
    assert "stale" in reason.lower()


@pytest.mark.asyncio
async def test_volatility_shock_rejection():
    # ATR is 4x median ATR -> shock rejection
    approved, sizing, reason = await RiskEvaluator.evaluate_prediction(
        symbol="BTCUSDT",
        timeframe="15m",
        direction="long",
        calibrated_probability=0.70,
        meta_confidence=0.75,
        current_price=50000.0,
        atr=2000.0,
        median_atr=400.0,
        last_tick_time=datetime.now(timezone.utc),
    )
    assert approved is False
    assert "volatility shock" in reason.lower()


@pytest.mark.asyncio
async def test_cost_to_risk_rejection():
    # Stop distance is tiny (0.1%), friction (0.14%) is > 25% of stop distance
    approved, sizing, reason = await RiskEvaluator.evaluate_prediction(
        symbol="BTCUSDT",
        timeframe="15m",
        direction="long",
        calibrated_probability=0.70,
        meta_confidence=0.75,
        current_price=50000.0,
        atr=20.0,  # 20 / 50000 = 0.04% stop loss!
        median_atr=20.0,
        last_tick_time=datetime.now(timezone.utc),
    )
    assert approved is False
    assert "cost-to-risk" in reason.lower()


@pytest.mark.asyncio
async def test_successful_approval_and_sizing():
    mock_conn = AsyncMock()
    mock_res = MagicMock()
    mock_res.fetchall.return_value = []
    mock_conn.execute.return_value = mock_res

    class MockBeginCtx:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_engine = MagicMock()
    mock_engine.begin.side_effect = MockBeginCtx

    try:
        import evaluator
    except ImportError:
        from services.risk_service import evaluator

    with patch.object(evaluator, "engine", mock_engine), \
         patch.object(RiskEvaluator, "get_open_positions", new=AsyncMock(return_value=[])), \
         patch.object(RiskEvaluator, "get_current_equity", new=AsyncMock(return_value=10000.0)), \
         patch.object(RiskEvaluator, "get_realized_losses", new=AsyncMock(return_value=0.0)):
        approved, sizing, reason = await RiskEvaluator.evaluate_prediction(
            symbol="BTCUSDT",
            timeframe="15m",
            direction="long",
            calibrated_probability=0.70,
            meta_confidence=0.75,
            current_price=50000.0,
            atr=1000.0,  # 2% stop distance
            median_atr=1000.0,
            last_tick_time=datetime.now(timezone.utc),
        )
        assert approved is True, f"Expected approval but rejected with: {reason}"
        assert sizing is not None
        assert sizing["stop_loss"] == 49000.0
        assert sizing["take_profit"] == 52000.0
        assert sizing["effective_leverage"] <= 3.0


@pytest.mark.asyncio
async def test_risk_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "risk-service"
        assert data["status"] == "healthy"
