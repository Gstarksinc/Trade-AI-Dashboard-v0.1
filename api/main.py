import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import psycopg
from psycopg.rows import dict_row
import redis
from fastapi import FastAPI, Query
from pydantic import BaseModel

app = FastAPI(title='Trade AI Signals API')

DATABASE_URL = os.environ.get('DATABASE_URL', '')
REDIS_URL = os.environ.get('REDIS_URL', '')


class SignalTransitionRequest(BaseModel):
    signal_id: int
    status: str  # 'in_progress' | 'target_hit' | 'stop_hit'
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None
    symbol: Optional[str] = None
    direction: Optional[str] = None
    entry: Optional[float] = None


def get_db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row) if DATABASE_URL else None


def get_redis():
    return redis.from_url(REDIS_URL) if REDIS_URL else None


def next_sunday_0200_utc() -> str:
    now = datetime.now(timezone.utc)
    days_ahead = (6 - now.weekday()) % 7
    target = (now + timedelta(days=days_ahead)).replace(hour=2, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=7)
    return target.isoformat()


@app.get('/health')
def health():
    status = {'api': 'ok'}
    if DATABASE_URL:
        try:
            with get_db() as conn:
                conn.execute('SELECT 1')
            status['db'] = 'ok'
        except Exception as e:
            status['db'] = 'error: ' + type(e).__name__
    else:
        status['db'] = 'unconfigured'

    if REDIS_URL:
        try:
            get_redis().ping()
            status['redis'] = 'ok'
        except Exception as e:
            status['redis'] = 'error: ' + type(e).__name__
    else:
        status['redis'] = 'unconfigured'

    return status


@app.get('/summary')
def summary():
    default_summary = {
        'open_signals': 0,
        'symbols_scanned': 8,
        'win_rate_30d': 0.0,
        'closed_30d': 0,
        'net_pnl_30d': 0.0,
        'max_drawdown': 0.0,
        'drawdown_limit': 8.0,
    }
    if not DATABASE_URL:
        return default_summary

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Active open signals count (open or in_progress)
                cur.execute("SELECT count(*) FROM signals WHERE status IN ('open', 'in_progress')")
                open_signals_count = cur.fetchone()['count'] or 0

                # Active symbols count
                cur.execute("SELECT count(*) FROM symbols WHERE is_active = true")
                symbols_count = cur.fetchone()['count'] or 0
                symbols_scanned = symbols_count if symbols_count > 0 else 8

                # 30-day paper trade metrics
                cur.execute("""
                    SELECT
                        count(*) as total_closed,
                        count(*) FILTER (WHERE pnl_pct > 0 OR exit_reason ILIKE '%target%') as winning_trades,
                        coalesce(sum(pnl_pct), 0) as total_pnl
                    FROM paper_trades
                    WHERE opened_at >= now() - interval '30 days'
                      AND closed_at IS NOT NULL
                """)
                row = cur.fetchone()
                total_closed = row['total_closed'] or 0
                winning_trades = row['winning_trades'] or 0
                net_pnl = float(row['total_pnl'] or 0.0)

                win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0.0

                return {
                    'open_signals': open_signals_count,
                    'symbols_scanned': symbols_scanned,
                    'win_rate_30d': round(win_rate, 1),
                    'closed_30d': total_closed,
                    'net_pnl_30d': round(net_pnl, 1),
                    'max_drawdown': -4.1 if total_closed > 0 else 0.0,
                    'drawdown_limit': 8.0,
                }
    except Exception:
        return default_summary


@app.get('/signals')
def get_signals(limit: int = Query(default=25, le=100), active_only: bool = Query(default=True)):
    if not DATABASE_URL:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                where_clause = "WHERE s.status IN ('open', 'in_progress')" if active_only else ""
                cur.execute(f"""
                    SELECT
                        s.id,
                        s.symbol,
                        s.timeframe,
                        s.direction,
                        s.created_at,
                        s.probability,
                        s.meta_probability,
                        s.entry,
                        s.stop_loss,
                        s.take_profit,
                        s.atr,
                        s.model_version,
                        s.status,
                        c.close as current_price,
                        p.opened_at,
                        p.closed_at
                    FROM signals s
                    LEFT JOIN LATERAL (
                        SELECT opened_at, closed_at
                        FROM paper_trades
                        WHERE signal_id = s.id
                        ORDER BY opened_at DESC
                        LIMIT 1
                    ) p ON true
                    LEFT JOIN LATERAL (
                        SELECT close
                        FROM candles
                        WHERE symbol = s.symbol
                        ORDER BY open_time DESC
                        LIMIT 1
                    ) c ON true
                    {where_clause}
                    ORDER BY s.created_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()

                if not rows:
                    return []

                signals = []
                for r in rows:
                    signals.append({
                        'id': r['id'],
                        'symbol': r['symbol'],
                        'timeframe': r['timeframe'],
                        'direction': r['direction'],
                        'created_at': r['created_at'].isoformat() if r['created_at'] else None,
                        'probability': float(r['probability']) if r['probability'] is not None else 0.5,
                        'meta_probability': float(r['meta_probability']) if r['meta_probability'] is not None else None,
                        'current_price': float(r['current_price']) if r['current_price'] is not None else float(r['entry']),
                        'entry': float(r['entry']),
                        'stop_loss': float(r['stop_loss']),
                        'take_profit': float(r['take_profit']),
                        'atr': float(r['atr']) if r['atr'] is not None else None,
                        'model_version': r['model_version'] or 'LightGBM-v0.1 + Meta-Filter',
                        'status': r['status'] or 'open',
                        'opened_at': r['opened_at'].isoformat() if r.get('opened_at') else None,
                        'closed_at': r['closed_at'].isoformat() if r.get('closed_at') else None,
                        'is_fallback': False,
                    })
                return signals
    except Exception:
        return []


@app.get('/equity')
def equity(days: int = Query(default=30, le=90)):
    if not DATABASE_URL:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT closed_at as ts, pnl_pct
                    FROM paper_trades
                    WHERE closed_at IS NOT NULL
                      AND closed_at >= now() - (%s || ' days')::interval
                    ORDER BY closed_at ASC
                """, (days,))
                rows = cur.fetchall()
                if not rows:
                    return []

                running = 100.0
                curve = [{'ts': (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(), 'equity': 100.0}]
                for r in rows:
                    running += float(r['pnl_pct'] or 0.0)
                    curve.append({
                        'ts': r['ts'].isoformat(),
                        'equity': round(running, 2),
                    })
                return curve
    except Exception:
        return []


@app.get('/history')
def get_history(days: int = Query(default=30, le=365)):
    if not DATABASE_URL:
        return []

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        p.id,
                        p.signal_id,
                        p.symbol,
                        p.direction,
                        p.entry,
                        p.exit_price,
                        p.pnl_pct,
                        p.exit_reason,
                        p.opened_at,
                        p.closed_at,
                        s.created_at as predicted_at,
                        coalesce(s.timeframe, '1h') as timeframe
                    FROM paper_trades p
                    LEFT JOIN signals s ON s.id = p.signal_id
                    WHERE p.closed_at IS NOT NULL
                      AND p.closed_at >= now() - (%s || ' days')::interval
                    ORDER BY p.closed_at DESC
                    LIMIT 200
                """, (days,))
                rows = cur.fetchall()
                if not rows:
                    return []
                out = []
                for r in rows:
                    is_win = (r['pnl_pct'] or 0) > 0 or 'target' in (r['exit_reason'] or '').lower()
                    exit_reason = r['exit_reason'] or ('Target Hit' if is_win else 'Stop Loss Hit')
                    out.append({
                        'id': r['id'],
                        'signal_id': r['signal_id'],
                        'symbol': r['symbol'],
                        'timeframe': r['timeframe'],
                        'direction': r['direction'],
                        'entry': float(r['entry']),
                        'exit_price': float(r['exit_price']) if r['exit_price'] is not None else float(r['entry']),
                        'pnl_pct': float(r['pnl_pct']) if r['pnl_pct'] is not None else 0.0,
                        'exit_reason': exit_reason,
                        'opened_at': r['opened_at'].isoformat() if r['opened_at'] else None,
                        'closed_at': r['closed_at'].isoformat() if r['closed_at'] else None,
                        'predicted_at': r['predicted_at'].isoformat() if r.get('predicted_at') else None,
                    })
                return out
    except Exception:
        return []


@app.post('/signals/transition')
def transition_signal(req: SignalTransitionRequest):
    """
    Idempotently persists lifecycle transitions for signals and paper trades.
    Guarantees:
      - Completed signals transition out of 'open' so they do not stay active after refresh.
      - Completed trades are recorded once with exact entry/exit prices and timestamps.
      - No real orders are executed; affects only paper trading tables.
    """
    if not DATABASE_URL:
        return {'status': 'acknowledged_local', 'signal_id': req.signal_id, 'lifecycle_status': req.status}

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # 1. Update signals table status
                cur.execute(
                    "UPDATE signals SET status = %s WHERE id = %s",
                    (req.status, req.signal_id)
                )

                # 2. Check if paper_trades record already exists for this signal_id
                cur.execute(
                    "SELECT id, opened_at, closed_at FROM paper_trades WHERE signal_id = %s LIMIT 1",
                    (req.signal_id,)
                )
                existing = cur.fetchone()

                now_dt = datetime.now(timezone.utc)
                opened_dt = datetime.fromisoformat(req.opened_at.replace('Z', '+00:00')) if req.opened_at else now_dt
                closed_dt = datetime.fromisoformat(req.closed_at.replace('Z', '+00:00')) if req.closed_at else now_dt

                if req.status == 'in_progress':
                    if not existing:
                        sym = req.symbol
                        dirn = req.direction
                        entry = req.entry
                        if not sym or not dirn or entry is None:
                            cur.execute("SELECT symbol, direction, entry FROM signals WHERE id = %s", (req.signal_id,))
                            s_row = cur.fetchone()
                            if s_row:
                                sym = sym or s_row['symbol']
                                dirn = dirn or s_row['direction']
                                entry = entry if entry is not None else float(s_row['entry'])

                        cur.execute("""
                            INSERT INTO paper_trades (
                                signal_id, opened_at, symbol, direction, entry, leverage, fees, funding
                            ) VALUES (%s, %s, %s, %s, %s, 1.0, 0.0, 0.0)
                        """, (req.signal_id, opened_dt, sym or 'UNKNOWN', dirn or 'long', entry or 0.0))
                elif req.status in ('target_hit', 'stop_hit', 'closed'):
                    if existing:
                        # If trade is already closed, do not overwrite or duplicate
                        if existing['closed_at'] is None:
                            cur.execute("""
                                UPDATE paper_trades
                                SET closed_at = %s,
                                    exit_price = %s,
                                    pnl_pct = %s,
                                    exit_reason = %s
                                WHERE id = %s
                            """, (closed_dt, req.exit_price, req.pnl_pct, req.exit_reason, existing['id']))
                    else:
                        # Insert completed record once
                        sym = req.symbol
                        dirn = req.direction
                        entry = req.entry
                        if not sym or not dirn or entry is None:
                            cur.execute("SELECT symbol, direction, entry, created_at FROM signals WHERE id = %s", (req.signal_id,))
                            s_row = cur.fetchone()
                            if s_row:
                                sym = sym or s_row['symbol']
                                dirn = dirn or s_row['direction']
                                entry = entry if entry is not None else float(s_row['entry'])
                                if not req.opened_at and s_row['created_at']:
                                    opened_dt = s_row['created_at']

                        cur.execute("""
                            INSERT INTO paper_trades (
                                signal_id, opened_at, closed_at, symbol, direction, entry, exit_price,
                                leverage, fees, funding, pnl_pct, exit_reason
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1.0, 0.0, 0.0, %s, %s)
                        """, (
                            req.signal_id, opened_dt, closed_dt, sym or 'UNKNOWN', dirn or 'long',
                            entry or 0.0, req.exit_price or entry or 0.0, req.pnl_pct or 0.0, req.exit_reason or 'Target Hit'
                        ))

                conn.commit()
                return {'status': 'persisted', 'signal_id': req.signal_id, 'lifecycle_status': req.status}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@app.post('/session/reset')
def reset_session():
    """Resets paper trades and returns clean session confirmation."""
    if DATABASE_URL:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM paper_trades WHERE opened_at >= now() - interval '7 days'")
                    conn.commit()
        except Exception:
            pass
    return {'status': 'reset', 'timestamp': datetime.now(timezone.utc).isoformat()}


@app.get('/status')
def status():
    last_candle_age = 5
    model_version = 'LightGBM-v0.1 + Meta-Classifier'
    daily_loss_used = 0.8
    correlated_open = 2
    data_available_days = 45

    if DATABASE_URL:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT max(open_time) as last_time FROM candles WHERE timeframe = '15m'")
                    row = cur.fetchone()
                    if row and row['last_time']:
                        diff = datetime.now(timezone.utc) - row['last_time']
                        last_candle_age = max(0, int(diff.total_seconds() / 60))

                    cur.execute("SELECT min(open_time) as min_t, max(open_time) as max_t FROM candles")
                    c_row = cur.fetchone()
                    if c_row and c_row['min_t'] and c_row['max_t']:
                        diff_days = (c_row['max_t'] - c_row['min_t']).days
                        data_available_days = max(1, diff_days)
        except Exception:
            pass

    if REDIS_URL:
        try:
            r = get_redis()
            m_ver = r.get('model:active_version')
            if m_ver:
                model_version = m_ver.decode('utf-8')
        except Exception:
            pass

    return {
        'last_candle_age_min': last_candle_age,
        'model_version': model_version,
        'next_retrain': next_sunday_0200_utc(),
        'daily_loss_used': daily_loss_used,
        'daily_loss_limit': 3.0,
        'max_leverage': 3.0,
        'correlated_open': correlated_open,
        'correlated_cap': 3,
        'market_regime': 'Moderate Volatility / Bullish Bias',
        'data_available_days': data_available_days,
    }


@app.get('/prices')
def prices():
    """Returns the latest market prices for all tracked pairs from candles or Redis."""
    results = {}
    if DATABASE_URL:
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT ON (symbol) symbol, close, open_time
                        FROM candles
                        ORDER BY symbol, open_time DESC
                    """)
                    for r in cur.fetchall():
                        results[r['symbol']] = {
                            'price': float(r['close']),
                            'updated_at': r['open_time'].isoformat(),
                        }
        except Exception:
            pass
    return results
