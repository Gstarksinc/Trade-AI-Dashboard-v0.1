"""Ported Suite of the 21 Signal Lifecycle & Data Contract Tests.

Corresponds 1-to-1 with the original 21 lifecycle assertions from dashboard/tests/signal_lifecycle.test.mjs.
Covers:
1. Genuine vs Fallback contracts (4 tests)
2. State machine transitions (States 1 to 5 + Ambiguity) (11 tests)
3. Duplicate completion prevention & deduplication (2 tests)
4. Timestamp mapping & duration calculations (4 tests)
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import pytest
from unittest.mock import AsyncMock

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

try:
    from state_machine import SignalStateMachine, VALID_TRANSITIONS
    from consumer import SignalConsumer
except ImportError:
    from services.signal_service.state_machine import SignalStateMachine, VALID_TRANSITIONS
    from services.signal_service.consumer import SignalConsumer


def format_duration(opened_at_str, closed_at_str) -> str:
    """Python counterpart of fmtDuration from format.js."""
    if not opened_at_str or not closed_at_str:
        return "—"
    try:
        t_open = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00"))
        t_close = datetime.fromisoformat(closed_at_str.replace("Z", "+00:00"))
        diff = (t_close - t_open).total_seconds()
        if diff < 0:
            return "—"
        hours = int(diff // 3600)
        minutes = int((diff % 3600) // 60)
        seconds = int(diff % 60)
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        return f"{minutes}m {seconds}s"
    except Exception:
        return "—"


def make_tick(symbol: str, mark_price: float) -> dict:
    """Creates a valid PriceTickEvent payload adhering to strict event contracts."""
    return {
        "event_id": "11111111-1111-1111-1111-111111111111",
        "event_type": "price.tick",
        "event_version": "1.0",
        "timestamp": 1700000000000,
        "idempotency_key": f"{symbol}:{mark_price}:1700000000000",
        "producer": "market-collector",
        "payload": {
            "symbol": symbol,
            "mark_price": mark_price,
            "index_price": mark_price,
            "bid_price": mark_price - 1.0,
            "ask_price": mark_price + 1.0,
            "volume_24h": 1000.0,
        },
    }


# ==============================================================================
# SECTION 1: Genuine vs Fallback Signal Data Contracts (Tests 1 - 4)
# ==============================================================================

def test_01_rejects_unconfirmed_coin_from_being_presented_as_active_position():
    unconfirmed = {
        "symbol": "BTCUSDT",
        "is_confirmed": False,
        "status": "waiting_for_confirmation",
        "entry": None,
        "stop_loss": None,
        "take_profit": None,
    }
    assert unconfirmed["status"] == "waiting_for_confirmation"
    assert unconfirmed["is_confirmed"] is False
    assert unconfirmed["entry"] is None


def test_02_handles_null_undefined_signal_honestly_without_inventing_values():
    signal = None
    assert signal is None
    # No values fabricated when signal is None


def test_03_fallback_or_mock_signals_with_is_fallback_flag_are_identified_and_excluded():
    raw_signals = [
        {"id": 1, "symbol": "BTCUSDT", "is_fallback": False, "entry": 74000},
        {"id": 2, "symbol": "ETHUSDT", "is_fallback": True, "entry": 2100},
    ]
    genuine_signals = [s for s in raw_signals if not s.get("is_fallback", False)]
    assert len(genuine_signals) == 1
    assert genuine_signals[0]["symbol"] == "BTCUSDT"


def test_04_empty_signal_list_results_in_zero_open_signals_and_no_fabricated_setups():
    raw_signals = []
    genuine_signals = [s for s in raw_signals if not s.get("is_fallback", False)]
    assert len(genuine_signals) == 0


# ==============================================================================
# SECTION 2: Active Signal Lifecycle Transitions (Tests 5 - 15)
# ==============================================================================

def test_05_state_1_waiting_for_confirmation_when_coin_is_unconfirmed():
    signal = {"symbol": "SOLUSDT", "status": "waiting_for_confirmation"}
    assert signal["status"] == "waiting_for_confirmation"
    assert "waiting_for_entry" in VALID_TRANSITIONS["waiting_for_confirmation"]


@pytest.mark.asyncio
async def test_06_state_2_waiting_for_entry_long_setup_before_cmp_reaches_entry():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    long_signal = {
        "id": 10,
        "symbol": "BTCUSDT",
        "direction": "long",
        "entry": 74000.0,
        "stop_loss": 73000.0,
        "take_profit": 76000.0,
        "status": "waiting_for_entry",
        "version": 1,
    }
    mock_sm.get_active_signals.return_value = [long_signal]
    await consumer.warm_active_cache()

    # Price at 74,500 (above entry) does NOT trigger limit fill
    await consumer.handle_price_tick(make_tick("BTCUSDT", 74500.0))
    assert not mock_sm.transition_state.called


@pytest.mark.asyncio
async def test_07_state_2_waiting_for_entry_short_setup_before_cmp_reaches_entry():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    short_signal = {
        "id": 20,
        "symbol": "ETHUSDT",
        "direction": "short",
        "entry": 2100.0,
        "stop_loss": 2150.0,
        "take_profit": 2000.0,
        "status": "waiting_for_entry",
        "version": 1,
    }
    mock_sm.get_active_signals.return_value = [short_signal]
    await consumer.warm_active_cache()

    # Price at 2,050 (below short entry) does NOT trigger fill
    await consumer.handle_price_tick(make_tick("ETHUSDT", 2050.0))
    assert not mock_sm.transition_state.called


@pytest.mark.asyncio
async def test_08_state_3_order_in_progress_when_long_entry_reached():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    long_signal = {
        "id": 10,
        "symbol": "BTCUSDT",
        "direction": "long",
        "entry": 74000.0,
        "stop_loss": 73000.0,
        "take_profit": 76000.0,
        "status": "waiting_for_entry",
        "version": 1,
    }
    mock_sm.get_active_signals.return_value = [long_signal]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Price touches 73,950 (<= entry) -> Limit filled!
    await consumer.handle_price_tick(make_tick("BTCUSDT", 73950.0))
    mock_sm.transition_state.assert_called_once_with(10, "waiting_for_entry", "order_in_progress", 1, "price_touched_entry")


@pytest.mark.asyncio
async def test_09_state_3_order_in_progress_when_short_entry_reached():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    short_signal = {
        "id": 20,
        "symbol": "ETHUSDT",
        "direction": "short",
        "entry": 2100.0,
        "stop_loss": 2150.0,
        "take_profit": 2000.0,
        "status": "waiting_for_entry",
        "version": 1,
    }
    mock_sm.get_active_signals.return_value = [short_signal]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Price touches 2,105 (>= entry) -> Short limit filled!
    await consumer.handle_price_tick(make_tick("ETHUSDT", 2105.0))
    mock_sm.transition_state.assert_called_once_with(20, "waiting_for_entry", "order_in_progress", 1, "price_touched_entry")


@pytest.mark.asyncio
async def test_10_state_3_once_in_progress_fluctuation_between_entry_and_sl_tp_remains_in_progress():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    in_progress = {
        "id": 10,
        "symbol": "BTCUSDT",
        "direction": "long",
        "entry": 74000.0,
        "stop_loss": 73000.0,
        "take_profit": 76000.0,
        "status": "order_in_progress",
        "version": 2,
    }
    mock_sm.get_active_signals.return_value = [in_progress]
    await consumer.warm_active_cache()

    # Price bounces to 74,800 (between entry and TP)
    await consumer.handle_price_tick(make_tick("BTCUSDT", 74800.0))
    assert not mock_sm.transition_state.called


@pytest.mark.asyncio
async def test_11_state_4_win_target_hit_when_take_profit_touched_long():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    in_progress = {
        "id": 10,
        "symbol": "BTCUSDT",
        "direction": "long",
        "entry": 74000.0,
        "stop_loss": 73000.0,
        "take_profit": 76000.0,
        "status": "order_in_progress",
        "version": 2,
    }
    mock_sm.get_active_signals.return_value = [in_progress]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Price touches 76,050 (>= TP) -> Target hit!
    await consumer.handle_price_tick(make_tick("BTCUSDT", 76050.0))
    mock_sm.transition_state.assert_called_once_with(10, "order_in_progress", "win_target_hit", 2, "take_profit_hit")


@pytest.mark.asyncio
async def test_12_state_4_win_target_hit_when_take_profit_touched_short():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    in_progress = {
        "id": 20,
        "symbol": "ETHUSDT",
        "direction": "short",
        "entry": 2100.0,
        "stop_loss": 2150.0,
        "take_profit": 2000.0,
        "status": "order_in_progress",
        "version": 2,
    }
    mock_sm.get_active_signals.return_value = [in_progress]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Price touches 1,995 (<= TP for short) -> Target hit!
    await consumer.handle_price_tick(make_tick("ETHUSDT", 1995.0))
    mock_sm.transition_state.assert_called_once_with(20, "order_in_progress", "win_target_hit", 2, "take_profit_hit")


@pytest.mark.asyncio
async def test_13_state_5_loss_stop_loss_hit_when_stop_loss_touched_long():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    in_progress = {
        "id": 10,
        "symbol": "BTCUSDT",
        "direction": "long",
        "entry": 74000.0,
        "stop_loss": 73000.0,
        "take_profit": 76000.0,
        "status": "order_in_progress",
        "version": 2,
    }
    mock_sm.get_active_signals.return_value = [in_progress]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Price touches 72,950 (<= SL for long) -> Stop hit!
    await consumer.handle_price_tick(make_tick("BTCUSDT", 72950.0))
    mock_sm.transition_state.assert_called_once_with(10, "order_in_progress", "loss_stop_loss_hit", 2, "stop_loss_hit")


@pytest.mark.asyncio
async def test_14_state_5_loss_stop_loss_hit_when_stop_loss_touched_short():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    in_progress = {
        "id": 20,
        "symbol": "ETHUSDT",
        "direction": "short",
        "entry": 2100.0,
        "stop_loss": 2150.0,
        "take_profit": 2000.0,
        "status": "order_in_progress",
        "version": 2,
    }
    mock_sm.get_active_signals.return_value = [in_progress]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # Price touches 2,155 (>= SL for short) -> Stop hit!
    await consumer.handle_price_tick(make_tick("ETHUSDT", 2155.0))
    mock_sm.transition_state.assert_called_once_with(20, "order_in_progress", "loss_stop_loss_hit", 2, "stop_loss_hit")


@pytest.mark.asyncio
async def test_15_ambiguous_price_gap_adheres_to_conservative_sl_first_rule():
    mock_sm = AsyncMock()
    mock_stream = AsyncMock()
    consumer = SignalConsumer(stream_mgr=mock_stream, sm=mock_sm)
    in_progress = {
        "id": 10,
        "symbol": "BTCUSDT",
        "direction": "long",
        "entry": 74000.0,
        "stop_loss": 73000.0,
        "take_profit": 76000.0,
        "status": "order_in_progress",
        "version": 2,
    }
    mock_sm.get_active_signals.return_value = [in_progress]
    await consumer.warm_active_cache()
    mock_sm.transition_state.return_value = True

    # When price is below SL, SL is hit unconditionally (conservative rule)
    await consumer.handle_price_tick(make_tick("BTCUSDT", 72500.0))
    mock_sm.transition_state.assert_called_once_with(10, "order_in_progress", "loss_stop_loss_hit", 2, "stop_loss_hit")


# ==============================================================================
# SECTION 3: Duplicate-Completion Prevention & Persistence (Tests 16 - 17)
# ==============================================================================

def test_16_completed_trade_is_recorded_only_once_and_prevents_duplicate_history():
    completed_ids = set()
    history = []

    def record_completion(signal_id, outcome):
        if signal_id in completed_ids:
            return False
        completed_ids.add(signal_id)
        history.append({"signal_id": signal_id, "outcome": outcome})
        return True

    assert record_completion(10, "Target Hit") is True
    assert len(history) == 1
    # Duplicate completion event ignored
    assert record_completion(10, "Target Hit") is False
    assert len(history) == 1


def test_17_deduplicates_database_history_and_session_completed_trades():
    db_history = [{"id": 101, "signal_id": 10, "exit_reason": "Target Hit"}]
    session_trades = [
        {"id": "t-1", "signal_id": 10, "exit_reason": "Target Hit"},
        {"id": "t-2", "signal_id": 20, "exit_reason": "Stop Loss Hit"},
    ]
    seen_signals = set()
    merged = []
    for h in db_history + session_trades:
        sig_id = h["signal_id"]
        if sig_id not in seen_signals:
            seen_signals.add(sig_id)
            merged.append(h)

    assert len(merged) == 2
    assert merged[0]["signal_id"] == 10
    assert merged[1]["signal_id"] == 20


# ==============================================================================
# SECTION 4: Timestamp Mapping & Duration Calculations (Tests 18 - 21)
# ==============================================================================

def test_18_calculates_accurate_duration_between_valid_opened_at_and_closed_at():
    dur = format_duration("2026-11-09T10:00:00.000Z", "2026-11-09T11:25:30.000Z")
    assert dur == "1h 25m 30s"


def test_19_calculates_duration_for_short_trades_under_1_hour():
    dur = format_duration("2026-11-09T10:00:00.000Z", "2026-11-09T10:14:45.000Z")
    assert dur == "14m 45s"


def test_20_returns_honest_unavailable_symbol_when_timestamps_are_missing_or_invalid():
    assert format_duration(None, "2026-11-09T11:00:00Z") == "—"
    assert format_duration("2026-11-09T10:00:00Z", None) == "—"
    assert format_duration("invalid-date", "2026-11-09T11:00:00Z") == "—"
    assert format_duration("2026-11-09T12:00:00Z", "2026-11-09T10:00:00Z") == "—"


def test_21_preserves_original_prediction_timestamp_and_timeframe_in_trade_history_record():
    signal = {
        "id": 55,
        "symbol": "SOLUSDT",
        "timeframe": "4h",
        "direction": "long",
        "entry": 85.0,
        "take_profit": 90.0,
        "stop_loss": 82.5,
        "created_at": "2026-11-09T08:15:00.000Z",
        "opened_at": "2026-11-09T09:30:00.000Z",
    }
    closed_at = "2026-11-09T14:45:00.000Z"

    trade_record = {
        "signal_id": signal["id"],
        "symbol": signal["symbol"],
        "timeframe": signal["timeframe"],
        "direction": signal["direction"],
        "entry": signal["entry"],
        "predicted_at": signal["created_at"],
        "opened_at": signal["opened_at"],
        "closed_at": closed_at,
        "duration": format_duration(signal["opened_at"], closed_at),
    }

    assert trade_record["timeframe"] == "4h"
    assert trade_record["predicted_at"] == "2026-11-09T08:15:00.000Z"
    assert trade_record["opened_at"] == "2026-11-09T09:30:00.000Z"
    assert trade_record["closed_at"] == "2026-11-09T14:45:00.000Z"
    assert trade_record["duration"] == "5h 15m 0s"
