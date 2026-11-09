import pytest
from risk.engine import RiskEngine, RiskLimits, calculate_trade_levels, calculate_position_size

def test_calculate_trade_levels_long():
    levels = calculate_trade_levels(current_price=50000.0, atr=500.0, direction="long", pt_mult=2.0, sl_mult=1.0)
    assert levels['entry'] == 50000.0
    assert levels['stop_loss'] == 49500.0
    assert levels['take_profit'] == 51000.0
    assert levels['rr_ratio'] == 2.0

def test_calculate_trade_levels_short():
    levels = calculate_trade_levels(current_price=50000.0, atr=500.0, direction="short", pt_mult=2.0, sl_mult=1.0)
    assert levels['entry'] == 50000.0
    assert levels['stop_loss'] == 50500.0
    assert levels['take_profit'] == 49000.0
    assert levels['rr_ratio'] == 2.0

def test_calculate_position_size_leverage_cap():
    # $10,000 equity, 1% risk ($100), tiny 0.1% stop loss -> raw size would be $100k (10x leverage)
    res = calculate_position_size(equity=10000.0, entry_price=100.0, stop_loss_price=99.9, risk_pct=0.01, max_leverage=3.0)
    assert res['is_leverage_capped'] is True
    assert res['position_value_dollars'] == 30000.0 # 3x capped
    assert res['effective_leverage'] == 3.0

def test_risk_engine_limits():
    engine = RiskEngine(RiskLimits(daily_loss_limit_pct=0.03, max_correlated_positions=3))
    assert engine.check_daily_loss(2.5) is True
    assert engine.check_daily_loss(3.5) is False
