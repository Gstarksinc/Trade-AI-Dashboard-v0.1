"""Feature Distribution Drift Detection: Population Stability Index (PSI) & Wasserstein Distance."""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance


def calculate_psi(
    expected: np.ndarray,
    actual: np.ndarray,
    num_bins: int = 10,
    epsilon: float = 1e-4,
) -> float:
    """
    Computes Population Stability Index (PSI) between baseline (expected) and target (actual) distributions.
    PSI < 0.10: No drift
    0.10 <= PSI < 0.25: Moderate drift
    PSI >= 0.25: Significant drift
    """
    expected = expected[~np.isnan(expected)]
    actual = actual[~np.isnan(actual)]
    if len(expected) < 10 or len(actual) < 10:
        return 0.0

    # Determine quantile bins based on expected baseline
    quantiles = np.linspace(0, 100, num_bins + 1)
    bins = np.percentile(expected, quantiles)
    bins = np.unique(bins)
    if len(bins) < 2:
        return 0.0

    bins[0] = -np.inf
    bins[-1] = np.inf

    expected_counts, _ = np.histogram(expected, bins=bins)
    actual_counts, _ = np.histogram(actual, bins=bins)

    expected_pct = expected_counts / len(expected) + epsilon
    actual_pct = actual_counts / len(actual) + epsilon

    # Normalize to sum to 1
    expected_pct /= expected_pct.sum()
    actual_pct /= actual_pct.sum()

    psi_val = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(round(psi_val, 4))


def generate_feature_drift_report(
    training_features: pd.DataFrame,
    recent_features: pd.DataFrame,
    features_to_check: List[str] = None,
) -> Dict[str, any]:
    """Generates comprehensive drift report across key feature distributions."""
    if features_to_check is None:
        features_to_check = [c for c in training_features.columns if c in recent_features.columns]

    psi_scores = {}
    wasserstein_scores = {}
    drifted_features = []

    for feat in features_to_check:
        train_vals = training_features[feat].values
        recent_vals = recent_features[feat].values

        psi = calculate_psi(train_vals, recent_vals)
        psi_scores[feat] = psi

        wd = float(round(wasserstein_distance(train_vals, recent_vals), 5))
        wasserstein_scores[feat] = wd

        if psi >= 0.25:
            drifted_features.append(feat)

    avg_psi = float(round(np.mean(list(psi_scores.values())), 4)) if psi_scores else 0.0

    return {
        "average_psi": avg_psi,
        "is_drift_detected": avg_psi >= 0.20 or len(drifted_features) > 3,
        "drifted_features_count": len(drifted_features),
        "drifted_features": drifted_features,
        "psi_scores": psi_scores,
        "wasserstein_distances": wasserstein_scores,
    }

