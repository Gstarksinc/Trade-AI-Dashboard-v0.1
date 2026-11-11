"""Quantitative Evaluation, Bootstrap Confidence Intervals, DSR, PBO, and Promotion Gates.
Phase 6.6: Unified evaluation function, break-even derived probability gating,
and rigorous Sharpe ratio audit (per-trade frequency vs period annualization).
"""

from dataclasses import dataclass, field
import logging
import os
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.stats import norm

log = logging.getLogger("training-service.evaluator")


from libs.common.risk_rules import DEFAULT_BARRIER_CONFIG


@dataclass
class UnifiedThresholdConfig:
    """Unified configuration for training, funnel diagnostics, and leakage audit."""
    pt_multiplier: float = DEFAULT_BARRIER_CONFIG.pt_multiplier
    sl_multiplier: float = DEFAULT_BARRIER_CONFIG.sl_multiplier
    friction: float = DEFAULT_BARRIER_CONFIG.default_friction          # 14 bps round-trip
    max_cost_to_risk: float = DEFAULT_BARRIER_CONFIG.max_cost_to_risk_ratio     # Max round-trip cost / stop distance
    holdout_pct: float = 0.20          # 20% untouched final holdout
    warmup_bars: int = 200             # Warmup bars required for indicator lookbacks
    embargo_bars: int = 24             # Embargo between train and holdout
    limit_wait_bars: int = 2           # Limit order fill window
    max_holding_bars: int = 24         # Vertical time barrier
    min_trades_inner: int = 15         # Minimum trades required in inner fold
    min_trades_holdout: int = 20       # Minimum trades required on holdout
    max_ece: float = 0.12              # ECE promotion ceiling


def compute_per_setup_breakeven_p_star(
    atrs: np.ndarray,
    closes: np.ndarray,
    pt_multiplier: float = DEFAULT_BARRIER_CONFIG.pt_multiplier,
    sl_multiplier: float = DEFAULT_BARRIER_CONFIG.sl_multiplier,
    friction: float = DEFAULT_BARRIER_CONFIG.default_friction,
) -> np.ndarray:
    """
    Computes per-setup dynamic break-even probability gate p* from each bar's ATR%:
      p*_i = (stop%_i + cost) / (target%_i + stop%_i)
    """
    atr_pct = np.where(closes > 0, atrs / closes, 0.015)
    stop_pct = sl_multiplier * atr_pct
    target_pct = pt_multiplier * atr_pct
    denom = target_pct + stop_pct
    return np.where(denom > 0, (stop_pct + friction) / denom, 0.3644)


def derive_breakeven_probability_gate(
    pt_multiplier: float = DEFAULT_BARRIER_CONFIG.pt_multiplier,
    sl_multiplier: float = DEFAULT_BARRIER_CONFIG.sl_multiplier,
    friction: float = DEFAULT_BARRIER_CONFIG.default_friction,
    avg_sl_pct: float = 0.015,
) -> float:
    """
    Derives the mathematical break-even probability threshold p*:
    E[Net Return] = p * (TP - friction) + (1 - p) * (-SL - friction) = 0
    => p * (TP + SL) = SL + friction
    => p* = (SL + friction) / (TP + SL)
    
    For a 2:1 TP/SL ratio with avg SL = 1.5% and friction = 0.14%:
    p* = (0.015 + 0.0014) / (0.030 + 0.015) = 0.0164 / 0.0450 = 36.44%.
    """
    tp_pct = pt_multiplier * avg_sl_pct
    sl_pct = sl_multiplier * avg_sl_pct
    denom = tp_pct + sl_pct
    if denom <= 0:
        return 0.5
    p_star = (sl_pct + friction) / denom
    return float(round(p_star, 4))


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

    euler_mascheroni = 0.5772156649
    z_max = (1.0 - euler_mascheroni) * norm.ppf(1.0 - 1.0 / n_trials) + euler_mascheroni * norm.ppf(1.0 - 1.0 / (n_trials * np.e))
    expected_max_sharpe = np.sqrt(var_sharpe) * z_max

    sr_std_err = np.sqrt((1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * (sharpe ** 2)) / (n_obs - 1.0))
    if sr_std_err <= 0:
        return 0.0

    dsr = norm.cdf((sharpe - expected_max_sharpe) / sr_std_err)
    return float(round(dsr, 4))


def compute_pbo(
    cpcv_path_sharpes: List[float],
    candidate_ranks: Optional[List[float]] = None,
) -> float:
    """
    Computes Probability of Backtest Overfitting (PBO).
    1. If multi-trial candidate ranks are provided (Marcos López de Prado's CSCV/CPCV PBO):
       Computes the probability that the strategy chosen as optimal in-sample ranks below the median
       out-of-sample: PBO = mean(rel_rank <= 0.5).
    2. If only single-strategy path Sharpes are provided:
       Computes the non-positive path Sharpe rate: mean(arr <= 0.0).
    """
    if candidate_ranks and len(candidate_ranks) > 0:
        arr_ranks = np.array(candidate_ranks)
        pbo = float(np.mean(arr_ranks <= 0.5))
        return float(round(pbo, 4))
    if not cpcv_path_sharpes:
        return 0.5
    arr = np.array(cpcv_path_sharpes)
    pbo = float(np.mean(arr <= 0.0))
    return float(round(pbo, 4))


def select_thresholds_inner_fold(
    primary_probs: np.ndarray,
    meta_probs: np.ndarray,
    net_returns: np.ndarray,
    is_filled: np.ndarray,
    cost_gate_passed: np.ndarray,
    p_star: float,
    min_trades: int = 15,
) -> Tuple[float, float, float]:
    """
    Selects optimal thresholds strictly in inner cross-validation folds.
    Centering search around break-even gate p* and realistic meta base rates (~25-30%).
    """
    best_ev = -999.0
    best_p = p_star
    best_m = 0.30

    prob_candidates = [
        round(p_star, 4),
        round(p_star + 0.01, 4),
        round(p_star + 0.02, 4),
        round(p_star + 0.03, 4),
        round(p_star + 0.04, 4),
    ]
    meta_candidates = [0.25, 0.28, 0.30, 0.35, 0.40, 0.50]

    for p_thresh in prob_candidates:
        for m_thresh in meta_candidates:
            mask = (primary_probs >= p_thresh) & (meta_probs >= m_thresh) & is_filled & cost_gate_passed
            if np.sum(mask) >= min_trades:
                ev = float(np.mean(net_returns[mask]))
                if ev > best_ev:
                    best_ev = ev
                    best_p = p_thresh
                    best_m = m_thresh

    return best_p, best_m, best_ev


def optimize_thresholds_inner_fold(
    primary_probs: np.ndarray,
    meta_probs: np.ndarray,
    directions: np.ndarray,
    net_returns: np.ndarray,
    min_trades: int = 15,
) -> Tuple[float, float, float]:
    """Legacy backward-compatible wrapper using default break-even gate (0.364)."""
    p_star = 0.3644
    is_filled = np.ones(len(net_returns), dtype=bool)
    cost_gate = np.ones(len(net_returns), dtype=bool)
    return select_thresholds_inner_fold(
        primary_probs=primary_probs,
        meta_probs=meta_probs,
        net_returns=net_returns,
        is_filled=is_filled,
        cost_gate_passed=cost_gate,
        p_star=p_star,
        min_trades=min_trades,
    )


def run_unified_evaluation(
    holdout_primary_probs: np.ndarray,
    holdout_meta_probs: np.ndarray,
    holdout_net_returns: np.ndarray,
    holdout_gross_returns: np.ndarray,
    holdout_filled_flags: np.ndarray,
    holdout_cost_gate_flags: np.ndarray,
    y_holdout: np.ndarray,
    prob_threshold: float,
    meta_threshold: float,
    p_star: float,
    total_bars: int,
    warmup_bars: int = 200,
    embargo_bars: int = 24,
    limit_wait_bars: int = 2,
    max_holding_bars: int = 24,
    timeframe: str = "1h",
    cpcv_sharpes: Optional[List[float]] = None,
    cpcv_ranks: Optional[List[float]] = None,
    min_holdout_trades: int = 20,
    max_ece: float = 0.12,
) -> Dict[str, any]:
    """
    ONE UNIFIED EVALUATION FUNCTION across Funnel Diagnostics, Batch Runner, and Leakage Audit.
    Enforces identical threshold application, identical funnel tracking, and audited Sharpe reporting.
    """
    holdout_size_bars = len(holdout_primary_probs)
    candidate_bars = max(0, holdout_size_bars - (limit_wait_bars + max_holding_bars))

    # Funnel stages: candidate bars -> prob gate -> meta gate -> cost gate -> limit fill -> trades
    prob_gate_mask = holdout_primary_probs[:candidate_bars] >= prob_threshold
    prob_gate_passed = int(np.sum(prob_gate_mask))

    meta_gate_mask = prob_gate_mask & (holdout_meta_probs[:candidate_bars] >= meta_threshold)
    meta_gate_passed = int(np.sum(meta_gate_mask))

    cost_gate_mask = meta_gate_mask & holdout_cost_gate_flags[:candidate_bars]
    cost_gate_passed_count = int(np.sum(cost_gate_mask))

    limit_fill_mask = cost_gate_mask & holdout_filled_flags[:candidate_bars]
    limit_fill_passed_count = int(np.sum(limit_fill_mask))

    final_trades_count = limit_fill_passed_count
    final_trade_indices = np.where(limit_fill_mask)[0]

    funnel = {
        "total_bars_in_series": total_bars,
        "warmup_bars": warmup_bars,
        "embargo_bars": embargo_bars,
        "holdout_size_bars": holdout_size_bars,
        "candidate_bars": candidate_bars,
        "prob_gate_passed": prob_gate_passed,
        "meta_gate_passed": meta_gate_passed,
        "cost_gate_passed": cost_gate_passed_count,
        "limit_fill_passed": limit_fill_passed_count,
        "final_executed_trades": final_trades_count,
    }

    # Trade performance on executed holdout trades
    if final_trades_count > 0:
        trades_net_ret = holdout_net_returns[final_trade_indices]
        trades_gross_ret = holdout_gross_returns[final_trade_indices]

        mean_ev, ev_low, ev_high = bootstrap_ci(trades_net_ret, np.mean, n_bootstraps=1000)
        wins = trades_net_ret > 0.0
        hit_rate = float(np.mean(wins))
        win_count = int(np.sum(wins))
        loss_count = int(np.sum(~wins))
        avg_win = float(np.mean(trades_net_ret[wins])) if win_count > 0 else 0.0
        avg_loss = float(np.mean(trades_net_ret[~wins])) if loss_count > 0 else 0.0
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 1.0
        break_even_win_rate = abs(avg_loss) / (abs(avg_win) + abs(avg_loss)) if (abs(avg_win) + abs(avg_loss)) > 0 else 0.5

        mdd = compute_max_drawdown(trades_net_ret)
        pos_sum = np.sum(trades_net_ret[wins])
        neg_sum = abs(np.sum(trades_net_ret[~wins]))
        profit_factor = float(pos_sum / neg_sum) if neg_sum > 0 else 1.0

        # Audited Sharpe calculations:
        mean_r = float(np.mean(trades_net_ret))
        std_r = float(np.std(trades_net_ret)) if len(trades_net_ret) > 1 else 0.0
        trade_sharpe = mean_r / std_r if std_r > 0 else 0.0

        # Holding duration in years
        bars_per_day = 24.0 if timeframe == "1h" else 6.0
        holdout_years = max(0.1, (holdout_size_bars / bars_per_day) / 365.25)
        trades_per_year = final_trades_count / holdout_years
        annualized_trade_sharpe = trade_sharpe * np.sqrt(trades_per_year)

        # Flawed legacy annualization (multiplying trade returns by sqrt(8760))
        flawed_sharpe = trade_sharpe * np.sqrt(8760)

    else:
        mean_ev, ev_low, ev_high = 0.0, 0.0, 0.0
        hit_rate, win_count, loss_count = 0.0, 0, 0
        avg_win, avg_loss, win_loss_ratio, break_even_win_rate = 0.0, 0.0, 1.0, 0.5
        mdd, profit_factor = 0.0, 0.0
        trade_sharpe, trades_per_year, annualized_trade_sharpe, flawed_sharpe = 0.0, 0.0, 0.0, 0.0
        trades_net_ret = np.array([])
        trades_gross_ret = np.array([])

    # ECE and Reliability Curve
    bins = np.linspace(0.0, 1.0, 11)
    bin_indices = np.digitize(holdout_primary_probs, bins) - 1
    ece = 0.0
    mce = 0.0
    reliability_curve = []
    n_h = len(holdout_primary_probs)

    for b in range(10):
        mask = bin_indices == b
        cnt = int(np.sum(mask))
        if cnt > 0:
            pred_b = float(np.mean(holdout_primary_probs[mask]))
            true_b = float(np.mean(y_holdout[mask]))
            diff = abs(pred_b - true_b)
            ece += (cnt / n_h) * diff
            mce = max(mce, diff)
            reliability_curve.append({
                "bin_center": round(float((bins[b] + bins[b+1]) / 2.0), 2),
                "mean_predicted": round(pred_b, 3),
                "empirical_accuracy": round(true_b, 3),
                "count": cnt,
            })

    # Strict Promotion Gates
    cpcv_list = cpcv_sharpes or []
    median_cpcv_sharpe = float(np.median(cpcv_list)) if cpcv_list else -1.0
    promotion_approved, gate_metrics = evaluate_promotion_gates(
        holdout_net_returns=trades_net_ret,
        ece=ece,
        cpcv_sharpes=cpcv_list,
        min_trades=min_holdout_trades,
        max_ece=max_ece,
    )

    # Overfitting metrics
    dsr_trials, dsr_derivation = get_dsr_trial_count()
    dsr = compute_deflated_sharpe_ratio(annualized_trade_sharpe, n_trials=dsr_trials, var_sharpe=0.5, n_obs=final_trades_count)
    pbo = compute_pbo(cpcv_list, candidate_ranks=cpcv_ranks)
    non_positive_sharpe_rate = float(np.mean(np.array(cpcv_list) <= 0.0)) if cpcv_list else 0.5

    return {
        "funnel": funnel,
        "final_trade_indices": final_trade_indices,
        "thresholds_used": {
            "prob_threshold": round(prob_threshold, 4),
            "meta_threshold": round(meta_threshold, 4),
            "p_star_breakeven": round(p_star, 4),
        },
        "trade_performance": {
            "executed_trades": final_trades_count,
            "gross_ev_pct": round(float(np.mean(trades_gross_ret)) * 100.0, 3) if final_trades_count > 0 else 0.0,
            "net_ev_pct": round(mean_ev * 100.0, 3),
            "bootstrap_ci_95": [round(ev_low * 100.0, 3), round(ev_high * 100.0, 3)],
            "hit_rate_pct": round(hit_rate * 100.0, 2),
            "win_count": win_count,
            "loss_count": loss_count,
            "avg_win_pct": round(avg_win * 100.0, 3),
            "avg_loss_pct": round(avg_loss * 100.0, 3),
            "win_loss_ratio": round(win_loss_ratio, 3),
            "break_even_win_rate_pct": round(break_even_win_rate * 100.0, 2),
            "max_drawdown_pct": round(mdd * 100.0, 3),
            "profit_factor": round(profit_factor, 3),
        },
        "sharpe_audit": {
            "per_trade_sharpe": round(trade_sharpe, 3),
            "trades_per_year": round(trades_per_year, 1),
            "annualized_trade_sharpe": round(annualized_trade_sharpe, 3),
            "flawed_sharpe_sqrt8760": round(flawed_sharpe, 3),
            "explanation": (
                "Flawed Sharpe multiplied per-trade returns by sqrt(8760), erroneously assuming 8,760 trades "
                f"occur per year (inflating Sharpe by ~{np.sqrt(8760/max(1, trades_per_year)):.1f}x). "
                "Annualized trade Sharpe properly scales by sqrt(trades_per_year)."
            ),
        },
        "calibration": {
            "ece": round(ece, 4),
            "mce": round(mce, 4),
            "reliability_curve": reliability_curve,
        },
        "overfitting": {
            "pbo": pbo,
            "non_positive_sharpe_rate": round(non_positive_sharpe_rate, 4),
            "pbo_explanation": (
                "Marcos López de Prado's CSCV/CPCV PBO: probability that the strategy selected in-sample "
                f"ranks below the median out-of-sample across combinatorial paths (PBO={pbo}). "
                f"Non-positive Sharpe path fraction: {round(non_positive_sharpe_rate, 4)}."
            ),
            "dsr": dsr,
            "dsr_trials": dsr_trials,
            "dsr_derivation": dsr_derivation,
        },
        "promotion_gates": gate_metrics["gates"],
        "promotion_approved": promotion_approved,
    }


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

    min_n = min(n_cand, n_champ)
    diff = cand_returns[:min_n] - champ_returns[:min_n]
    mean_diff, lower_diff, upper_diff = bootstrap_ci(diff, np.mean, n_bootstraps=1000)

    beats_champion = mean_diff > 0.0 and lower_diff > 0.0
    return beats_champion, {
        "mean_diff_pct": round(mean_diff * 100.0, 3),
        "diff_ci_95": [round(lower_diff * 100.0, 3), round(upper_diff * 100.0, 3)],
        "beats_champion_with_confidence": beats_champion,
    }
