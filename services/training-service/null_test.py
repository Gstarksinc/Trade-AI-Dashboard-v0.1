"""Phase 6.8 Item 1: Null Test Validation Suite.

Executes the identical CPCV Sharpe + PBO pipeline on:
(a) Label-shuffled data (20 seeds)
(b) Random probabilities (20 seeds)
For BTC/ETH on 1h and 4h.

Verifies the Null Hypothesis:
- Median CPCV Sharpe <= 0.0 (or insufficient)
- PBO distribution centered near ~0.50
"""

import asyncio
import logging
from typing import Dict, List
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier

from batch_runner import fetch_binance_klines
from evaluator import derive_breakeven_probability_gate, run_cpcv_pbo_pipeline
from services.feature_service.indicators.pipeline import build_point_in_time_features
from labeling import apply_triple_barrier_with_execution, compute_sample_uniqueness_weights
from cross_validation import PurgedKFoldCV
from trainer import ModelTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("null_test")


async def run_null_tests_for_pair(symbol: str, tf: str, n_seeds: int = 20) -> Dict[str, any]:
    log.info("Preparing baseline data for %s %s...", symbol, tf)
    trainer = ModelTrainer()
    
    # 1. Load data
    candles, _ = await trainer.load_training_data(symbol, tf, limit=None)
    if len(candles) < 300:
        candles = await fetch_binance_klines(symbol, tf, limit=1500)
    
    ref_btc = None
    if symbol != "BTCUSDT":
        ref_btc = await fetch_binance_klines("BTCUSDT", tf, limit=1500)

    features = build_point_in_time_features(candles, btc_candles=ref_btc)
    
    # Labeling matching trainer.py exactly
    labels_df, fill_stats = apply_triple_barrier_with_execution(
        candles,
        pt_multiplier=2.0,
        sl_multiplier=1.0,
        max_holding_bars=24,
        limit_wait_bars=2,
        max_cost_to_risk=0.25,
        timeframe=tf,
    )
    
    event_starts = pd.Series(candles.index, index=candles.index)
    event_ends = labels_df["touch_time"]
    weights = compute_sample_uniqueness_weights(event_starts, event_ends)
    
    exclude_cols = {
        "open", "high", "low", "close", "volume", "taker_buy_base", "open_time", "close_time",
        "oi_change_4", "oi_change_24", "oi_zscore", "sum_open_interest",
        "lsr_ratio", "lsr_delta_4", "lsr_zscore", "ratio",
    }
    feature_cols = [c for c in features.columns if c not in exclude_cols]
    X = features[feature_cols].copy().replace([np.inf, -np.inf], 0.0).fillna(0.0)
    y = (labels_df["label"] == 1).astype(int)
    net_returns = labels_df["net_return"].values
    is_filled = labels_df["is_filled"].values
    cost_gate_passed = labels_df["cost_gate_passed"].values
    
    # Compute break-even p* matching trainer.py
    p_star = derive_breakeven_probability_gate(
        pt_multiplier=2.0, sl_multiplier=1.0, friction=0.0014, avg_sl_pct=0.015
    )
    
    # 20% holdout split
    n = len(X)
    split_idx = int(n * 0.80)
    train_end_idx = split_idx - 24
    
    X_train = X.iloc[:train_end_idx]
    y_train = y.iloc[:train_end_idx]
    w_train = weights.iloc[:train_end_idx]
    starts_tr = event_starts.iloc[:train_end_idx]
    ends_tr = event_ends.iloc[:train_end_idx]
    
    # Fit canonical OOF predictions on real features
    purged_cv = PurgedKFoldCV(n_splits=5, max_holding_bars=24, event_times=(starts_tr, ends_tr))
    oof_primary_probs = np.zeros(len(X_train))
    for tr_idx, val_idx in purged_cv.split(X_train):
        sub_clf = LGBMClassifier(n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42, verbose=-1)
        sub_clf.fit(X_train.iloc[tr_idx], y_train.iloc[tr_idx], sample_weight=w_train.iloc[tr_idx])
        oof_primary_probs[val_idx] = sub_clf.predict_proba(X_train.iloc[val_idx])[:, 1]
    
    X_tr_meta = X_train.copy()
    X_tr_meta["primary_prob"] = oof_primary_probs
    X_tr_meta["primary_conf"] = np.abs(oof_primary_probs - 0.5)
    meta_y_train = (net_returns[:train_end_idx] > 0.0) & cost_gate_passed[:train_end_idx] & is_filled[:train_end_idx]
    rf_meta = RandomForestClassifier(n_estimators=80, max_depth=4, random_state=42)
    rf_meta.fit(X_tr_meta, meta_y_train.astype(int))
    meta_oof_probs = rf_meta.predict_proba(X_tr_meta)[:, 1]
    
    # (a) Label-shuffled null test (20 seeds)
    log.info("Running (a) Label-shuffled null test (20 seeds) for %s %s...", symbol, tf)
    shuffled_sharpes = []
    shuffled_pbos = []
    shuffled_insufficient_count = 0
    
    for seed in range(1, n_seeds + 1):
        rng = np.random.default_rng(seed)
        permuted_returns = rng.permutation(net_returns[:train_end_idx])
        
        res = run_cpcv_pbo_pipeline(
            oof_primary_probs=oof_primary_probs,
            meta_oof_probs=meta_oof_probs,
            net_returns=permuted_returns,
            is_filled=is_filled[:train_end_idx],
            cost_gate_passed=cost_gate_passed[:train_end_idx],
            starts_tr=starts_tr,
            ends_tr=ends_tr,
            p_star=p_star,
            timeframe=tf,
        )
        shuffled_pbos.append(res["pbo"])
        if isinstance(res["median_cpcv_sharpe"], (int, float)):
            shuffled_sharpes.append(res["median_cpcv_sharpe"])
        else:
            shuffled_insufficient_count += 1
            shuffled_sharpes.append(0.0)  # non-positive
    
    # (b) Random probabilities null test (20 seeds)
    log.info("Running (b) Random probabilities null test (20 seeds) for %s %s...", symbol, tf)
    random_prob_sharpes = []
    random_prob_pbos = []
    random_prob_insufficient_count = 0
    
    for seed in range(1, n_seeds + 1):
        rng = np.random.default_rng(seed + 100)
        rand_primary = rng.uniform(0.30, 0.70, size=len(oof_primary_probs))
        rand_meta = rng.uniform(0.20, 0.60, size=len(meta_oof_probs))
        
        res = run_cpcv_pbo_pipeline(
            oof_primary_probs=rand_primary,
            meta_oof_probs=rand_meta,
            net_returns=net_returns[:train_end_idx],
            is_filled=is_filled[:train_end_idx],
            cost_gate_passed=cost_gate_passed[:train_end_idx],
            starts_tr=starts_tr,
            ends_tr=ends_tr,
            p_star=p_star,
            timeframe=tf,
        )
        random_prob_pbos.append(res["pbo"])
        if isinstance(res["median_cpcv_sharpe"], (int, float)):
            random_prob_sharpes.append(res["median_cpcv_sharpe"])
        else:
            random_prob_insufficient_count += 1
            random_prob_sharpes.append(0.0)

    return {
        "symbol": symbol,
        "timeframe": tf,
        "n_seeds": n_seeds,
        "label_shuffled": {
            "pbo_mean": float(np.mean(shuffled_pbos)),
            "pbo_median": float(np.median(shuffled_pbos)),
            "pbo_std": float(np.std(shuffled_pbos)),
            "pbo_min": float(np.min(shuffled_pbos)),
            "pbo_max": float(np.max(shuffled_pbos)),
            "sharpe_median": float(np.median(shuffled_sharpes)),
            "sharpe_max": float(np.max(shuffled_sharpes)),
            "insufficient_runs": shuffled_insufficient_count,
            "all_pbos": shuffled_pbos,
        },
        "random_probabilities": {
            "pbo_mean": float(np.mean(random_prob_pbos)),
            "pbo_median": float(np.median(random_prob_pbos)),
            "pbo_std": float(np.std(random_prob_pbos)),
            "pbo_min": float(np.min(random_prob_pbos)),
            "pbo_max": float(np.max(random_prob_pbos)),
            "sharpe_median": float(np.median(random_prob_sharpes)),
            "sharpe_max": float(np.max(random_prob_sharpes)),
            "insufficient_runs": random_prob_insufficient_count,
            "all_pbos": random_prob_pbos,
        },
    }


async def main():
    pairs = [
        ("BTCUSDT", "1h"),
        ("BTCUSDT", "4h"),
        ("ETHUSDT", "1h"),
        ("ETHUSDT", "4h"),
    ]
    
    all_results = []
    print("\n" + "=" * 90)
    print("PHASE 6.8 ITEM 1: NULL TEST SUITE (20 SEEDS EACH - LABEL SHUFFLE & RANDOM PROBABILITIES)")
    print("=" * 90)
    
    for sym, tf in pairs:
        res = await run_null_tests_for_pair(sym, tf, n_seeds=20)
        all_results.append(res)
        
        ls = res["label_shuffled"]
        rp = res["random_probabilities"]
        
        print(f"\nResults for {sym} {tf}:")
        print(f"  (a) Label-Shuffled Data (20 seeds):")
        print(f"      PBO Distribution: mean={ls['pbo_mean']:.3f}, median={ls['pbo_median']:.3f}, std={ls['pbo_std']:.3f}, min={ls['pbo_min']:.3f}, max={ls['pbo_max']:.3f}")
        print(f"      Median CPCV Sharpe: median={ls['sharpe_median']:.3f}, max={ls['sharpe_max']:.3f} (Insufficient runs: {ls['insufficient_runs']}/20)")
        print(f"      Validation: PBO ~0.50 ({'PASS' if 0.40 <= ls['pbo_mean'] <= 0.60 else 'CHECK'}), Median Sharpe <= 0 ({'PASS' if ls['sharpe_median'] <= 0.0 else 'FAIL'})")
        
        print(f"  (b) Random Probabilities (20 seeds):")
        print(f"      PBO Distribution: mean={rp['pbo_mean']:.3f}, median={rp['pbo_median']:.3f}, std={rp['pbo_std']:.3f}, min={rp['pbo_min']:.3f}, max={rp['pbo_max']:.3f}")
        print(f"      Median CPCV Sharpe: median={rp['sharpe_median']:.3f}, max={rp['sharpe_max']:.3f} (Insufficient runs: {rp['insufficient_runs']}/20)")
        print(f"      Validation: PBO ~0.50 ({'PASS' if 0.40 <= rp['pbo_mean'] <= 0.60 else 'CHECK'}), Median Sharpe <= 0 ({'PASS' if rp['sharpe_median'] <= 0.0 else 'FAIL'})")
    
    print("\n" + "=" * 90)
    print("NULL TEST OVERALL SUMMARY TABLE:")
    print(f"{'Pair':<12} | {'Null Type':<16} | {'Mean PBO':<10} | {'Median PBO':<10} | {'Median Sharpe':<14} | {'Status'}")
    print("-" * 90)
    for r in all_results:
        sym_tf = f"{r['symbol']} {r['timeframe']}"
        ls = r["label_shuffled"]
        rp = r["random_probabilities"]
        status_ls = "PASS" if (0.40 <= ls['pbo_mean'] <= 0.60 and ls['sharpe_median'] <= 0.0) else "WARN"
        status_rp = "PASS" if (0.40 <= rp['pbo_mean'] <= 0.60 and rp['sharpe_median'] <= 0.0) else "WARN"
        print(f"{sym_tf:<12} | {'Label Shuffled':<16} | {ls['pbo_mean']:<10.3f} | {ls['pbo_median']:<10.3f} | {ls['sharpe_median']:<14.3f} | {status_ls}")
        print(f"{sym_tf:<12} | {'Random Probs':<16} | {rp['pbo_mean']:<10.3f} | {rp['pbo_median']:<10.3f} | {rp['sharpe_median']:<14.3f} | {status_rp}")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(main())
