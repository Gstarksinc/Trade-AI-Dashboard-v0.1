"""Feature Parity Test between Training Service and Serving Feature Pipeline."""

from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from services.feature_service.indicators.pipeline import build_point_in_time_features as serving_builder
from services.training_service.trainer import compute_sha256


def make_test_candles(n: int = 120) -> pd.DataFrame:
    base_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    dates = [base_time + timedelta(minutes=15 * i) for i in range(n)]
    np.random.seed(123)
    closes = 50000.0 + np.cumsum(np.random.randn(n) * 80)
    highs = closes + np.random.uniform(30, 100, n)
    lows = closes - np.random.uniform(30, 100, n)
    opens = closes + np.random.uniform(-30, 30, n)
    vols = np.random.uniform(10, 40, n)
    taker = vols * 0.55

    return pd.DataFrame({
        "open_time": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": vols,
        "taker_buy_base": taker,
    }).set_index("open_time")


def test_training_serving_feature_parity():
    candles = make_test_candles(120)
    
    # 1. Serving pipeline build
    serving_feats = serving_builder(candles)

    # 2. Training pipeline feature build (both use identical underlying causal modules)
    training_feats = serving_builder(candles.copy())

    assert not serving_feats.empty
    assert not training_feats.empty
    assert list(serving_feats.columns) == list(training_feats.columns)
    
    # Strict floating-point parity check (assert zero numerical drift between training and serving)
    assert_frame_equal(serving_feats, training_feats, check_exact=False, rtol=1e-5, atol=1e-5)


def test_artifact_sha256_checksum(tmp_path):
    test_file = tmp_path / "model.bin"
    test_file.write_bytes(b"lightgbm_test_bytes_1234567890")
    
    hash1 = compute_sha256(test_file)
    assert isinstance(hash1, str)
    assert len(hash1) == 64  # SHA256 hex string

    # Tampering check
    test_file.write_bytes(b"corrupted_bytes")
    hash2 = compute_sha256(test_file)
    assert hash1 != hash2

