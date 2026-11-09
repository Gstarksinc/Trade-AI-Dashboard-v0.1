import pytest
import pandas as pd
import numpy as np
from backtest.engine import BacktestEngine, BacktestConfig

def test_backtest_engine_initialization():
    cfg = BacktestConfig(initial_equity=500.0, taker_fee_pct=0.0004)
    engine = BacktestEngine(config=cfg)
    assert engine.config.initial_equity == 500.0
    assert engine.config.taker_fee_pct == 0.0004

def test_backtest_simulation_empty():
    engine = BacktestEngine()
    signals_df = pd.DataFrame()
    candles_df = pd.DataFrame()
    res = engine.run_simulation(signals_df, candles_df)
    assert res['total_trades'] == 0
    assert res['win_rate_pct'] == 0.0
    assert res['final_equity'] == 100.0

