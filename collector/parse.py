"""Pure parsing helpers (no network or database), so they can be unit tested."""
from datetime import datetime, timezone

TF_MS = {
    '1m': 60_000, '5m': 300_000, '15m': 900_000, '30m': 1_800_000,
    '1h': 3_600_000, '2h': 7_200_000, '4h': 14_400_000, '1d': 86_400_000,
}


def ts(ms):
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def floor_boundary(now_ms, tf):
    """Open time (ms) of the candle that is forming at now_ms."""
    step = TF_MS[tf]
    return (now_ms // step) * step


def candle_rows(symbol, tf, raw, now_ms):
    """Rows for closed candles only; a candle whose close time is still ahead is skipped."""
    rows = []
    for k in raw:
        if int(k[6]) >= now_ms:
            continue
        rows.append((symbol, tf, ts(k[0]), fnum(k[1]), fnum(k[2]), fnum(k[3]), fnum(k[4]),
                     fnum(k[5]), fnum(k[7]), int(k[8]), fnum(k[9]), fnum(k[10])))
    return rows


def funding_rows(symbol, raw):
    return [(symbol, ts(f['fundingTime']), fnum(f.get('fundingRate')), fnum(f.get('markPrice'))) for f in raw]


def _oi(symbol, period, raw):
    return [(symbol, ts(r['timestamp']), period, fnum(r['sumOpenInterest']), fnum(r['sumOpenInterestValue'])) for r in raw]


def _lsr(symbol, period, raw):
    return [(symbol, ts(r['timestamp']), period, fnum(r['longAccount']), fnum(r['shortAccount']), fnum(r['longShortRatio'])) for r in raw]


def _taker(symbol, period, raw):
    return [(symbol, ts(r['timestamp']), period, fnum(r['buySellRatio']), fnum(r['buyVol']), fnum(r['sellVol'])) for r in raw]


METRIC_TABLE = {'oi': 'open_interest', 'lsr': 'long_short_ratio', 'taker': 'taker_volume'}
_METRIC_PARSER = {'oi': _oi, 'lsr': _lsr, 'taker': _taker}


def metric_rows(kind, symbol, period, raw):
    return _METRIC_PARSER[kind](symbol, period, raw)
