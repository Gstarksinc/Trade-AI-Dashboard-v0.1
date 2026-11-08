CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE symbols (
  symbol          text PRIMARY KEY,
  base_asset      text,
  coingecko_id    text,
  market_cap_rank int,
  is_active       boolean DEFAULT true,
  onboard_date    timestamptz,
  updated_at      timestamptz DEFAULT now()
);

CREATE TABLE candles (
  symbol          text NOT NULL,
  timeframe       text NOT NULL,
  open_time       timestamptz NOT NULL,
  open            double precision,
  high            double precision,
  low             double precision,
  close           double precision,
  volume          double precision,
  quote_volume    double precision,
  trades          int,
  taker_buy_base  double precision,
  taker_buy_quote double precision,
  PRIMARY KEY (symbol, timeframe, open_time)
);
SELECT create_hypertable('candles', 'open_time', chunk_time_interval => INTERVAL '30 days');
ALTER TABLE candles SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol,timeframe', timescaledb.compress_orderby = 'open_time DESC');
SELECT add_compression_policy('candles', INTERVAL '30 days');

CREATE TABLE funding_rates (
  symbol       text NOT NULL,
  funding_time timestamptz NOT NULL,
  funding_rate double precision,
  mark_price   double precision,
  PRIMARY KEY (symbol, funding_time)
);
SELECT create_hypertable('funding_rates', 'funding_time', chunk_time_interval => INTERVAL '90 days');

CREATE TABLE open_interest (
  symbol                text NOT NULL,
  ts                    timestamptz NOT NULL,
  period                text NOT NULL,
  sum_open_interest     double precision,
  sum_open_interest_val double precision,
  PRIMARY KEY (symbol, period, ts)
);
SELECT create_hypertable('open_interest', 'ts', chunk_time_interval => INTERVAL '30 days');

CREATE TABLE long_short_ratio (
  symbol        text NOT NULL,
  ts            timestamptz NOT NULL,
  period        text NOT NULL,
  long_account  double precision,
  short_account double precision,
  ratio         double precision,
  PRIMARY KEY (symbol, period, ts)
);
SELECT create_hypertable('long_short_ratio', 'ts', chunk_time_interval => INTERVAL '30 days');

CREATE TABLE taker_volume (
  symbol         text NOT NULL,
  ts             timestamptz NOT NULL,
  period         text NOT NULL,
  buy_sell_ratio double precision,
  buy_vol        double precision,
  sell_vol       double precision,
  PRIMARY KEY (symbol, period, ts)
);
SELECT create_hypertable('taker_volume', 'ts', chunk_time_interval => INTERVAL '30 days');

CREATE TABLE liquidations (
  symbol text NOT NULL,
  ts     timestamptz NOT NULL,
  side   text,
  price  double precision,
  qty    double precision
);
SELECT create_hypertable('liquidations', 'ts', chunk_time_interval => INTERVAL '7 days');

CREATE TABLE news_items (
  id           bigserial PRIMARY KEY,
  published_at timestamptz NOT NULL,
  source       text,
  title        text NOT NULL,
  url          text UNIQUE,
  sentiment    double precision
);

CREATE TABLE signals (
  id               bigserial PRIMARY KEY,
  created_at       timestamptz NOT NULL DEFAULT now(),
  symbol           text NOT NULL,
  timeframe        text NOT NULL,
  direction        text NOT NULL,
  probability      double precision,
  meta_probability double precision,
  entry            double precision,
  stop_loss        double precision,
  take_profit      double precision,
  atr              double precision,
  model_version    text,
  status           text DEFAULT 'open',
  features         jsonb
);
CREATE INDEX ON signals (symbol, created_at DESC);

CREATE TABLE paper_trades (
  id          bigserial PRIMARY KEY,
  signal_id   bigint REFERENCES signals(id),
  opened_at   timestamptz NOT NULL,
  closed_at   timestamptz,
  symbol      text NOT NULL,
  direction   text NOT NULL,
  entry       double precision,
  exit_price  double precision,
  leverage    double precision,
  fees        double precision,
  funding     double precision,
  pnl_pct     double precision,
  exit_reason text
);
