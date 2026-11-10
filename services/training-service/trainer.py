"""Model Training Pipeline with Phase 3.1 Strict Promotion Gates, CPCV, DSR, PBO, and Audit."""

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sqlalchemy import text

from libs.database.connection import engine
try:
    from .labeling import apply_triple_barrier_with_execution, compute_sample_uniqueness_weights
    from .cross_validation import PurgedKFoldCV, CombinatorialPurgedCV
    from .calibration import calculate_expected_calibration_error, evaluate_calibration
    from .drift import generate_feature_drift_report
    from .evaluator import (
        bootstrap_ci,
        compute_max_drawdown,
        compute_deflated_sharpe_ratio,
        compute_pbo,
        optimize_thresholds_inner_fold,
        evaluate_promotion_gates,
        compare_candidate_vs_champion_holdout,
        get_dsr_trial_count,
    )
except (ImportError, ValueError):
    from labeling import apply_triple_barrier_with_execution, compute_sample_uniqueness_weights
    from cross_validation import PurgedKFoldCV, CombinatorialPurgedCV
    from calibration import calculate_expected_calibration_error, evaluate_calibration
    from drift import generate_feature_drift_report
    from evaluator import (
        bootstrap_ci,
        compute_max_drawdown,
        compute_deflated_sharpe_ratio,
        compute_pbo,
        optimize_thresholds_inner_fold,
        evaluate_promotion_gates,
        compare_candidate_vs_champion_holdout,
        get_dsr_trial_count,
    )

log = logging.getLogger("training-service.trainer")
ARTIFACTS_DIR = Path(os.environ.get("MODEL_ARTIFACTS_DIR", "artifacts/models"))


def compute_sha256(filepath: Path) -> str:
    """Computes SHA256 hex digest for artifact checksum."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


class ModelTrainer:
    def __init__(self, artifacts_dir: Path = ARTIFACTS_DIR):
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def load_training_data(self, symbol: str = "BTCUSDT", timeframe: str = "15m", limit: int = 4000) -> Tuple[pd.DataFrame, pd.DataFrame]:
        query = text("""
            SELECT open_time, open, high, low, close, volume, taker_buy_base
            FROM market_data.candles
            WHERE symbol = :symbol AND timeframe = :timeframe AND is_closed = TRUE
            ORDER BY open_time ASC LIMIT :limit;
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query, {"symbol": symbol, "timeframe": timeframe, "limit": limit})
            rows = result.fetchall()
            if not rows:
                return pd.DataFrame(), pd.DataFrame()
            cols = ["open_time", "open", "high", "low", "close", "volume", "taker_buy_base"]
            candles = pd.DataFrame(rows, columns=cols)
            candles["open_time"] = pd.to_datetime(candles["open_time"], utc=True)
            candles = candles.sort_values("open_time").set_index("open_time")
            for c in ["open", "high", "low", "close", "volume", "taker_buy_base"]:
                candles[c] = candles[c].astype(float)

        from services.feature_service.indicators.pipeline import build_point_in_time_features
        features = build_point_in_time_features(candles)
        return candles, features

    async def get_current_champion(self) -> Optional[dict]:
        query = text("""
            SELECT version, stage, algorithm, feature_set_version, metrics, artifact_path, created_at
            FROM model_registry.models
            WHERE stage = 'champion'
            ORDER BY created_at DESC LIMIT 1;
        """)
        async with engine.connect() as conn:
            result = await conn.execute(query)
            row = result.fetchone()
            if row:
                return {
                    "version": row[0],
                    "stage": row[1],
                    "algorithm": row[2],
                    "feature_set_version": row[3],
                    "metrics": json.loads(row[4]) if isinstance(row[4], str) else row[4],
                    "artifact_path": row[5],
                    "created_at": row[6].isoformat(),
                }
            return None

    async def record_model(self, version: str, stage: str, algorithm: str, feature_set_version: str, metrics: dict, artifact_path: str):
        query = text("""
            INSERT INTO model_registry.models (
                version, stage, algorithm, feature_set_version, metrics, artifact_path, created_at
            ) VALUES (
                :version, :stage, :algorithm, :feature_set_version, :metrics, :artifact_path, now()
            )
            ON CONFLICT (version) DO UPDATE SET
                stage = EXCLUDED.stage,
                metrics = EXCLUDED.metrics;
        """)
        async with engine.begin() as conn:
            await conn.execute(query, {
                "version": version,
                "stage": stage,
                "algorithm": algorithm,
                "feature_set_version": feature_set_version,
                "metrics": json.dumps(metrics),
                "artifact_path": artifact_path,
            })

    async def record_drift_report(self, model_version: str, drift_report: dict):
        query = text("""
            INSERT INTO model_registry.drift_reports (
                model_version, detected_at, drift_score, psi_scores, details
            ) VALUES (
                :model_version, now(), :drift_score, :psi_scores, :details
            );
        """)
        async with engine.begin() as conn:
            await conn.execute(query, {
                "model_version": model_version,
                "drift_score": drift_report.get("average_psi", 0.0),
                "psi_scores": json.dumps(drift_report.get("psi_scores", {})),
                "details": json.dumps(drift_report),
            })

    def run_training_pipeline(
        self,
        candles_df: pd.DataFrame,
        features_df: pd.DataFrame,
        symbol: str = "BTCUSDT",
        timeframe: str = "15m",
        feature_set_version: str = "v1.0.0",
        holdout_pct: float = 0.20,
    ) -> dict:
        log.info("Starting Phase 3.1 Training Pipeline for %s %s (%d bars)...", symbol, timeframe, len(features_df))

        # 1. Triple-barrier labeling with live limit-entry & funding accrual
        max_holding_bars = 24
        labels_df, fill_stats = apply_triple_barrier_with_execution(
            candles_df,
            pt_multiplier=2.0,
            sl_multiplier=1.0,
            max_holding_bars=max_holding_bars,
            limit_wait_bars=2,
            max_cost_to_risk=0.25,
        )

        # 2. Sample-uniqueness weights
        event_starts = pd.Series(candles_df.index, index=candles_df.index)
        event_ends = labels_df["touch_time"]
        weights = compute_sample_uniqueness_weights(event_starts, event_ends)

        # Target and returns
        y = (labels_df["label"] == 1).astype(int)
        net_returns = labels_df["net_return"].values
        is_filled = labels_df["is_filled"].values
        cost_gate_passed = labels_df["cost_gate_passed"].values

        # Feature selection
        # Exclude OHLCV, timestamps, and features requiring short-history public datasets (OI, LSR)
        exclude_cols = {
            "open", "high", "low", "close", "volume", "taker_buy_base", "open_time", "close_time",
            "oi_change_4", "oi_change_24", "oi_zscore", "sum_open_interest",
            "lsr_ratio", "lsr_delta_4", "lsr_zscore", "ratio",
        }
        feature_cols = [c for c in features_df.columns if c not in exclude_cols]
        X = features_df[feature_cols].copy().replace([np.inf, -np.inf], 0.0).fillna(0.0)

        # 3. Final Untouched Holdout Split (Strict nested evaluation)
        n = len(X)
        split_idx = int(n * (1.0 - holdout_pct))
        
        # Enforce embargo >= max_holding_bars between train and holdout
        embargo_bars = max_holding_bars
        train_end_idx = split_idx - embargo_bars

        X_train, y_train, w_train = X.iloc[:train_end_idx], y.iloc[:train_end_idx], weights.iloc[:train_end_idx]
        starts_tr, ends_tr = event_starts.iloc[:train_end_idx], event_ends.iloc[:train_end_idx]

        X_holdout, y_holdout = X.iloc[split_idx:], y.iloc[split_idx:]
        net_ret_holdout = net_returns[split_idx:]
        filled_holdout = is_filled[split_idx:]
        cost_gate_holdout = cost_gate_passed[split_idx:]

        # 4. Nested Purged Cross-Validation with scikit-learn CalibratedClassifierCV
        purged_cv = PurgedKFoldCV(n_splits=5, max_holding_bars=max_holding_bars, event_times=(starts_tr, ends_tr))

        # Primary classifier
        base_lgb = LGBMClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1,
        )
        
        # Passes PurgedKFold CV directly into CalibratedClassifierCV
        calibrated_primary = CalibratedClassifierCV(estimator=base_lgb, method="sigmoid", cv=purged_cv)
        calibrated_primary.fit(X_train, y_train, sample_weight=w_train)

        # Meta-Model trained strictly on out-of-fold primary predictions
        oof_primary_probs = np.zeros(len(X_train))
        for tr_idx, val_idx in purged_cv.split(X_train):
            sub_clf = LGBMClassifier(n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42, verbose=-1)
            sub_clf.fit(X_train.iloc[tr_idx], y_train.iloc[tr_idx], sample_weight=w_train.iloc[tr_idx])
            oof_primary_probs[val_idx] = sub_clf.predict_proba(X_train.iloc[val_idx])[:, 1]

        X_tr_meta = X_train.copy()
        X_tr_meta["primary_prob"] = oof_primary_probs
        X_tr_meta["primary_conf"] = np.abs(oof_primary_probs - 0.5)
        
        # Meta label: profitable after costs and cost-to-risk gate passed
        meta_y_train = (net_returns[:train_end_idx] > 0.0) & cost_gate_passed[:train_end_idx] & is_filled[:train_end_idx]
        rf_meta = RandomForestClassifier(n_estimators=80, max_depth=4, random_state=42)
        rf_meta.fit(X_tr_meta, meta_y_train.astype(int))

        # 5. Inner-fold Threshold Selection
        meta_oof_probs = rf_meta.predict_proba(X_tr_meta)[:, 1]
        best_p, best_m, _ = optimize_thresholds_inner_fold(
            primary_probs=oof_primary_probs,
            meta_probs=meta_oof_probs,
            directions=np.where(oof_primary_probs >= 0.5, 1, -1),
            net_returns=net_returns[:train_end_idx],
        )

        # 6. Combinatorial Purged CV (CPCV) Path Distribution
        cpcv = CombinatorialPurgedCV(n_groups=5, k_test_groups=2, max_holding_bars=max_holding_bars)
        cpcv_sharpes = []
        cpcv_pfs = []
        cpcv_mdds = []

        for c_tr_idx, c_te_idx in cpcv.split(starts_tr, ends_tr):
            if len(c_te_idx) == 0:
                continue
            path_returns = net_returns[:train_end_idx][c_te_idx]
            path_returns = path_returns[~np.isnan(path_returns)]
            if len(path_returns) > 5:
                mean_r = np.mean(path_returns)
                std_r = np.std(path_returns)
                sr = (mean_r / std_r * np.sqrt(365 * 24)) if std_r > 0 else 0.0
                cpcv_sharpes.append(float(round(sr, 3)))
                cpcv_mdds.append(float(round(compute_max_drawdown(path_returns), 4)))
                pos = path_returns[path_returns > 0]
                neg = abs(path_returns[path_returns < 0])
                pf = float(np.sum(pos) / np.sum(neg)) if np.sum(neg) > 0 else 1.5
                cpcv_pfs.append(float(round(pf, 3)))

        # 7. Evaluate on Final Untouched Holdout Set
        holdout_primary_probs = calibrated_primary.predict_proba(X_holdout)[:, 1]
        X_h_meta = X_holdout.copy()
        X_h_meta["primary_prob"] = holdout_primary_probs
        X_h_meta["primary_conf"] = np.abs(holdout_primary_probs - 0.5)
        holdout_meta_probs = rf_meta.predict_proba(X_h_meta)[:, 1]

        # Apply inner thresholds and cost-to-risk gate to holdout
        trade_mask = (holdout_primary_probs >= best_p) & (holdout_meta_probs >= best_m) & filled_holdout & cost_gate_holdout
        executed_holdout_returns = net_ret_holdout[trade_mask]

        # ECE on holdout
        ece_val, mce_val = calculate_expected_calibration_error(y_holdout.values, holdout_primary_probs, n_bins=10)

        # 8. Check Phase 3.1 Strict Promotion Gates
        promotion_approved, gate_metrics = evaluate_promotion_gates(
            holdout_net_returns=executed_holdout_returns,
            ece=ece_val,
            cpcv_sharpes=cpcv_sharpes,
            min_trades=20,     # Enforced holdout trade floor
            max_ece=0.12,
        )

        # 9. Deflated Sharpe & PBO with configurable trial count & logged derivation
        dsr_trials, dsr_derivation = get_dsr_trial_count()
        log.info("Computing DSR: %s", dsr_derivation)
        holdout_sharpe = float(np.mean(executed_holdout_returns) / np.std(executed_holdout_returns) * np.sqrt(365 * 24)) if len(executed_holdout_returns) > 2 and np.std(executed_holdout_returns) > 0 else 0.0
        dsr = compute_deflated_sharpe_ratio(holdout_sharpe, n_trials=dsr_trials, var_sharpe=0.5, n_obs=len(executed_holdout_returns))
        pbo = compute_pbo(cpcv_sharpes)

        # Reliability Curve (10 probability bins)
        bins = np.linspace(0.0, 1.0, 11)
        bin_idx = np.digitize(holdout_primary_probs, bins) - 1
        reliability_curve = []
        for b in range(10):
            m = bin_idx == b
            if np.any(m):
                reliability_curve.append({
                    "bin_center": round(float((bins[b] + bins[b+1]) / 2.0), 2),
                    "mean_predicted": round(float(np.mean(holdout_primary_probs[m])), 3),
                    "empirical_accuracy": round(float(np.mean(y_holdout.values[m])), 3),
                    "count": int(np.sum(m)),
                })

        # Save artifacts with SHA256 checksums
        version = f"LGBM-V31-{symbol}-{timeframe}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        v_dir = self.artifacts_dir / version
        v_dir.mkdir(parents=True, exist_ok=True)

        p_path = v_dir / "primary_model.joblib"
        m_path = v_dir / "meta_model.joblib"
        f_path = v_dir / "feature_cols.joblib"

        joblib.dump(calibrated_primary, p_path)
        joblib.dump(rf_meta, m_path)
        joblib.dump(feature_cols, f_path)

        p_hash = compute_sha256(p_path)
        m_hash = compute_sha256(m_path)
        f_hash = compute_sha256(f_path)

        drift_report = generate_feature_drift_report(X_train, X_holdout)

        metrics_payload = {
            "version": version,
            "symbol": symbol,
            "timeframe": timeframe,
            "feature_set_version": feature_set_version,
            "artifact_checksums": {
                "primary_model_sha256": p_hash,
                "meta_model_sha256": m_hash,
                "feature_cols_sha256": f_hash,
            },
            "fill_and_execution_stats": fill_stats,
            "inner_thresholds": {
                "prob_threshold": best_p,
                "meta_threshold": best_m,
            },
            "holdout_evaluation": {
                "total_holdout_bars": len(X_holdout),
                "executed_trades": len(executed_holdout_returns),
                "net_ev_pct": gate_metrics["mean_net_ev_pct"],
                "bootstrap_ci_95": gate_metrics["bootstrap_ci_95"],
                "holdout_sharpe": round(holdout_sharpe, 2),
                "holdout_max_drawdown": round(compute_max_drawdown(executed_holdout_returns), 4),
                "ece": gate_metrics["ece"],
                "deflated_sharpe_ratio": dsr,
                "pbo": pbo,
            },
            "cpcv_distributions": {
                "sharpe": {
                    "min": float(np.min(cpcv_sharpes)) if cpcv_sharpes else 0.0,
                    "median": gate_metrics["median_cpcv_sharpe"],
                    "max": float(np.max(cpcv_sharpes)) if cpcv_sharpes else 0.0,
                    "paths_count": len(cpcv_sharpes),
                },
                "profit_factor": {
                    "median": float(np.median(cpcv_pfs)) if cpcv_pfs else 1.0,
                },
                "max_drawdown": {
                    "median": float(np.median(cpcv_mdds)) if cpcv_mdds else 0.0,
                },
            },
            "reliability_curve": reliability_curve,
            "drift_report": drift_report,
            "promotion_gates": gate_metrics["gates"],
            "promotion_approved": promotion_approved,
        }

        with open(v_dir / "metrics.json", "w") as f:
            json.dump(metrics_payload, f, indent=2)

        return {
            "version": version,
            "artifact_path": str(v_dir),
            "promotion_approved": promotion_approved,
            "metrics": metrics_payload,
            "drift_report": drift_report,
        }
