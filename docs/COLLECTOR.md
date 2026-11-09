# Collector

Collects public Binance USD-M Futures data into TimescaleDB. No API key is needed or used.

## What it stores

| Table | Source endpoint | History |
|---|---|---|
| `candles` (15m, 1h, 4h) | `/fapi/v1/klines` | `BACKFILL_YEARS` back (default 2), closed candles only |
| `funding_rates` | `/fapi/v1/fundingRate` | `BACKFILL_YEARS` back |
| `open_interest` | `/futures/data/openInterestHist` | about 29 days back, then live |
| `long_short_ratio` | `/futures/data/globalLongShortAccountRatio` | about 29 days back, then live |
| `taker_volume` | `/futures/data/takerlongshortRatio` | about 29 days back, then live |
| `symbols` | `/fapi/v1/exchangeInfo` | listing date, kept for survivorship checks |

Binance serves only about 30 days of open interest, long/short and taker data, so these series start building history from the day you first run the collector. Liquidations and order book data are not collected yet.

## How it runs

1. **Validate:** symbols in `SYMBOLS` that are not tradable USDT perpetuals are dropped with an error in the log.
2. **Backfill:** resumes after the newest stored row, so restarts and repeats are safe and cheap.
3. **Live loop:** every 15 s it stores newly closed candles (5 s after each candle boundary), every 5 min the latest open interest, long/short and taker values, every hour the latest funding rates, and every hour a gap-fill pass for candles missed during outages.
4. **Heartbeat:** Redis keys `collector:heartbeat` (every loop) and hash `collector:last_candle` (newest candle per `SYMBOL:timeframe`) feed the dashboard and notifier.

Requests retry with backoff, honor `Retry-After` on HTTP 429/418, and pause when the used request weight gets high. HTTP 403/451 is reported as a region or IP block.

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `SYMBOLS` | BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT | Coins to collect |
| `TIMEFRAMES` | 15m,1h,4h | Candle timeframes, also used as the metric periods |
| `BACKFILL_YEARS` | 2 | Candle and funding history to fetch |

These are optional: the defaults apply if they are missing from `.env`.

## Run it

Binance access must work from the server first (`curl -s -o /dev/null -w '%{http_code}' https://fapi.binance.com/fapi/v1/ping` prints 200).

```bash
cd /opt/signals
docker compose up -d                                   # db, redis, api must be healthy
docker compose --profile full build collector
docker compose --profile full run --rm collector python -m collector.main --backfill-only
docker compose --profile full up -d collector          # live collection
docker compose logs -f --tail=50 collector
```

Only start the `collector` service by name. The `notifier` service has no code yet and would restart in a loop.

## Verify

```bash
docker compose exec db psql -U signals -d signals -c "SELECT symbol, timeframe, count(*), min(open_time), max(open_time) FROM candles GROUP BY 1,2 ORDER BY 1,2;"
docker compose exec db psql -U signals -d signals -c "SELECT symbol, count(*), max(funding_time) FROM funding_rates GROUP BY 1;"
docker compose exec db psql -U signals -d signals -c "SELECT symbol, period, count(*), max(ts) FROM open_interest GROUP BY 1,2 ORDER BY 1,2;"
source .env && docker compose exec redis redis-cli -a $REDIS_PASSWORD hgetall collector:last_candle
```

Expect about 70,000 15m candles per symbol for 2 years, each timeframe's newest `open_time` within one candle of now, and a Redis heartbeat that keeps updating.

## Data quality check for gaps

```sql
-- 15m candles missing between the first and last stored candle (should be 0)
SELECT symbol, (extract(epoch FROM max(open_time) - min(open_time)) / 900)::int + 1 - count(*) AS missing
FROM candles WHERE timeframe = '15m' GROUP BY symbol;
```

## Tests

```bash
docker compose run --rm api python -m unittest discover -s tests
```

The tests cover candle parsing (forming candles are skipped), timeframe alignment, empty funding mark prices and backfill pagination against a fake exchange. They do not call Binance.
