"""Unit tests for signal-service state machine and optimistic locking."""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from services.signal_service.state_machine import SignalStateMachine, VALID_TRANSITIONS
from services.signal_service.consumer import SignalConsumer


def test_valid_and_invalid_transitions():
    assert "waiting_for_entry" in VALID_TRANSITIONS["waiting_for_confirmation"]
    assert "order_in_progress" in VALID_TRANSITIONS["waiting_for_entry"]
    assert "invalidated" in VALID_TRANSITIONS["waiting_for_entry"]
    assert "win_target_hit" in VALID_TRANSITIONS["order_in_progress"]
    assert "loss_stop_loss_hit" in VALID_TRANSITIONS["order_in_progress"]

    # Invalid: win_target_hit directly from waiting_for_entry
    assert "win_target_hit" not in VALID_TRANSITIONS["waiting_for_entry"]


@pytest.mark.asyncio
async def test_signal_tick_transition_to_in_progress():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)

    # Active signal waiting for entry at 50,000
    mock_sm.get_active_signals.return_value = [
        {
            "id": 42,
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "direction": "long",
            "entry": 50000.0,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
            "status": "waiting_for_entry",
            "version": 1,
        }
    ]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Incoming tick: mark_price trades down to 49,950 (<= entry)
    tick_event = {
        "event_id": "33333333-3333-3333-3333-333333333333",
        "event_type": "price.tick",
        "event_version": "1.0",
        "timestamp": 1700000000000,
        "idempotency_key": "BTCUSDT:1700000000000",
        "producer": "market-collector",
        "payload": {
            "symbol": "BTCUSDT",
            "mark_price": 49950.0,
            "index_price": 49950.0,
            "bid_price": 49949.0,
            "ask_price": 49951.0,
            "volume_24h": 0.0,
        }
    }

    await consumer.handle_price_tick(tick_event)

    # Verify state transition called with optimistic version 1
    mock_sm.transition_state.assert_called_once_with(42, "waiting_for_entry", "order_in_progress", 1, "price_touched_entry")
    assert mock_stream.publish.called


@pytest.mark.asyncio
async def test_signal_tick_invalidation():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)

    mock_sm.get_active_signals.return_value = [
        {
            "id": 43,
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "direction": "long",
            "entry": 50000.0,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
            "status": "waiting_for_entry",
            "version": 1,
        }
    ]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Price crashes straight past SL (48,800 <= 49,000) before entry fill
    tick_event = {
        "event_id": "44444444-4444-4444-4444-444444444444",
        "event_type": "price.tick",
        "event_version": "1.0",
        "timestamp": 1700000000000,
        "idempotency_key": "BTCUSDT:1700000000000",
        "producer": "market-collector",
        "payload": {
            "symbol": "BTCUSDT",
            "mark_price": 48800.0,
            "index_price": 48800.0,
            "bid_price": 48799.0,
            "ask_price": 48801.0,
            "volume_24h": 0.0,
        }
    }

    await consumer.handle_price_tick(tick_event)
    mock_sm.transition_state.assert_called_once_with(43, "waiting_for_entry", "invalidated", 1, "price_breached_sl_before_entry")


@pytest.mark.asyncio
async def test_short_signal_entry_fill():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)

    # Active short signal waiting for entry at 50,000 (SL=51,000, TP=48,000)
    mock_sm.get_active_signals.return_value = [
        {
            "id": 101,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "direction": "short",
            "entry": 3000.0,
            "stop_loss": 3100.0,
            "take_profit": 2800.0,
            "status": "waiting_for_entry",
            "version": 1,
        }
    ]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Price rises up to 3005 (>= 3000 entry) -> triggers limit short fill
    tick_event = {
        "event_id": "55555555-5555-5555-5555-555555555555",
        "event_type": "price.tick",
        "event_version": "1.0",
        "timestamp": 1700000000000,
        "idempotency_key": "ETHUSDT:1700000000000",
        "producer": "market-collector",
        "payload": {
            "symbol": "ETHUSDT",
            "mark_price": 3005.0,
            "index_price": 3005.0,
            "bid_price": 3004.0,
            "ask_price": 3006.0,
            "volume_24h": 0.0,
        }
    }

    await consumer.handle_price_tick(tick_event)
    mock_sm.transition_state.assert_called_once_with(101, "waiting_for_entry", "order_in_progress", 1, "price_touched_entry")


@pytest.mark.asyncio
async def test_short_signal_invalidation_before_entry():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)

    # Short signal: entry=3000, SL=3100
    mock_sm.get_active_signals.return_value = [
        {
            "id": 102,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "direction": "short",
            "entry": 3000.0,
            "stop_loss": 3100.0,
            "take_profit": 2800.0,
            "status": "waiting_for_entry",
            "version": 2,
        }
    ]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Price gaps past stop loss to 3150 (>= 3100) before entry
    tick_event = {
        "event_id": "66666666-6666-6666-6666-666666666666",
        "event_type": "price.tick",
        "event_version": "1.0",
        "timestamp": 1700000000000,
        "idempotency_key": "ETHUSDT:1700000000000",
        "producer": "market-collector",
        "payload": {
            "symbol": "ETHUSDT",
            "mark_price": 3150.0,
            "index_price": 3150.0,
            "bid_price": 3149.0,
            "ask_price": 3151.0,
            "volume_24h": 0.0,
        }
    }

    await consumer.handle_price_tick(tick_event)
    mock_sm.transition_state.assert_called_once_with(102, "waiting_for_entry", "invalidated", 2, "price_breached_sl_before_entry")


@pytest.mark.asyncio
async def test_signal_health():
    import importlib
    main_mod = importlib.import_module("services.signal-service.main")
    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "signal-service"
        assert data["status"] == "healthy"
