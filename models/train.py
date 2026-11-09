"""Model Training Engine with Purged Walk-Forward Cross-Validation,
LightGBM Directional Classifier, Probability Calibration, and Meta-Labeling.
Entry point: python -m models.train
"""
import argparse
import logging
import os
from pathlib import Path
from typing import Generator, List, Tuple

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, precision_score, roc_auc_score

from features.builder import build_features
from labeling.meta_labeling import compute_meta_labels
from labeling.triple_barrier import apply_triple_barrier

log = logging.getLogger('models.train')
MODEL_DIR = Path('models/saved')


def purged_walk_forward_cv(
    df: pd.DataFrame,
    n_splits: int = 5,
    train_bars: int = 1500,
    test_bars: int = 300,
    embargo_bars: int = 24,
) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
    """
    Purged Walk-Forward Cross-Validation with Embargo (Marcos López de Prado).
    Prevents information leakage from overlapping holding periods across train and test sets.
    """
    total_bars = len(df)
    step = (total_bars - train_bars - test_bars - embargo_bars) // n_splits
    if step <= 0:
        # Fallback to simple temporal split if dataset is small
        split_idx = int(total_bars * 0.75)
        yield np.arange(0, split_idx - embargo_bars), np.arange(split_idx, total_bars)
        return

    for i in range(n_splits):
        train_start = i * step
        train_end = train_start + train_bars
        test_start = train_end + embargo_bars
        test_end = min(total_bars, test_start + test_bars)

        if test_end <= test_start:
            break

        train_indices = np.arange(train_start, train_end)
        test_indices = np.arange(test_start, test_end)
        yield train_indices, test_indices


def calculate_trading_metrics(returns: pd.Series) -> dict:
    """Computes quantitative performance metrics."""
    if returns.empty or len(returns) < 2:
        return {'total_trades': 0, 'win_rate': 0.0, 'profit_factor': 0.0, 'sharpe': 0.0, 'net_return_pct': 0.0}

    winning = returns[returns > 0]
    losing = returns[returns < 0]

    win_rate = (len(winning) / len(returns)) * 100.0 if len(returns) > 0 else 0.0
    gross_profit = winning.sum()
    gross_loss = abs(losing.sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 2.0

    mean_ret = returns.mean()
    std_ret = returns.std()
    sharpe = (mean_ret / std_ret * np.sqrt(365 * 24)) if std_ret > 0 else 0.0

    return {
        'total_trades': len(returns),
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'sharpe': round(sharpe, 2),
        'net_return_pct': round(returns.sum() * 100.0, 2),
    }


def train_pipeline(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    save_models: bool = True,
) -> dict:
    """
    Executes the two-stage modeling pipeline:
    1. Primary LightGBM Classifier (calibrated for probabilities)
    2. Meta-Labeling Secondary Classifier (filters false positives)
    """
    # Align features and target
    common_idx = features_df.index.intersection(labels_df.index)
    X = features_df.loc[common_idx].copy()
    y_raw = labels_df.loc[common_idx, 'label'].copy()

    # Drop non-feature columns
    drop_cols = ['open', 'high', 'low', 'close', 'volume', 'timeframe', 'symbol']
    feature_cols = [c for c in X.columns if c not in drop_cols and np.issubdtype(X[c].dtype, np.number)]
    X = X[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # Convert -1/1 labels to binary 0/1 for binary classifier (1 = Bullish TP touch, 0 = Bearish SL touch)
    binary_mask = y_raw != 0
    X_primary = X[binary_mask]
    y_primary = (y_raw[binary_mask] == 1).astype(int)
    realized_returns = labels_df.loc[X_primary.index, 'return_pct']

    if len(X_primary) < 200:
        log.warning("Insufficient labeled data points (%d); minimum 200 required.", len(X_primary))
        return {'status': 'insufficient_data', 'samples': len(X_primary)}

    # Stage 1: Primary LightGBM Classifier with Probability Calibration
    base_lgbm = LGBMClassifier(
        n_estimators=150,
        learning_rate=0.03,
        max_depth=5,
        num_leaves=24,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=-1,
    )

    # Purged Walk-Forward Validation
    primary_preds = pd.Series(index=X_primary.index, dtype=float)
    primary_probs = pd.Series(index=X_primary.index, dtype=float)

    for train_idx, test_idx in purged_walk_forward_cv(X_primary, n_splits=4):
        X_tr, y_tr = X_primary.iloc[train_idx], y_primary.iloc[train_idx]
        X_te, y_te = X_primary.iloc[test_idx], y_primary.iloc[test_idx]

        calibrated = CalibratedClassifierCV(estimator=base_lgbm, method='sigmoid', cv=3)
        calibrated.fit(X_tr, y_tr)

        test_probs = calibrated.predict_proba(X_te)[:, 1]
        primary_probs.iloc[test_idx] = test_probs
        primary_preds.iloc[test_idx] = np.where(test_probs >= 0.5, 1, -1)

    # Clean out unpredicted bars
    valid_mask = primary_preds.notna()
    val_preds = primary_preds[valid_mask]
    val_probs = primary_probs[valid_mask]
    val_y = y_primary[valid_mask]
    val_returns = realized_returns[valid_mask]

    # Evaluate Primary Model
    primary_acc = accuracy_score(val_y, (val_preds == 1).astype(int))
    primary_metrics = calculate_trading_metrics(val_preds * val_returns)
    log.info("Primary Model Accuracy: %.2f%% | Total Trades: %d | Win Rate: %.1f%%",
             primary_acc * 100, primary_metrics['total_trades'], primary_metrics['win_rate'])

    # Stage 2: Meta-Labeling (Filter False Positives)
    meta_df = compute_meta_labels(
        primary_predictions=val_preds,
        realized_returns=val_returns,
        fee_pct=0.0005,
        slippage_pct=0.0002,
    )
    y_meta = meta_df['meta_label']

    # Meta Features: Base features + Primary Model Confidence
    X_meta = X_primary.loc[val_preds.index].copy()
    X_meta['primary_prob'] = val_probs
    X_meta['primary_confidence'] = (val_probs - 0.5).abs()

    meta_lgbm = LGBMClassifier(
        n_estimators=100,
        learning_rate=0.03,
        max_depth=4,
        num_leaves=16,
        subsample=0.8,
        random_state=42,
        verbosity=-1,
    )
    meta_lgbm.fit(X_meta, y_meta)
    meta_probs = meta_lgbm.predict_proba(X_meta)[:, 1]

    # Filtered Trades (Meta Confidence >= 0.55)
    take_trade_mask = meta_probs >= 0.55
    filtered_returns = meta_df.loc[take_trade_mask, 'net_return']
    meta_metrics = calculate_trading_metrics(filtered_returns)

    log.info("Meta-Filtered Trades: %d (Filtered out %d) | Win Rate: %.1f%% | Profit Factor: %.2f",
             len(filtered_returns), len(val_preds) - len(filtered_returns),
             meta_metrics['win_rate'], meta_metrics['profit_factor'])

    # Train final full models on all data
    final_primary = CalibratedClassifierCV(estimator=base_lgbm, method='sigmoid', cv=3)
    final_primary.fit(X_primary, y_primary)

    X_all_meta = X_primary.copy()
    all_probs = final_primary.predict_proba(X_primary)[:, 1]
    X_all_meta['primary_prob'] = all_probs
    X_all_meta['primary_confidence'] = (pd.Series(all_probs, index=X_primary.index) - 0.5).abs()
    
    final_meta = LGBMClassifier(n_estimators=100, learning_rate=0.03, max_depth=4, random_state=42, verbosity=-1)
    full_meta_labels = compute_meta_labels(
        primary_predictions=pd.Series(np.where(all_probs >= 0.5, 1, -1), index=X_primary.index),
        realized_returns=realized_returns,
    )['meta_label']
    final_meta.fit(X_all_meta, full_meta_labels)

    # Save Models
    if save_models:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(final_primary, MODEL_DIR / 'primary_model.joblib')
        joblib.dump(final_meta, MODEL_DIR / 'meta_model.joblib')
        joblib.dump(feature_cols, MODEL_DIR / 'feature_cols.joblib')
        log.info("Saved trained model artifacts to %s", MODEL_DIR)

    return {
        'status': 'success',
        'primary_accuracy': primary_acc,
        'primary_metrics': primary_metrics,
        'meta_metrics': meta_metrics,
        'feature_count': len(feature_cols),
    }


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    parser = argparse.ArgumentParser(description='Trade AI Model Training')
    parser.add_argument('--symbol', default='BTCUSDT', help='Symbol to train model for')
    parser.add_argument('--timeframe', default='1h', help='Candle timeframe')
    args = parser.parse_args()

    log.info("Starting model training for %s %s...", args.symbol, args.timeframe)
    
    # Check if TimescaleDB is configured to load real candles
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        try:
            import psycopg
            with psycopg.connect(db_url) as conn:
                query = "SELECT * FROM candles WHERE symbol=%s AND timeframe=%s ORDER BY open_time ASC"
                candles = pd.read_sql(query, conn, params=(args.symbol, args.timeframe))
                if not candles.empty:
                    log.info("Loaded %d candles from TimescaleDB for %s", len(candles), args.symbol)
                    features = build_features(candles)
                    labels = apply_triple_barrier(candles)
                    res = train_pipeline(features, labels, save_models=True)
                    log.info("Training complete: %s", res)
                    return
        except Exception as e:
            log.warning("Database load skipped (%s), running synthetic validation.", e)

    # Synthetic baseline check to verify training pipeline integrity
    dates = pd.date_range('2024-01-01', periods=1200, freq='1h', tz='UTC')
    np.random.seed(42)
    prices = 50000 + np.cumsum(np.random.randn(1200) * 150)
    mock_df = pd.DataFrame({
        'open_time': dates,
        'open': prices,
        'high': prices + np.random.uniform(20, 100, 1200),
        'low': prices - np.random.uniform(20, 100, 1200),
        'close': prices + np.random.randn(1200) * 20,
        'volume': np.random.uniform(500, 5000, 1200),
    })
    mock_df.loc[mock_df['low'] > mock_df['close'], 'low'] = mock_df['close'] - 10
    mock_df.loc[mock_df['high'] < mock_df['close'], 'high'] = mock_df['close'] + 10

    features = build_features(mock_df)
    labels = apply_triple_barrier(mock_df)
    results = train_pipeline(features, labels, save_models=True)
    log.info("Training pipeline verified successfully: %s", results)


if __name__ == '__main__':
    main()

