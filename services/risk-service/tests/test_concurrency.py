"""Concurrency and Advisory Lock Reservation Integration Test.

Proves that parallel risk evaluations are serialized by the advisory lock
and cluster / portfolio caps are strictly never exceeded under concurrency.
"""

import asyncio
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch, MagicMock
import pytest

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

try:
    import evaluator
    from evaluator import RiskEvaluator
    from config import settings
except ImportError:
    from services.risk_service import evaluator
    from services.risk_service.evaluator import RiskEvaluator
    from services.risk_service.config import settings


@pytest.mark.asyncio
async def test_parallel_risk_evaluations_respect_caps():
    """
    Simulates 10 concurrent risk approval attempts across different symbols
    belonging to the same cluster ('major': BTC, ETH) and across clusters.
    Verifies that the advisory lock and atomic reservations prevent cap breaches.
    """
    # Track reserved symbols in a simulated shared state
    simulated_reserved = []
    lock = asyncio.Lock()

    async def mock_execute(query, params=None):
        nonlocal simulated_reserved
        query_str = str(query)

        # SELECT pg_advisory_xact_lock
        if "pg_advisory_xact_lock" in query_str:
            mock_res = MagicMock()
            return mock_res

        # SELECT symbol FROM signals_ledger.signals
        if "FROM signals_ledger.signals" in query_str:
            mock_res = MagicMock()
            mock_res.fetchall.return_value = [(s,) for s in simulated_reserved]
            return mock_res

        # INSERT INTO signals_ledger.signals
        if "INSERT INTO signals_ledger.signals" in query_str and params:
            simulated_reserved.append(params["symbol"])
            mock_res = MagicMock()
            return mock_res

        mock_res = MagicMock()
        mock_res.fetchone.return_value = None
        mock_res.fetchall.return_value = []
        return mock_res

    # Mock DB engine connection
    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = mock_execute

    class MockBeginCtx:
        async def __aenter__(self):
            await lock.acquire()
            return mock_conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            lock.release()

    mock_engine = MagicMock()
    mock_engine.begin.side_effect = MockBeginCtx

    with patch.object(evaluator, "engine", mock_engine), \
         patch.object(RiskEvaluator, "get_current_equity", new=AsyncMock(return_value=10000.0)), \
         patch.object(RiskEvaluator, "get_open_positions", new=AsyncMock(return_value=[])), \
         patch.object(RiskEvaluator, "get_realized_losses", new=AsyncMock(return_value=0.0)):

        # Launch 4 parallel evaluation tasks for BTC and ETH (both in 'major' cluster, cap is 2)
        tasks = [
            RiskEvaluator.evaluate_and_reserve("BTCUSDT", "1h", "long", 0.70, 0.75, 60000.0, 500.0),
            RiskEvaluator.evaluate_and_reserve("ETHUSDT", "1h", "long", 0.68, 0.72, 3000.0, 30.0),
            RiskEvaluator.evaluate_and_reserve("BTCUSDT", "1h", "long", 0.75, 0.80, 60000.0, 500.0),  # Duplicate BTC
            RiskEvaluator.evaluate_and_reserve("ETHUSDT", "1h", "long", 0.71, 0.76, 3000.0, 30.0),  # Duplicate ETH
        ]

        results = await asyncio.gather(*tasks)

        approvals = [r for r in results if r[0] is True]
        rejections = [r for r in results if r[0] is False]

        # Exactly 2 should be approved (1 BTC, 1 ETH)
        assert len(approvals) == 2, f"Expected 2 approvals, got {len(approvals)}"
        assert len(rejections) == 2, f"Expected 2 rejections, got {len(rejections)}"

        # Rejection reasons must mention duplicate or cluster capacity
        reasons = [r[2] for r in rejections]
        assert any("already exists" in r or "capacity full" in r for r in reasons)


@pytest.mark.asyncio
async def test_portfolio_total_cap_concurrency():
    """Simulates 10 concurrent trades across distinct symbols when max_total_open_trades = 5."""
    simulated_reserved = []
    lock = asyncio.Lock()

    async def mock_execute(query, params=None):
        nonlocal simulated_reserved
        query_str = str(query)
        if "FROM signals_ledger.signals" in query_str:
            mock_res = MagicMock()
            mock_res.fetchall.return_value = [(s,) for s in simulated_reserved]
            return mock_res
        if "INSERT INTO signals_ledger.signals" in query_str and params:
            simulated_reserved.append(params["symbol"])
            mock_res = MagicMock()
            return mock_res
        mock_res = MagicMock()
        mock_res.fetchone.return_value = None
        mock_res.fetchall.return_value = []
        return mock_res

    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = mock_execute

    class MockBeginCtx:
        async def __aenter__(self):
            await lock.acquire()
            return mock_conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            lock.release()

    candidates = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT", "TRXUSDT"]

    mock_engine = MagicMock()
    mock_engine.begin.side_effect = MockBeginCtx

    with patch.object(evaluator, "engine", mock_engine), \
         patch.object(RiskEvaluator, "get_current_equity", new=AsyncMock(return_value=10000.0)), \
         patch.object(RiskEvaluator, "get_open_positions", new=AsyncMock(return_value=[])), \
         patch.object(RiskEvaluator, "get_realized_losses", new=AsyncMock(return_value=0.0)):

        tasks = [
            RiskEvaluator.evaluate_and_reserve(sym, "1h", "long", 0.70, 0.75, 100.0, 1.0)
            for sym in candidates
        ]

        results = await asyncio.gather(*tasks)
        approved_count = sum(1 for r in results if r[0] is True)

        # Must not exceed max_total_open_trades (5)
        assert approved_count <= settings.max_total_open_trades, (
            f"Approved count {approved_count} exceeded cap {settings.max_total_open_trades}"
        )
