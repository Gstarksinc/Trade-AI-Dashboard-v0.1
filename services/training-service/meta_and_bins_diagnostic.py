"""Phase 6.8 Items 6 & 7: Meta-Model Evaluation & Unfiltered Prediction-Bin Table.

Item 6:
Compare Primary-Only vs Primary+Meta on the holdout across BTC/ETH 1h/4h.
If Meta does not beat Primary-Only, add a config flag to disable it and document.

Item 7:
Generate unfiltered 10-bin prediction calibration table with n, mean prob,
empirical win rate %, and 95% bootstrap confidence intervals per bin.
"""

import asyncio
import logging
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

from batch_runner import fetch_binance_klines
from evaluator import bootstrap_ci, derive_breakeven_probability_gate, run_unified_evaluation
from services.feature_service.indicators.pipeline import build_point_in_time_features
from trainer import ModelTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("meta_bins_diag")


def compute_prediction_bin_table(
    probs: np.ndarray,
    y_true: np.ndarray,
    n_bins: int = 10,
) -> List[Dict[str, any]]:
    """Generates standard unfiltered 10-bin calibration table with 95% bootstrap CIs."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.digitize(probs, bins) - 1
    
    bin_rows = []
    for i in range(n_bins):
        mask = bin_idx == i
        n = int(np.sum(mask))
        bin_label = f"[{bins[i]:.1f}, {bins[i+1]:.1f})" if i < n_bins - 1 else f"[{bins[i]:.1f}, {bins[i+1]:.1f}]"
        
        if n > 0:
            mean_prob = float(np.mean(probs[mask]))
            y_bin = y_true[mask]
            win_rate = float(np.mean(y_bin)) * 100.0
            if n >= 5:
                _, ci_low, ci_high = bootstrap_ci(y_bin, np.mean, n_bootstraps=1000)
                ci_low_pct = round(ci_low * 100.0, 2)
                ci_high_pct = round(ci_high * 100.0, 2)
            else:
                ci_low_pct = round(win_rate, 2)
                ci_high_pct = round(win_rate, 2)
        else:
            mean_prob = round((bins[i] + bins[i+1]) / 2.0, 3)
            win_rate = 0.0
            ci_low_pct = 0.0
            ci_high_pct = 0.0
            
        bin_rows.append({
            "bin": i + 1,
            "range": bin_label,
            "n": n,
            "mean_prob": round(mean_prob, 4),
            "empirical_win_rate_pct": round(win_rate, 2),
            "ci_95": [ci_low_pct, ci_high_pct],
        })
    return bin_rows


async def run_meta_and_bins_evaluation(symbol: str, tf: str) -> Dict[str, any]:
    trainer = ModelTrainer()
    candles, _ = await trainer.load_training_data(symbol, tf, limit=None)
    if len(candles) < 300:
        candles = await fetch_binance_klines(symbol, tf, limit=1500)

    ref_btc = None
    if symbol != "BTCUSDT":
        ref_btc = await fetch_binance_klines("BTCUSDT", tf, limit=1500)

    features = build_point_in_time_features(candles, btc_candles=ref_btc)

    # Train canonical model pipeline
    out = trainer.run_training_pipeline(
        candles_df=candles,
        features_df=features,
        symbol=symbol,
        timeframe=tf,
        feature_set_version="v1.0.0",
        holdout_pct=0.20,
    )
    
    # Load canonical artifact bundle
    bundle_path = trainer.artifacts_dir / f"{symbol}_{tf}_canonical.joblib"
    import joblib
    bundle = joblib.load(bundle_path)
    
    calibrated_primary = bundle["primary_model"]
    rf_meta = bundle["meta_model"]
    feature_cols = bundle["feature_cols"]
    thresholds = bundle["thresholds"]
    best_p = thresholds["prob_threshold"]
    best_m = thresholds["meta_threshold"]
    p_star = thresholds["p_star"]
    
    # Prepare holdout set
    from trainer import apply_triple_barrier_with_execution
    labels_df, _ = apply_triple_barrier_with_execution(
        candles,
        pt_multiplier=2.0,
        sl_multiplier=1.0,
        max_holding_bars=24,
        limit_wait_bars=2,
        max_cost_to_risk=0.25,
        timeframe=tf,
    )
    
    X = features[feature_cols].copy().replace([np.inf, -np.inf], 0.0).fillna(0.0)
    y = (labels_df["label"] == 1).astype(int).values
    net_returns = labels_df["net_return"].values
    gross_returns = labels_df["gross_return"].values
    is_filled = labels_df["is_filled"].values
    cost_gate_passed = labels_df["cost_gate_passed"].values
    
    split_idx = int(len(X) * 0.80)
    X_holdout = X.iloc[split_idx:]
    y_h = y[split_idx:]
    net_r_h = net_returns[split_idx:]
    gross_r_h = gross_returns[split_idx:]
    filled_h = is_filled[split_idx:]
    cost_gate_h = cost_gate_passed[split_idx:]
    
    holdout_primary_probs = calibrated_primary.predict_proba(X_holdout)[:, 1]
    X_h_meta = X_holdout.copy()
    X_h_meta["primary_prob"] = holdout_primary_probs
    X_h_meta["primary_conf"] = np.abs(holdout_primary_probs - 0.5)
    holdout_meta_probs = rf_meta.predict_proba(X_h_meta)[:, 1]
    
    # 1. Primary + Meta Evaluation
    eval_with_meta = run_unified_evaluation(
        holdout_primary_probs=holdout_primary_probs,
        holdout_meta_probs=holdout_meta_probs,
        holdout_net_returns=net_r_h,
        holdout_gross_returns=gross_r_h,
        holdout_filled_flags=filled_h,
        holdout_cost_gate_flags=cost_gate_h,
        y_holdout=y_h,
        prob_threshold=best_p,
        meta_threshold=best_m,
        p_star=p_star,
        total_bars=len(candles),
        timeframe=tf,
    )
    
    # 2. Primary-Only Evaluation (meta threshold set to 0.0 effectively bypassing meta gate)
    eval_primary_only = run_unified_evaluation(
        holdout_primary_probs=holdout_primary_probs,
        holdout_meta_probs=holdout_meta_probs,
        holdout_net_returns=net_r_h,
        holdout_gross_returns=gross_r_h,
        holdout_filled_flags=filled_h,
        holdout_cost_gate_flags=cost_gate_h,
        y_holdout=y_h,
        prob_threshold=best_p,
        meta_threshold=0.0,  # Bypass meta gate
        p_star=p_star,
        total_bars=len(candles),
        timeframe=tf,
    )
    
    # 3. Item 7: Prediction-bin calibration table
    bin_table = compute_prediction_bin_table(holdout_primary_probs, y_h, n_bins=10)
    
    return {
        "symbol": symbol,
        "timeframe": tf,
        "with_meta": eval_with_meta["trade_performance"],
        "primary_only": eval_primary_only["trade_performance"],
        "bin_table": bin_table,
    }


async def main():
    pairs = [
        ("BTCUSDT", "1h"),
        ("BTCUSDT", "4h"),
        ("ETHUSDT", "1h"),
        ("ETHUSDT", "4h"),
    ]
    
    print("\n" + "=" * 90)
    print("PHASE 6.8 ITEM 6: META-MODEL VS PRIMARY-ONLY COMPARISON ON HOLDOUT")
    print("=" * 90)
    
    comparisons = []
    bin_tables = {}
    
    for sym, tf in pairs:
        res = await run_meta_and_bins_evaluation(sym, tf)
        wm = res["with_meta"]
        po = res["primary_only"]
        
        meta_beats_primary = (wm["net_ev_pct"] > po["net_ev_pct"]) or (wm["net_ev_pct"] == po["net_ev_pct"] and wm["hit_rate_pct"] > po["hit_rate_pct"])
        comparisons.append({
            "pair": f"{sym} {tf}",
            "po_trades": po["executed_trades"],
            "po_ev": po["net_ev_pct"],
            "po_ci": po["bootstrap_ci_95"],
            "po_hit": po["hit_rate_pct"],
            "wm_trades": wm["executed_trades"],
            "wm_ev": wm["net_ev_pct"],
            "wm_ci": wm["bootstrap_ci_95"],
            "wm_hit": wm["hit_rate_pct"],
            "meta_beats_primary": meta_beats_primary,
        })
        bin_tables[f"{sym}_{tf}"] = res["bin_table"]
    
    print(f"{'Pair':<12} | {'Primary-Only (N / EV% / Hit%)':<30} | {'Primary+Meta (N / EV% / Hit%)':<30} | {'Meta Beats?'}")
    print("-" * 90)
    any_meta_beats = False
    for c in comparisons:
        po_str = f"N={c['po_trades']:<2} | EV={c['po_ev']:>5.2f}% | Hit={c['po_hit']:>4.1f}%"
        wm_str = f"N={c['wm_trades']:<2} | EV={c['wm_ev']:>5.2f}% | Hit={c['wm_hit']:>4.1f}%"
        beats_str = "YES" if c["meta_beats_primary"] else "NO"
        if c["meta_beats_primary"]:
            any_meta_beats = True
        print(f"{c['pair']:<12} | {po_str:<30} | {wm_str:<30} | {beats_str}")
    print("=" * 90)
    
    print("\n" + "=" * 90)
    print("PHASE 6.8 ITEM 7: UNFILTERED PREDICTION-BIN TABLES (10 DECILES WITH N & 95% CI)")
    print("=" * 90)
    
    for key, table in bin_tables.items():
        print(f"\n--- Prediction Bins for {key} ---")
        print(f"{'Bin':<4} | {'Range':<14} | {'N':<6} | {'Mean Prob':<10} | {'Win Rate %':<12} | {'95% Bootstrap CI'}")
        print("-" * 75)
        for row in table:
            ci_str = f"[{row['ci_95'][0]:.1f}%, {row['ci_95'][1]:.1f}%]"
            print(f"{row['bin']:<4} | {row['range']:<14} | {row['n']:<6} | {row['mean_prob']:<10.4f} | {row['empirical_win_rate_pct']:<12.2f} | {ci_str}")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(main())
