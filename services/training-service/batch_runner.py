"""Batch Training Runner across all 8 perpetual symbols and 3 timeframes (15m, 1h, 4h).

Generates the Phase 3.1 Comprehensive Multi-Asset Model Evaluation Report.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Dict, List
import httpx
import numpy as np
import pandas as pd

from services.feature_service.indicators.pipeline import build_point_in_time_features
try:
    from .trainer import ModelTrainer
except (ImportError, ValueError):
    from trainer import ModelTrainer

log = logging.getLogger("training-service.batch-runner")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT", "TRXUSDT"]
TIMEFRAMES = ["15m", "1h", "4h"]


async def fetch_binance_klines(symbol: str, interval: str, limit: int = 1500) -> pd.DataFrame:
    """Fetches public historical klines directly from Binance USD-M Futures REST."""
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            log.warning("Failed fetching klines for %s %s: HTTP %d", symbol, interval, resp.status_code)
            return pd.DataFrame()
        raw = resp.json()

    records = []
    for k in raw:
        records.append({
            "open_time": datetime.fromtimestamp(k[0] / 1000.0, tz=timezone.utc),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "taker_buy_base": float(k[9]),
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        df = df.sort_values("open_time").set_index("open_time")
    return df


async def run_batch_evaluation(symbols: List[str] = None, timeframes: List[str] = None) -> Dict[str, any]:
    if symbols is None:
        symbols = SYMBOLS
    if timeframes is None:
        timeframes = TIMEFRAMES

    trainer = ModelTrainer()
    results = []

    # Pre-fetch BTC reference candles for cross-asset correlations
    btc_candles = {}
    for tf in timeframes:
        btc_df, _ = await trainer.load_training_data("BTCUSDT", tf, limit=None)
        if btc_df.empty or len(btc_df) < 300:
            btc_df = await fetch_binance_klines("BTCUSDT", tf, limit=1500)
        btc_candles[tf] = btc_df

    for symbol in symbols:
        for tf in timeframes:
            log.info("Processing training & evaluation for %s %s...", symbol, tf)
            try:
                # 1. Load complete history from TimescaleDB
                candles, _ = await trainer.load_training_data(symbol, tf, limit=None)
                
                # 2. If cold DB, pull directly from public Binance REST
                if len(candles) < 300:
                    candles = await fetch_binance_klines(symbol, tf, limit=1500)

                if len(candles) < 200:
                    log.warning("Skipping %s %s: insufficient bars (%d)", symbol, tf, len(candles))
                    continue

                # Build features with BTC reference
                ref_btc = btc_candles.get(tf) if symbol != "BTCUSDT" else None
                features = build_point_in_time_features(candles, btc_candles=ref_btc)

                # Execute Phase 3.1 pipeline
                pipeline_out = trainer.run_training_pipeline(
                    candles_df=candles,
                    features_df=features,
                    symbol=symbol,
                    timeframe=tf,
                    feature_set_version="v1.0.0",
                    holdout_pct=0.20,
                )

                metrics = pipeline_out["metrics"]
                holdout = metrics["holdout_evaluation"]
                cpcv = metrics["cpcv_distributions"]
                fill_stats = metrics["fill_and_execution_stats"]
                gates = metrics["promotion_gates"]

                summary_entry = {
                    "symbol": symbol,
                    "timeframe": tf,
                    "version": pipeline_out["version"],
                    "total_bars": len(candles),
                    "fill_rate": fill_stats["fill_rate"],
                    "gate_pass_rate": fill_stats["gate_pass_rate"],
                    "thresholds": metrics.get("inner_thresholds", {}),
                    "funnel": metrics.get("funnel", {}),
                    "holdout_trades": holdout["executed_trades"],
                    "holdout_net_ev_pct": holdout["net_ev_pct"],
                    "bootstrap_ci_95": holdout["bootstrap_ci_95"],
                    "holdout_sharpe": holdout["holdout_sharpe"],
                    "per_trade_sharpe": holdout.get("per_trade_sharpe", 0.0),
                    "trades_per_year": holdout.get("trades_per_year", 0.0),
                    "median_cpcv_sharpe": cpcv["sharpe"]["median"],
                    "cpcv_valid_paths": cpcv["sharpe"].get("valid_paths_count", 0),
                    "cpcv_total_paths": cpcv["sharpe"].get("paths_count", 10),
                    "ece": holdout["ece"],
                    "auc": holdout.get("auc", 0.5),
                    "auc_ci_95": holdout.get("auc_ci_95", [0.5, 0.5]),
                    "dsr": holdout["deflated_sharpe_ratio"],
                    "pbo": holdout["pbo"],
                    "promotion_approved": pipeline_out["promotion_approved"],
                    "gates_breakdown": gates,
                }
                results.append(summary_entry)

            except Exception as e:
                log.exception("Error evaluating %s %s: %s", symbol, tf, e)

    report_path = Path("artifacts/reports")
    report_path.mkdir(parents=True, exist_ok=True)
    report_file = report_path / "phase_3_1_training_report.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_models_evaluated": len(results),
        "results": results,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # All 8 symbols across 1h and 4h
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "LINKUSDT", "TRXUSDT"]
    timeframes = ["1h", "4h"]
    out = asyncio.run(run_batch_evaluation(symbols=symbols, timeframes=timeframes))
    
    print("\n" + "=" * 120)
    print("PHASE 6.8 ITEM 4: FINAL EVALUATION TABLE (ALL 8 SYMBOLS x 1h/4h ON FULL HISTORY)")
    print("=" * 120)
    print("| Symbol | TF | Bars | Inner Thresh (p*, prob, meta) | Holdout Trades | Net EV% (95% CI) | CPCV Med Sharpe (valid/10) | PBO | DSR (208 trials) | Primary AUC (95% CI) | Promotion Gate |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for r in out["results"]:
        th = r["thresholds"]
        th_str = f"p*={th.get('p_star_breakeven', 0.364):.3f}, p={th.get('prob_threshold', 0.5):.3f}, m={th.get('meta_threshold', 0.5):.2f}"
        ev_str = f"{r['holdout_net_ev_pct']:.2f}% [{r['bootstrap_ci_95'][0]:.2f}%, {r['bootstrap_ci_95'][1]:.2f}%]"
        cpcv_sh = r["median_cpcv_sharpe"]
        cpcv_str = f"{cpcv_sh:.2f} ({r.get('cpcv_valid_paths', 0)}/10)" if isinstance(cpcv_sh, (int, float)) else f"{cpcv_sh} (0/10)"
        pbo_str = f"{r['pbo']:.3f}" if isinstance(r["pbo"], (int, float)) else str(r["pbo"])
        dsr_str = f"{r['dsr']:.4f}" if isinstance(r["dsr"], (int, float)) else str(r["dsr"])
        auc_ci = r.get("auc_ci_95", [0.5, 0.5])
        auc_str = f"{r.get('auc', 0.5):.3f} [{auc_ci[0]:.3f}, {auc_ci[1]:.3f}]"
        gate_status = "APPROVED" if r["promotion_approved"] else "REJECTED"
        print(f"| {r['symbol']} | {r['timeframe']} | {r['total_bars']} | {th_str} | {r['holdout_trades']} | {ev_str} | {cpcv_str} | {pbo_str} | {dsr_str} | {auc_str} | {gate_status} |")
    print("=" * 120)

