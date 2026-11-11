"""Database Experiment Logging & Synchronization Suite (Phase 6.8 Item 10).

Manages model_registry.experiments table in TimescaleDB:
1. Seeds initial registered historical trials (EXP-001 through EXP-208).
2. Automatically logs new training evaluations to the DB table.
3. Exports and keeps docs/EXPERIMENTS.md synchronized from the DB table.
4. Provides dynamic trial count for DSR calculation directly from DB count.
"""

import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from libs.database.connection import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("sync_experiments")


INITIAL_EXPERIMENT_BATCHES = [
    {
        "prefix": "EXP-001-050",
        "phase": "3.1",
        "date": "2026-11-09",
        "symbol": "BTC, ETH",
        "timeframe": "1h, 4h",
        "model_name": "LightGBM CPCV Sweeps",
        "prob_thresh": 0.5000,
        "meta_thresh": 0.4000,
        "trials": 50,
        "status": "Rejected",
        "notes": "Initial GBDT sweeps (n in {50, 80, 100, 150}, depth in {3, 4, 5}); lookahead audit failed",
    },
    {
        "prefix": "EXP-051-100",
        "phase": "3.1",
        "date": "2026-11-09",
        "symbol": "BTC, ETH",
        "timeframe": "1h, 4h",
        "model_name": "RF Meta Threshold Grid",
        "prob_thresh": 0.5500,
        "meta_thresh": 0.5000,
        "trials": 50,
        "status": "Rejected",
        "notes": "Raw uncalibrated probability grid search; rejected in favor of isotonic/sigmoid calibration",
    },
    {
        "prefix": "EXP-101-148",
        "phase": "6.5",
        "date": "2026-11-10",
        "symbol": "8 Perpetuals",
        "timeframe": "1h, 4h",
        "model_name": "Calibrated GBDT 3-Seed Re-Audit",
        "prob_thresh": 0.3644,
        "meta_thresh": 0.3000,
        "trials": 48,
        "status": "Rejected",
        "notes": "Seeds 42, 123, 999 on 3+ years backfilled history; 2x cost stress (28 bps); insufficient holdout trades",
    },
    {
        "prefix": "EXP-149-178",
        "phase": "6.6",
        "date": "2026-11-11",
        "symbol": "BTC, ETH",
        "timeframe": "1h, 4h",
        "model_name": "Unified Evaluation Reconciliation",
        "prob_thresh": 0.3644,
        "meta_thresh": 0.3500,
        "trials": 30,
        "status": "Rejected",
        "notes": "Threshold calibration around p*; lower EV bootstrap CI bound < 0; no model promoted",
    },
    {
        "prefix": "EXP-179-208",
        "phase": "6.7",
        "date": "2026-11-11",
        "symbol": "BTC, ETH",
        "timeframe": "1h, 4h",
        "model_name": "Per-Setup Dynamic Break-Even Gates",
        "prob_thresh": 0.3644,
        "meta_thresh": 0.3500,
        "trials": 30,
        "status": "Rejected",
        "notes": "Dynamic p*_i grid from median ATR%; strict promotion gates maintained 100% unpromoted",
    },
]


async def seed_experiments_table() -> int:
    """Seeds the initial 208 trials into model_registry.experiments if not already present."""
    async with engine.begin() as conn:
        # Check current row count
        res = await conn.execute(text("SELECT COUNT(*) FROM model_registry.experiments"))
        count = res.scalar()
        if count and count >= 208:
            log.info("model_registry.experiments table already contains %d trials; skipping seed.", count)
            return count

        log.info("Seeding initial 208 trials into model_registry.experiments...")
        exp_num = 1
        for batch in INITIAL_EXPERIMENT_BATCHES:
            trials_in_batch = batch["trials"]
            for _ in range(trials_in_batch):
                exp_id = f"EXP-{exp_num:03d}"
                await conn.execute(
                    text("""
                        INSERT INTO model_registry.experiments (
                            experiment_id, symbol, timeframe, model_name,
                            prob_threshold, meta_threshold, holdout_trades,
                            holdout_net_ev_pct, holdout_sharpe, pbo, dsr,
                            status, notes
                        ) VALUES (
                            :exp_id, :symbol, :tf, :model_name,
                            :prob_thresh, :meta_thresh, 0,
                            0.0, 0.0, 0.5, 0.0,
                            :status, :notes
                        )
                        ON CONFLICT (experiment_id) DO NOTHING;
                    """),
                    {
                        "exp_id": exp_id,
                        "symbol": batch["symbol"],
                        "tf": batch["timeframe"],
                        "model_name": batch["model_name"],
                        "prob_thresh": batch["prob_thresh"],
                        "meta_thresh": batch["meta_thresh"],
                        "status": batch["status"],
                        "notes": batch["notes"],
                    },
                )
                exp_num += 1

        res_final = await conn.execute(text("SELECT COUNT(*) FROM model_registry.experiments"))
        final_count = res_final.scalar()
        log.info("Successfully seeded model_registry.experiments. Total rows: %d", final_count)
        return final_count


async def log_experiment_to_db(
    symbol: str,
    timeframe: str,
    model_name: str,
    prob_thresh: float,
    meta_thresh: float,
    holdout_trades: int,
    holdout_net_ev_pct: float,
    holdout_sharpe: float,
    pbo: float,
    dsr: float,
    status: str = "Evaluated",
    notes: Optional[str] = None,
) -> str:
    """Logs an individual evaluated experiment trial to model_registry.experiments."""
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT COUNT(*) FROM model_registry.experiments"))
        cnt = res.scalar() or 0
        new_exp_id = f"EXP-{cnt + 1:03d}"
        await conn.execute(
            text("""
                INSERT INTO model_registry.experiments (
                    experiment_id, symbol, timeframe, model_name,
                    prob_threshold, meta_threshold, holdout_trades,
                    holdout_net_ev_pct, holdout_sharpe, pbo, dsr,
                    status, notes
                ) VALUES (
                    :exp_id, :symbol, :tf, :model_name,
                    :prob_thresh, :meta_thresh, :trades,
                    :ev, :sharpe, :pbo, :dsr,
                    :status, :notes
                );
            """),
            {
                "exp_id": new_exp_id,
                "symbol": symbol,
                "tf": timeframe,
                "model_name": model_name,
                "prob_thresh": round(prob_thresh, 4),
                "meta_thresh": round(meta_thresh, 4),
                "trades": holdout_trades,
                "ev": round(holdout_net_ev_pct, 4),
                "sharpe": round(holdout_sharpe, 4),
                "pbo": round(pbo, 4),
                "dsr": round(dsr, 4),
                "status": status,
                "notes": notes or f"Batch evaluation on full history",
            },
        )
        log.info("Logged trial %s to model_registry.experiments (%s %s)", new_exp_id, symbol, timeframe)
        return new_exp_id


async def generate_experiments_md_from_db(output_file: str = "docs/EXPERIMENTS.md") -> int:
    """Queries model_registry.experiments and regenerates docs/EXPERIMENTS.md."""
    async with engine.connect() as conn:
        res = await conn.execute(
            text("SELECT experiment_id, symbol, timeframe, model_name, prob_threshold, meta_threshold, holdout_trades, holdout_net_ev_pct, holdout_sharpe, pbo, dsr, status, notes, created_at FROM model_registry.experiments ORDER BY id ASC")
        )
        rows = res.mappings().all()

    total_trials = len(rows)
    md_path = Path(output_file)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Quantitative Experiment & Trial Registry",
        "",
        "This registry tracks every model architecture, hyperparameter combination, and threshold search variant evaluated across the Trade AI Dashboard project. Under Marcos López de Prado's Deflated Sharpe Ratio (DSR), the expected maximum Sharpe ratio under the null hypothesis of no skill increases with the number of independent trials. Therefore, **the DSR trial count ($N$) is dynamically derived directly from the `model_registry.experiments` database table**.",
        "",
        "---",
        "",
        "## Trial Count Summary",
        "",
        f"| Source Database Table | Total Registered Trials ($N_{{\\text{{trials}}}}$) | Last Synced (UTC) |",
        "| :--- | :---: | :---: |",
        f"| `model_registry.experiments` | **{total_trials}** | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} |",
        "",
        "---",
        "",
        "## Registered Historical Batches",
        "",
        "| Batch Range | Phase | Symbol | TF | Model Family / Strategy | Candidate Grid | Trials | Status / Gate Result |",
        "| :--- | :---: | :---: | :---: | :--- | :--- | :---: | :---: |",
        "| `EXP-001` - `EXP-050` | 3.1 | BTC, ETH | 1h, 4h | LightGBM GBDT | GBDT parameter sweep (depth, lr, estimators) | 50 | Rejected (Lookahead audit failed) |",
        "| `EXP-051` - `EXP-100` | 3.1 | BTC, ETH | 1h, 4h | RF Meta | Static threshold grid search | 50 | Rejected (Uncalibrated probabilities) |",
        "| `EXP-101` - `EXP-148` | 6.5 | 8 Perpetuals | 1h, 4h | Calibrated GBDT | 3 clean seeds (42, 123, 999) + 2x cost stress | 48 | Rejected (Insufficient holdout trades) |",
        "| `EXP-149` - `EXP-178` | 6.6 | BTC, ETH | 1h, 4h | Calibrated + RF | Inner-fold selection around p* | 30 | Rejected (Lower EV CI bound < 0) |",
        "| `EXP-179` - `EXP-208` | 6.7 | BTC, ETH | 1h, 4h | Calibrated + RF | Per-setup dynamic p*_i break-even grid | 30 | Rejected (Zero models promoted) |",
    ]

    # If any experiments were logged beyond 208, add them to a dynamic section
    if total_trials > 208:
        lines.extend([
            "",
            "---",
            "",
            "## Dynamically Logged Experiments",
            "",
            "| ID | Symbol | TF | Model | Prob Thresh | Meta Thresh | Holdout Trades | Net EV % | Sharpe | PBO | DSR | Status |",
            "| :--- | :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ])
        for r in rows[208:]:
            lines.append(
                f"| `{r['experiment_id']}` | {r['symbol']} | {r['timeframe']} | {r['model_name']} | {r['prob_threshold']:.4f} | {r['meta_threshold']:.4f} | {r['holdout_trades']} | {r['holdout_net_ev_pct']:.2f}% | {r['holdout_sharpe']:.2f} | {r['pbo']:.2f} | {r['dsr']:.4f} | {r['status']} |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## Dynamic DSR Derivation Rule",
        "",
        "1. The function `evaluator.py::get_dsr_trial_count()` directly queries `SELECT COUNT(*) FROM model_registry.experiments`.",
        f"2. Current dynamic trial count in database: **{total_trials}**.",
        "3. Formula for Bailey & López de Prado DSR:",
        "   $$\\text{DSR} = \\Phi\\left(\\frac{(\\widehat{\\text{SR}} - \\text{SR}^*) \\sqrt{T-1}}{\\sqrt{1 - \\widehat{\\gamma}_3 \\widehat{\\text{SR}} + \\frac{\\widehat{\\gamma}_4 - 1}{4}\\widehat{\\text{SR}}^2}}\\right)$$",
        "   where:",
        f"   $$\\text{{SR}}^* = \\sqrt{{2 \\ln({total_trials})}} \\left(1 - \\frac{{\\gamma}}{{\\sqrt{{2 \\ln({total_trials})}}}}\\right) + \\frac{{\\text{{Euler-Mascheroni}}}}{{\\sqrt{{2 \\ln({total_trials})}}}}$$",
        f"   with $N_{{\\text{{trials}}}} = {total_trials}$.",
        "",
    ])

    content = "\n".join(lines)
    candidate_paths = [Path("/app/docs/EXPERIMENTS.md"), Path("../../docs/EXPERIMENTS.md"), Path("docs/EXPERIMENTS.md")]
    written = False
    for p in candidate_paths:
        if p.parent.exists() and "services" not in p.resolve().parts:
            p.write_text(content, encoding="utf-8")
            log.info("Successfully generated %s from DB with %d trials.", p, total_trials)
            written = True
            break
    if not written:
        md_path = Path(output_file)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(content, encoding="utf-8")
        log.info("Successfully generated %s from DB with %d trials.", md_path, total_trials)
    return total_trials


async def main():
    count = await seed_experiments_table()
    await generate_experiments_md_from_db()
    print(f"\nSynced model_registry.experiments table with docs/EXPERIMENTS.md. Total trials: {count}")


if __name__ == "__main__":
    asyncio.run(main())
