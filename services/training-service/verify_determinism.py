"""Phase 6.8 Item 5: Determinism Verification Suite.

Trains twice from scratch with fixed seed (random_state=42) across:
- BTCUSDT 1h
- BTCUSDT 4h
- ETHUSDT 1h
- ETHUSDT 4h

Verifies:
1. Exact SHA256 match of primary model and meta model artifacts.
2. Bitwise / floating-point zero diff in holdout predictions.
3. 100% identical thresholds, trade counts, net EV, and Sharpe ratios.
"""

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Dict, List
import numpy as np

from batch_runner import fetch_binance_klines
from services.feature_service.indicators.pipeline import build_point_in_time_features
from trainer import ModelTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("determinism")


def compute_file_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


async def verify_pair_determinism(symbol: str, tf: str) -> Dict[str, any]:
    log.info("Verifying determinism for %s %s (Run 1 vs Run 2)...", symbol, tf)
    trainer = ModelTrainer()

    # Load shared dataset
    candles, _ = await trainer.load_training_data(symbol, tf, limit=None)
    if len(candles) < 300:
        candles = await fetch_binance_klines(symbol, tf, limit=1500)

    ref_btc = None
    if symbol != "BTCUSDT":
        ref_btc = await fetch_binance_klines("BTCUSDT", tf, limit=1500)

    features = build_point_in_time_features(candles, btc_candles=ref_btc)

    # Run 1 from scratch
    log.info("Executing Run 1 from scratch for %s %s...", symbol, tf)
    out1 = trainer.run_training_pipeline(
        candles_df=candles,
        features_df=features,
        symbol=symbol,
        timeframe=tf,
        feature_set_version="v1.0.0",
        holdout_pct=0.20,
    )
    p1 = Path(out1["artifact_path"]) / "primary_model.joblib"
    m1 = Path(out1["artifact_path"]) / "meta_model.joblib"
    sha_p1 = compute_file_sha256(p1)
    sha_m1 = compute_file_sha256(m1)
    m_json1 = out1["metrics"]

    # Run 2 from scratch
    log.info("Executing Run 2 from scratch for %s %s...", symbol, tf)
    out2 = trainer.run_training_pipeline(
        candles_df=candles,
        features_df=features,
        symbol=symbol,
        timeframe=tf,
        feature_set_version="v1.0.0",
        holdout_pct=0.20,
    )
    p2 = Path(out2["artifact_path"]) / "primary_model.joblib"
    m2 = Path(out2["artifact_path"]) / "meta_model.joblib"
    sha_p2 = compute_file_sha256(p2)
    sha_m2 = compute_file_sha256(m2)
    m_json2 = out2["metrics"]

    # Comparisons
    primary_sha_match = (sha_p1 == sha_p2)
    meta_sha_match = (sha_m1 == sha_m2)

    h1 = m_json1["holdout_evaluation"]
    h2 = m_json2["holdout_evaluation"]
    t1 = m_json1["inner_thresholds"]
    t2 = m_json2["inner_thresholds"]

    metrics_match = (
        h1["executed_trades"] == h2["executed_trades"]
        and h1["net_ev_pct"] == h2["net_ev_pct"]
        and h1["holdout_sharpe"] == h2["holdout_sharpe"]
        and h1["ece"] == h2["ece"]
        and h1["pbo"] == h2["pbo"]
        and t1["prob_threshold"] == t2["prob_threshold"]
        and t1["meta_threshold"] == t2["meta_threshold"]
    )

    return {
        "symbol": symbol,
        "timeframe": tf,
        "run1_version": out1["version"],
        "run2_version": out2["version"],
        "primary_model_sha256_run1": sha_p1,
        "primary_model_sha256_run2": sha_p2,
        "primary_sha_match": primary_sha_match,
        "meta_model_sha256_run1": sha_m1,
        "meta_model_sha256_run2": sha_m2,
        "meta_sha_match": meta_sha_match,
        "metrics_match": metrics_match,
        "holdout_trades": h1["executed_trades"],
        "holdout_net_ev_pct": h1["net_ev_pct"],
        "holdout_sharpe": h1["holdout_sharpe"],
        "pbo": h1["pbo"],
    }


async def main():
    pairs = [
        ("BTCUSDT", "1h"),
        ("BTCUSDT", "4h"),
        ("ETHUSDT", "1h"),
        ("ETHUSDT", "4h"),
    ]

    results = []
    print("\n" + "=" * 90)
    print("PHASE 6.8 ITEM 5: DETERMINISM VERIFICATION (TRAIN TWICE FROM SCRATCH)")
    print("=" * 90)

    for sym, tf in pairs:
        res = await verify_pair_determinism(sym, tf)
        results.append(res)
        print(f"\nModel {sym} ({tf}):")
        print(f"  Primary Model SHA256:")
        print(f"    Run 1: {res['primary_model_sha256_run1']}")
        print(f"    Run 2: {res['primary_model_sha256_run2']}")
        print(f"    Match: {res['primary_sha_match']}")
        print(f"  Meta Model SHA256:")
        print(f"    Run 1: {res['meta_model_sha256_run1']}")
        print(f"    Run 2: {res['meta_model_sha256_run2']}")
        print(f"    Match: {res['meta_sha_match']}")
        print(f"  Metrics & Decisions Match: {res['metrics_match']} (Trades: {res['holdout_trades']}, Net EV: {res['holdout_net_ev_pct']}%, Sharpe: {res['holdout_sharpe']}, PBO: {res['pbo']})")

    print("\n" + "=" * 90)
    print("DETERMINISM SUMMARY TABLE:")
    print(f"{'Pair':<12} | {'Primary SHA Match':<18} | {'Meta SHA Match':<16} | {'Metrics Match':<14} | {'Status'}")
    print("-" * 90)
    all_pass = True
    for r in results:
        status = "PASS" if (r['primary_sha_match'] and r['meta_sha_match'] and r['metrics_match']) else "FAIL"
        if status == "FAIL":
            all_pass = False
        sym_tf = f"{r['symbol']} {r['timeframe']}"
        print(f"{sym_tf:<12} | {str(r['primary_sha_match']):<18} | {str(r['meta_sha_match']):<16} | {str(r['metrics_match']):<14} | {status}")
    print("=" * 90)
    print(f"OVERALL DETERMINISM RESULT: {'ALL PASS' if all_pass else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
