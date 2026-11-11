"""Detailed Model Diagnostics Suite (Phase 6.7 Item 4).

Computes:
1. Primary-model AUC and log-loss vs empirical base rate on holdout and per CPCV fold.
2. Gross (pre-cost) EV by prediction decile on holdout.
3. Meta-model AUC restricted to cost-gate-passed bars, and comparison with ATR/NATR-only features.
"""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier


def compute_base_rate_log_loss(y_true: np.ndarray) -> float:
    """Computes the theoretical log-loss of a naive prior predicting the empirical base rate."""
    b = float(np.mean(y_true))
    if b <= 0.0 or b >= 1.0:
        return 0.0
    loss = -(b * np.log(b) + (1.0 - b) * np.log(1.0 - b))
    return float(round(loss, 4))


def run_primary_model_diagnostics(
    y_true: np.ndarray,
    probs: np.ndarray,
) -> Dict[str, float]:
    """Computes AUC, log-loss, and compares against naive base rate."""
    base_rate = float(np.mean(y_true))
    b_loss = compute_base_rate_log_loss(y_true)
    
    # Clip probs for stable log-loss
    clipped_probs = np.clip(probs, 1e-7, 1.0 - 1e-7)
    m_loss = float(log_loss(y_true, clipped_probs))
    
    try:
        auc = float(roc_auc_score(y_true, probs))
    except Exception:
        auc = 0.5

    return {
        "base_rate": round(base_rate, 4),
        "base_rate_log_loss": round(b_loss, 4),
        "model_log_loss": round(m_loss, 4),
        "log_loss_delta": round(m_loss - b_loss, 4),
        "log_loss_better_than_base": m_loss < b_loss,
        "auc": round(auc, 4),
    }


def compute_gross_ev_by_decile(
    probs: np.ndarray,
    gross_returns: np.ndarray,
    n_bins: int = 10,
) -> List[Dict[str, any]]:
    """Partitions predictions into deciles and evaluates gross (pre-cost) return per decile."""
    # Using probability bins [0.0, 0.1, ..., 1.0]
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.digitize(probs, bins) - 1
    
    deciles = []
    for i in range(n_bins):
        mask = bin_idx == i
        cnt = int(np.sum(mask))
        if cnt > 0:
            mean_prob = float(np.mean(probs[mask]))
            gross_ev = float(np.mean(gross_returns[mask])) * 100.0
            pos_rate = float(np.mean(gross_returns[mask] > 0)) * 100.0
        else:
            mean_prob = (bins[i] + bins[i + 1]) / 2.0
            gross_ev = 0.0
            pos_rate = 0.0

        deciles.append({
            "decile": i + 1,
            "bin_range": f"[{bins[i]:.2f}, {bins[i+1]:.2f})",
            "count": cnt,
            "mean_prob": round(mean_prob, 3),
            "gross_ev_pct": round(gross_ev, 3),
            "gross_win_rate_pct": round(pos_rate, 2),
        })
    return deciles


def evaluate_meta_model_diagnostics(
    X_train: pd.DataFrame,
    y_meta_train: np.ndarray,
    X_holdout: pd.DataFrame,
    y_meta_holdout: np.ndarray,
    cost_gate_holdout: np.ndarray,
) -> Dict[str, any]:
    """
    Evaluates meta-model AUC restricted to cost-gate-passed bars,
    comparing full feature set vs ATR/NATR volatility-only feature set.
    """
    # 1. Full feature set meta-model restricted to cost-gate-passed holdout bars
    rf_full = RandomForestClassifier(n_estimators=80, max_depth=4, random_state=42)
    rf_full.fit(X_train, y_meta_train)
    
    holdout_mask = cost_gate_holdout & ~np.isnan(y_meta_holdout)
    if np.sum(holdout_mask) < 10 or len(np.unique(y_meta_holdout[holdout_mask])) < 2:
        return {"error": "Insufficient cost-gate-passed bars for meta AUC"}
        
    probs_full = rf_full.predict_proba(X_holdout.loc[holdout_mask])[:, 1]
    auc_full = float(roc_auc_score(y_meta_holdout[holdout_mask], probs_full))
    
    # 2. ATR/NATR volatility-only features
    vol_cols = [c for c in X_train.columns if any(k in c.lower() for k in ["atr", "natr", "volatility", "bb_width"])]
    if not vol_cols:
        vol_cols = ["atr_14"] if "atr_14" in X_train.columns else [X_train.columns[0]]
        
    rf_vol = RandomForestClassifier(n_estimators=80, max_depth=3, random_state=42)
    rf_vol.fit(X_train[vol_cols], y_meta_train)
    probs_vol = rf_vol.predict_proba(X_holdout[vol_cols].loc[holdout_mask])[:, 1]
    auc_vol = float(roc_auc_score(y_meta_holdout[holdout_mask], probs_vol))
    
    return {
        "cost_gate_passed_holdout_bars": int(np.sum(holdout_mask)),
        "meta_base_rate_pct": round(float(np.mean(y_meta_holdout[holdout_mask])) * 100.0, 2),
        "meta_auc_all_features": round(auc_full, 4),
        "meta_auc_atr_natr_only": round(auc_vol, 4),
        "volatility_features_used": vol_cols,
    }

