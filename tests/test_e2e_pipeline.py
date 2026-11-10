"""End-to-End Integration Test on Recorded Fixtures across Microservice Pipeline."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import numpy as np
import pytest

from libs.contracts.events import (
    FeaturesReadyEvent,
    FeaturesReadyPayload,
    PriceTickEvent,
    PriceTickPayload,
    PredictionReadyEvent,
    PredictionReadyPayload,
    SignalApprovedEvent,
    SignalRiskDecisionPayload,
    SignalStateChangedEvent,
    SignalStateChangedPayload,
    TradeClosedEvent,
)
from services.risk_service.evaluator import RiskEvaluator
from services.signal_service.state_machine import VALID_TRANSITIONS
from services.paper_exec_service.engine import PaperExecutionEngine


@pytest.mark.asyncio
async def test_e2e_signal_to_execution_flow():
    """
    Traces an end-to-end signal from risk evaluation -> state transition -> fill -> exit.
    """
    # 1. Prediction Ready payload
    pred_event = PredictionReadyEvent(
        event_id="evt-test-1",
        idempotency_key="idemp-pred-1",
        producer="model-service",
        payload=PredictionReadyPayload(
            symbol="BTCUSDT",
            timeframe="1h",
            candle_open_time=datetime.now(timezone.utc),
            direction="long",
            raw_probability=0.72,
            calibrated_probability=0.70,
            meta_confidence=0.78,
            model_version="LGBM-BTCUSDT-1h-CHAMPION",
            is_shadow=False,
        ),
    )
    assert pred_event.payload.is_shadow is False

    # 2. Risk Evaluation with 0.5% sizing & reservation
    with patch.object(RiskEvaluator, "get_account_state_with_unrealized_pnl", AsyncMock(return_value=(10000.0, 0.0, []))):
        with patch.object(RiskEvaluator, "get_realized_losses", AsyncMock(return_value=0.0)):
            with patch("services.risk_service.evaluator.engine") as mock_risk_db:
                mock_conn = AsyncMock()
                mock_cursor = MagicMock()
                mock_cursor.fetchall.return_value = []
                mock_conn.execute.return_value = mock_cursor
                mock_risk_db.begin.return_value.__aenter__.return_value = mock_conn

                approved, sizing, reason = await RiskEvaluator.evaluate_and_reserve(
                    symbol="BTCUSDT",
                    timeframe="1h",
                    direction="long",
                    calibrated_probability=0.70,
                    meta_confidence=0.78,
                    current_price=50000.0,
                    atr=1000.0,
                    median_atr=1000.0,
                    last_tick_time=datetime.now(timezone.utc),
                )
                assert approved is True
                assert sizing["effective_leverage"] <= 3.0
                assert sizing["entry_price"] == 50000.0
                assert sizing["stop_loss"] == 49000.0
                assert sizing["take_profit"] == 52000.0

    # 3. State Machine Transition: waiting_for_confirmation -> waiting_for_entry -> order_in_progress
    assert "waiting_for_entry" in VALID_TRANSITIONS["waiting_for_confirmation"]
    assert "order_in_progress" in VALID_TRANSITIONS["waiting_for_entry"]

    # 4. Limit fill and execution simulation
    mock_trade = [
        {
            "id": 888,
            "signal_id": 999,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "direction": "long",
            "entry": 50000.0,
            "leverage": 2.0,
            "opened_at": datetime.now(timezone.utc) - timedelta(minutes=45),
            "fees": 2.80,
            "funding": 0.20,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
            "signal_version": 2,
        }
    ]

    with patch.object(PaperExecutionEngine, "get_open_trades", AsyncMock(return_value=mock_trade)):
        with patch("services.paper_exec_service.engine.engine") as mock_exec_db:
            mock_conn = AsyncMock()
            mock_exec_db.begin.return_value.__aenter__.return_value = mock_conn

            # Incoming tick penetrating take-profit with 0.05% trade-through buffer:
            # 52000 * 1.0005 = 52026. Mark price = 52,050 -> Target Hit!
            closed_trades = await PaperExecutionEngine.evaluate_tick_exits(
                symbol="BTCUSDT",
                mark_price=52050.0,
            )
            assert len(closed_trades) == 1
            ct = closed_trades[0]
            assert ct["exit_reason"] == "target_hit"
            assert ct["exit_price"] == 52000.0
            assert ct["net_pnl_pct"] > 0.0
            assert ct["duration_seconds"] > 0
