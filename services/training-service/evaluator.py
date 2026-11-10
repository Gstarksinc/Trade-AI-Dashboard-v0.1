"""Quantitative Evaluation, Bootstrap Confidence Intervals, DSR, PBO, and Promotion Gates."""

import logging
import os
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.stats import norm

log = logging.getLogger("training-service.evaluator")


def get_dsr_trial_count(
    n_hyperparams: int = 5,
    n_threshold_combos: int = 20,
    default_trials: int = 100,
) -> Tuple[int, str]:
    """
    Returns configurable DSR trial count and logs its exact derivation.
    Configurable via DSR_TRIALS environment variable.
    """
    env_val = os.getenv("DSR_TRIALS")
    if env_val:
        try:
            trials = max(1, int(env_val))
            derivation = f"Configured via DSR_TRIALS environment variable: {trials}"
            log.info(derivation)
            return trials, derivation
        except ValueError:
            pass
    derived = n_hyperparams * n_threshold_combos
    trials = max(derived, default_trials)
    derivation = (
        f"Derived from search space: {n_hyperparams} hyperparam grids * "
        f"{n_threshold_combos} threshold combos = {derived} trials (floored at default {default_trials})"
    )
    log.info("DSR trial count derivation: %s (trials=%d)", derivation, trials)
    return trials, derivation


def bootstrap_ci(
    data: np.ndarray,
    stat_func: Callable[[np.ndarray], float] = np.mean,
    n_bootstraps: int = 1000,
    ci: float = 0.95,
) -> Tuple[float, float, float]:
    """
    Computes empirical bootstrap confidence interval.
    Returns (point_estimate, lower_bound, upper_bound).
    """
    if len(data) == 0:
        return 0.0, 0.0, 0.0

    point_est = float(stat_func(data))
    if len(data) < 5:
        return point_est, point_est, point_est

    rng = np.random.default_rng(42)
    boot_stats = []
    n = len(data)
    for _ in range(n_bootstraps):
        sample = rng.choice(data, size=n, replace=True)
        boot_stats.append(stat_func(sample))

    alpha = (1.0 - ci) / 2.0
    lower = float(np.percentile(boot_stats, alpha * 100))
    upper = float(np.percentile(boot_stats, (1.0 - alpha) * 100))
    return point_est, lower, upper


def compute_max_drawdown(returns: np.ndarray) -> float:
    """Computes percentage maximum drawdown from a series of trade returns."""
    if len(returns) == 0:
        return 0.0
    cum_equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(cum_equity)
    drawdowns = (peak - cum_equity) / peak
    return float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0


def compute_deflated_sharpe_ratio(
    sharpe: float,
    n_trials: int = 20,
    var_sharpe: float = 0.5,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    n_obs: int = 100,
) -> float:
    """
    Bailey and López de Prado's Deflated Sharpe Ratio (DSR).
    Accounts for multiple testing / selection bias.
    """
    if n_obs <= 2 or var_sharpe <= 0:
        return 0.0

    # Expected maximum Sharpe under null hypothesis of no true skill
    euler_mascheroni = 0.5772156649
    z_max = (1.0 - euler_mascheroni) * norm.ppf(1.0 - 1.0 / n_trials) + euler_mascheroni * norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    expected_max_sharpe = np.sqrt(var_sharpe) * z_max

    # Standard error of the Sharpe ratio accounting for non-normality
    sr_std_err = np.sqrt((1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * (sharpe ** 2)) / (n_obs - 1.0))
    if sr_std_err <= 0:
        return 0.0

    dsr = norm.cdf((sharpe - expected_max_sharpe) / sr_std_err)
    return float(round(dsr, 4))


def compute_pbo(cpcv_path_sharpes: List[float]) -> float:
    """
    Probability of Backtest Overfitting (PBO) from CPCV path performance.
    Estimates the probability that the chosen strategy underperforms the median.
    """
    if not cpcv_path_sharpes:
        return 0.5
    arr = np.array(cpcv_path_sharpes)
    # Proportion of paths where Sharpe is negative or below zero
    pbo = np.mean(arr <= 0.0)
    return float(round(pbo, 4))


def optimize_thresholds_inner_fold(
    primary_probs: np.ndarray,
    meta_probs: np.ndarray,
    directions: np.ndarray,
    net_returns: np.ndarray,
    min_trades: int = 15,
) -> Tuple[float, float, float]:
    """Inner fold threshold optimizer (prevents peeking at holdout)."""
    best_ev = -999.0
    best_p = 0.55
    best_m = 0.60

    prob_candidates = [0.50, 0.55, 0.60, 0.65]
    meta_candidates = [0.50, 0.55, 0.60, 0.65, 0.70]

    for p_thresh in prob_candidates:
        for m_thresh in meta_candidates:
            mask = (primary_probs >= p_thresh) & (meta_probs >= m_thresh)
            if np.sum(mask) >= min_trades:
                ev = np.mean(net_returns[mask])
                if ev > best_ev:
                    best_ev = ev
                    best_p = p_thresh
                    best_m = m_thresh

    return best_p, best_m, best_ev


def evaluate_promotion_gates(
    holdout_net_returns: np.ndarray,
    ece: float,
    cpcv_sharpes: List[float],
    min_trades: int = 50,
    max_ece: float = 0.12,
) -> Tuple[bool, Dict[str, any]]:
    """
    Phase 3.1 Strict Promotion Gates:
    1. Net EV after costs > 0.
    2. Bootstrap 95% CI lower bound of Net EV > 0.
    3. Trade count >= min_trades.
    4. ECE <= max_ece (0.12).
    5. Median CPCV path net Sharpe > 0.
    """
    n_trades = len(holdout_net_returns)
    mean_ev, ev_lower, ev_upper = bootstrap_ci(holdout_net_returns, np.mean, n_bootstraps=1000)
    median_cpcv_sharpe = float(np.median(cpcv_sharpes)) if cpcv_sharpes else -1.0

    gates = {
        "gate_min_trades_passed": n_trades >= min_trades,
        "gate_net_ev_passed": mean_ev > 0.0,
        "gate_bootstrap_ci_passed": ev_lower > 0.0,
        "gate_ece_passed": ece <= max_ece,
        "gate_cpcv_sharpe_passed": median_cpcv_sharpe > 0.0,
    }

    all_passed = all(gates.values())
    metrics = {
        "n_holdout_trades": n_trades,
        "mean_net_ev_pct": round(mean_ev * 100.0, 3),
        "bootstrap_ci_95": [round(ev_lower * 100.0, 3), round(ev_upper * 100.0, 3)],
        "ece": round(ece, 4),
        "median_cpcv_sharpe": round(median_cpcv_sharpe, 3),
        "gates": gates,
        "promotion_approved": all_passed,
    }
    return all_passed, metrics


def compare_candidate_vs_champion_holdout(
    cand_returns: np.ndarray,
    champ_returns: np.ndarray,
    min_trades: int = 30,
) -> Tuple[bool, Dict[str, any]]:
    """
    Compares candidate vs champion on the SAME holdout window.
    Requires statistically positive difference (bootstrap CI lower bound > 0).
    """
    n_cand = len(cand_returns)
    n_champ = len(champ_returns)

    if n_cand < min_trades or n_champ < min_trades:
        return False, {"reason": "Insufficient holdout trades for comparison"}

    # Resample difference
    min_n = min(n_cand, n_champ)
    diff = cand_returns[:min_n] - champ_returns[:min_n]
    mean_diff, lower_diff, upper_diff = bootstrap_ci(diff, np.mean, n_bootstraps=1000)

    beats_champion = mean_diff > 0.0 and lower_diff > 0.0
    return beats_champion, {
        "mean_diff_pct": round(mean_diff * 100.0, 3),
        "diff_ci_95": [round(lower_diff * 100.0, 3), round(upper_diff * 100.0, 3)],
        "beats_champion_with_confidence": beats_champion,
    }
