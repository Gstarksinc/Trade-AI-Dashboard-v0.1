import os


def _list(name, default):
    return [x.strip() for x in os.environ.get(name, default).split(',') if x.strip()]


DATABASE_URL = os.environ.get('DATABASE_URL', '')
REDIS_URL = os.environ.get('REDIS_URL', '')
BINANCE_FAPI_URL = os.environ.get('BINANCE_FAPI_URL', 'https://fapi.binance.com').rstrip('/')

# Mutable on purpose: main.py removes symbols that are not tradable USDT perpetuals.
SYMBOLS = [s.upper() for s in _list('SYMBOLS', 'BTCUSDT,ETHUSDT,BNBUSDT,XRPUSDT,SOLUSDT,TRXUSDT,DOGEUSDT,LINKUSDT')]
TIMEFRAMES = _list('TIMEFRAMES', '15m,1h,4h')
BACKFILL_YEARS = float(os.environ.get('BACKFILL_YEARS', '2'))
