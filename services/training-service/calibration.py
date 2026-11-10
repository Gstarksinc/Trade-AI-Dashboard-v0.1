"""Probability Calibration and Calibration Error Metrics (Brier Score, ECE, MCE)."""

from typing import Dict, Tuple
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss


def calculate_expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> Tuple[float, float]:
    """
    Computes Expected Calibration Error (ECE) and Maximum Calibration Error (MCE).
    y_true: binary 0/1 array
    y_prob: predicted probabilities in [0, 1]
    """
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins) - 1

    ece = 0.0
    mce = 0.0
    n = len(y_true)

    for i in range(n_bins):
        mask = bin_indices == i
        if not np.any(mask):
            continue
        bin_size = np.sum(mask)
        bin_acc = np.mean(y_true[mask])
        bin_conf = np.mean(y_prob[mask])
        diff = abs(bin_acc - bin_conf)

        ece += (bin_size / n) * diff
        mce = max(mce, diff)

    return float(round(ece, 4)), float(round(mce, 4))


def evaluate_calibration(
    y_true: np.ndarray,
    y_prob_uncalibrated: np.ndarray,
    y_prob_calibrated: np.ndarray,
) -> Dict[str, float]:
    """Evaluates improvement in Brier Score and ECE after calibration."""
    brier_uncal = brier_score_loss(y_true, y_prob_uncalibrated)
    brier_cal = brier_score_loss(y_true, y_prob_calibrated)

    ece_uncal, mce_uncal = calculate_expected_calibration_error(y_true, y_prob_uncalibrated)
    ece_cal, mce_cal = calculate_expected_calibration_error(y_true, y_prob_calibrated)

    return {
        "brier_score_raw": float(round(brier_uncal, 4)),
        "brier_score_calibrated": float(round(brier_cal, 4)),
        "ece_raw": ece_uncal,
        "ece_calibrated": ece_cal,
        "mce_calibrated": mce_cal,
        "calibration_improvement": float(round(brier_uncal - brier_cal, 4)),
    }

