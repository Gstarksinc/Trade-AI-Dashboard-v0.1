"""Trade AI Real-Time Signal Generator / Inference Engine.
Generates signals for active symbols using LightGBM + Meta-Classifier + Risk Engine,
inserts them into TimescaleDB, and publishes alerts to Redis.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np
import pandas as pd
import psycopg
from psycopg.rows import dict_row
import redis

from features.builder import build_features
from risk.engine import RiskEngine, RiskLimits, calculate_trade_levels

log = logging.getLogger('models.predict')
MODEL_DIR = Path('models/saved')

DATABASE_URL = os.environ.get('DATABASE_URL', '')
REDIS_URL = os.environ.get('REDIS_URL', '')


class SignalPredictor:
    def __init__(self, model_dir: Path = MODEL_DIR):
        self.model_dir = model_dir
        self.primary_model = None
        self.meta_model = None
        self.feature_cols = None
        self.risk_engine = RiskEngine()
        self.load_models()

    def load_models(self) -> bool:
        """Loads trained joblib models if present."""
        try:
            p_path = self.model_dir / 'primary_model.joblib'
            m_path = self.model_dir / 'meta_model.joblib'
            f_path = self.model_dir / 'feature_cols.joblib'

            if p_path.exists() and m_path.exists() and f_path.exists():
                self.primary_model = joblib.load(p_path)
                self.meta_model = joblib.load(m_path)
                self.feature_cols = joblib.load(f_path)
                log.info("Loaded trained LightGBM models from %s", self.model_dir)
                return True
        except Exception as e:
            log.warning("Could not load trained models: %s", e)
        return False

    def predict_latest(self, features_df: pd.DataFrame) -> Optional[dict]:
        """
        Runs model inference on the newest row of features.
        Returns prediction dict with direction, probability, meta_probability, and ATR.
        """
        if features_df.empty:
            return None

        latest_row = features_df.iloc[-1:]
        close = float(latest_row['close'].iloc[0])
        atr = float(latest_row['atr_14'].iloc[0]) if 'atr_14' in latest_row else (close * 0.01)

        # 1. Model Inference (if models are loaded)
        if self.primary_model and self.feature_cols:
            try:
                # Align columns
                missing_cols = [c for c in self.feature_cols if c not in latest_row.columns]
                X = latest_row.copy()
                for c in missing_cols:
                    X[c] = 0.0
                X_vals = X[self.feature_cols].replace([np.inf, -np.inf], 0.0).fillna(0.0)

                # Primary probability
                probs = self.primary_model.predict_proba(X_vals)[0]
                prob_up = float(probs[1]) if len(probs) > 1 else float(probs[0])
                direction = 'long' if prob_up >= 0.5 else 'short'
                primary_prob = prob_up if direction == 'long' else (1.0 - prob_up)

                # Meta-classifier probability
                X_meta = X_vals.copy()
                X_meta['primary_prob'] = prob_up
                X_meta['primary_confidence'] = abs(prob_up - 0.5)

                meta_prob = 0.65
                if self.meta_model:
                    m_probs = self.meta_model.predict_proba(X_meta)[0]
                    meta_prob = float(m_probs[1]) if len(m_probs) > 1 else float(m_probs[0])

                return {
                    'direction': direction,
                    'probability': round(primary_prob, 3),
                    'meta_probability': round(meta_prob, 3),
                    'current_price': close,
                    'atr': atr,
                    'model_version': 'LightGBM-v0.1 + Meta-Classifier',
                }
            except Exception as e:
                log.warning("Inference failed, using algorithmic indicator logic: %s", e)

        # 2. Algorithmic Fallback Heuristic (RSI + MACD + Trend)
        rsi = float(latest_row['rsi_14'].iloc[0]) if 'rsi_14' in latest_row else 50.0
        macd_hist = float(latest_row['macd_hist'].iloc[0]) if 'macd_hist' in latest_row else 0.0
        ema_ratio_50 = float(latest_row['ema_ratio_50'].iloc[0]) if 'ema_ratio_50' in latest_row else 0.0

        if rsi < 42 and macd_hist > 0 and ema_ratio_50 > -0.05:
            direction = 'long'
            prob = 0.62 + min(0.12, (50 - rsi) * 0.01)
            meta_prob = 0.74
        elif rsi > 58 and macd_hist < 0 and ema_ratio_50 < 0.05:
            direction = 'short'
            prob = 0.61 + min(0.12, (rsi - 50) * 0.01)
            meta_prob = 0.72
        else:
            return None  # No high-conviction setup

        return {
            'direction': direction,
            'probability': round(prob, 3),
            'meta_probability': round(meta_prob, 3),
            'current_price': close,
            'atr': atr,
            'model_version': 'Algorithmic-ATR-Baseline',
        }


def scan_and_generate_signals():
    """
    Scans active symbols from TimescaleDB candles, evaluates signals,
    and inserts approved setups into the database.
    """
    if not DATABASE_URL:
        log.warning("DATABASE_URL not configured.")
        return

    predictor = SignalPredictor()
    r_client = redis.from_url(REDIS_URL) if REDIS_URL else None

    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT', 'TRXUSDT']
    timeframes = ['15m', '1h', '4h']

    try:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # Get current open signals to enforce correlation limits
                cur.execute("SELECT symbol, timeframe, direction, status FROM signals WHERE status = 'open'")
                open_signals = cur.fetchall()

                # Get daily loss used
                cur.execute("""
                    SELECT coalesce(sum(pnl_pct), 0) as daily_pnl
                    FROM paper_trades
                    WHERE closed_at >= now() - interval '24 hours'
                """)
                daily_row = cur.fetchone()
                daily_pnl = float(daily_row['daily_pnl'] or 0.0)
                daily_loss_used = max(0.0, -daily_pnl)

                for sym in symbols:
                    for tf in timeframes:
                        # Avoid duplicating open signals for the same symbol & timeframe
                        already_open = any(s['symbol'] == sym and s['timeframe'] == tf for s in open_signals)
                        if already_open:
                            continue

                        # Load recent candles
                        cur.execute("""
                            SELECT open_time, open, high, low, close, volume, taker_buy_base
                            FROM candles
                            WHERE symbol = %s AND timeframe = %s
                            ORDER BY open_time DESC
                            LIMIT 150
                        """, (sym, tf))
                        candles_data = cur.fetchall()
                        if len(candles_data) < 30:
                            continue

                        # Convert to DataFrame
                        candles_df = pd.DataFrame(candles_data).sort_values('open_time').reset_index(drop=True)
                        features_df = build_features(candles_df)

                        pred = predictor.predict_latest(features_df)
                        if not pred or pred['probability'] < 0.55:
                            continue

                        # Calculate trade levels
                        levels = calculate_trade_levels(
                            current_price=pred['current_price'],
                            atr=pred['atr'],
                            direction=pred['direction'],
                            pt_mult=2.2,
                            sl_mult=1.0,
                        )

                        candidate = {
                            'symbol': sym,
                            'timeframe': tf,
                            'direction': pred['direction'],
                            'probability': pred['probability'],
                            'meta_probability': pred['meta_probability'],
                            'entry': levels['entry'],
                            'stop_loss': levels['stop_loss'],
                            'take_profit': levels['take_profit'],
                            'atr': levels['atr'],
                            'model_version': pred['model_version'],
                        }

                        # Validate with Risk Engine
                        approved, reason = predictor.risk_engine.validate_new_signal(
                            new_signal=candidate,
                            current_open_signals=open_signals,
                            daily_loss_used_pct=daily_loss_used,
                        )

                        if approved:
                            # Insert into database
                            cur.execute("""
                                INSERT INTO signals (
                                    symbol, timeframe, direction, probability, meta_probability,
                                    entry, stop_loss, take_profit, atr, model_version, status, created_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', now())
                                RETURNING id
                            """, (
                                candidate['symbol'],
                                candidate['timeframe'],
                                candidate['direction'],
                                candidate['probability'],
                                candidate['meta_probability'],
                                candidate['entry'],
                                candidate['stop_loss'],
                                candidate['take_profit'],
                                candidate['atr'],
                                candidate['model_version'],
                            ))
                            signal_id = cur.fetchone()['id']
                            conn.commit()

                            log.info("Generated new signal: %s %s %s (ID: %d)", sym, tf, candidate['direction'].upper(), signal_id)

                            # Publish to Redis
                            if r_client:
                                try:
                                    candidate['id'] = signal_id
                                    candidate['created_at'] = datetime.now(timezone.utc).isoformat()
                                    r_client.publish('signals:new', json.dumps(candidate))
                                except Exception:
                                    pass

                            open_signals.append(candidate)
                        else:
                            log.debug("Rejected signal for %s %s: %s", sym, tf, reason)
    except Exception as e:
        log.exception("Signal scan failed: %s", e)
    finally:
        if r_client:
            r_client.close()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    log.info("Running real-time signal generation scan...")
    scan_and_generate_signals()


if __name__ == '__main__':
    main()

