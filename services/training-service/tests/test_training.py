"""Unit tests for training-service ML math, labeling, and calibration."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest
from httpx import AsyncClient, ASGITransport

SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

try:
    from labeling import apply_triple_barrier_with_execution, compute_sample_uniqueness_weights
    from cross_validation import PurgedKFoldCV, CombinatorialPurgedCV
    from calibration import calculate_expected_calibration_error, evaluate_calibration
    from drift import calculate_psi, generate_feature_drift_report
    from evaluator import (
        optimize_thresholds_inner_fold,
        evaluate_promotion_gates,
        compare_candidate_vs_champion_holdout,
    )
    from main import app
except ImportError:
    from services.training_service.labeling import apply_triple_barrier_with_execution, compute_sample_uniqueness_weights
    from services.training_service.cross_validation import PurgedKFoldCV, CombinatorialPurgedCV
    from services.training_service.calibration import calculate_expected_calibration_error, evaluate_calibration
    from services.training_service.drift import calculate_psi, generate_feature_drift_report
    from services.training_service.evaluator import (
        optimize_thresholds_inner_fold,
        evaluate_promotion_gates,
        compare_candidate_vs_champion_holdout,
    )
    from services.training_service.main import app


def test_triple_barrier_conservative_sl_first_and_execution():
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    dates = [base_time + timedelta(minutes=15 * i) for i in range(15)]
    df = pd.DataFrame({
        "open": [100.0] * 15,
        "high": [101.0, 101.0, 105.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0],
        "low": [99.0, 99.0, 95.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0, 99.0],
        "close": [100.0] * 15,
        "atr_14": [2.0] * 15,
        "funding_rate": [0.0001] * 15,
    }, index=dates)

    # Entry evaluated at candle 0. Fills at candle 1 (Low <= 100).
    # In candle 2, high touches TP (104) and low touches SL (98).
    # Conservative SL-first rule must classify this as Stop Loss (-1).
    res, stats = apply_triple_barrier_with_execution(
        df,
        pt_multiplier=2.0,
        sl_multiplier=1.0,
        max_holding_bars=5,
        limit_wait_bars=2,
    )
    assert res.iloc[0]["label"] == -1
    assert res.iloc[0]["barrier"] == "sl"
    assert bool(res.iloc[0]["is_filled"]) is True
    assert stats["filled_trades"] > 0
    assert stats["fill_rate"] > 0.0


def test_sample_uniqueness_weights():
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    starts = pd.Series([base_time + timedelta(minutes=15 * i) for i in range(4)])
    ends = pd.Series([base_time + timedelta(minutes=15 * (i + 2)) for i in range(4)])

    weights = compute_sample_uniqueness_weights(starts, ends)
    assert len(weights) == 4
    assert abs(weights.mean() - 1.0) < 0.1
    assert (weights > 0).all()


def test_purged_cross_validation_embargo_ge_max_holding():
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    n = 120
    starts = pd.Series([base_time + timedelta(minutes=15 * i) for i in range(n)])
    ends = pd.Series([base_time + timedelta(minutes=15 * (i + 5)) for i in range(n)])

    cv = PurgedKFoldCV(n_splits=5, max_holding_bars=24, event_times=(starts, ends))
    splits = list(cv.split(starts, ends))
    assert len(splits) == 5

    for train_idx, test_idx in splits:
        assert len(set(train_idx).intersection(set(test_idx))) == 0
        assert len(train_idx) > 0
        assert len(test_idx) > 0


def test_promotion_gates_evaluation():
    # Failing gate test: negative EV
    neg_returns = np.array([-0.01, -0.02, 0.005, -0.015, -0.01] * 10)
    passed, metrics = evaluate_promotion_gates(
        holdout_net_returns=neg_returns,
        ece=0.08,
        cpcv_sharpes=[0.5, 0.8, -0.2],
        min_trades=20,
    )
    assert passed is False
    assert metrics["gates"]["gate_net_ev_passed"] is False

    # Passing gate test: positive EV with positive lower bootstrap bound
    pos_returns = np.array([0.02, 0.015, 0.025, 0.01, 0.018] * 10)
    passed_pos, metrics_pos = evaluate_promotion_gates(
        holdout_net_returns=pos_returns,
        ece=0.05,
        cpcv_sharpes=[1.2, 1.5, 0.9],
        min_trades=20,
    )
    assert passed_pos is True
    assert metrics_pos["gates"]["gate_bootstrap_ci_passed"] is True


def test_psi_drift_calculation():
    np.random.seed(42)
    dist1 = np.random.normal(0, 1, 1000)
    dist2 = np.random.normal(0, 1, 1000)
    dist3 = np.random.normal(2, 1, 1000)

    psi_ident = calculate_psi(dist1, dist2)
    psi_shifted = calculate_psi(dist1, dist3)

    assert psi_ident < 0.10
    assert psi_shifted > 0.25


@pytest.mark.asyncio
async def test_training_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "training-service"
        assert data["status"] == "healthy"
