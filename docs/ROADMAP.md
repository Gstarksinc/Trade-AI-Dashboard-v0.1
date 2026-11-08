# Roadmap

## Phase 1: build and test

1. **Infrastructure** (done): Compose stack, schema, API health, dashboard shell.
2. **Collector:** backfill 2-3 years of 15m/1h/4h klines and funding; start recording open interest, long/short ratio, taker volume and live streams immediately.
3. **Universe:** top coins from CoinGecko intersected with Binance USDT perpetuals; exclude stablecoins and wrapped tokens. Start with 5-30 liquid symbols.
4. **Features and labels:** build the dataset, triple-barrier labels, check for leakage.
5. **LightGBM baseline and walk-forward backtest** including all costs. If there is no edge after costs, fix features and labels before adding anything else.
6. **Meta-labeling and risk engine.**
7. **API endpoints** from `docs/DASHBOARD_API.md`, then Telegram notifier.
8. **Paper trade for 2-3 months.**

## Phase 2: only after the baseline is validated

- FinBERT or CryptoBERT sentiment, if it improves out-of-sample results.
- A second, different model (LSTM/TCN or logistic regression) for diversity.
- Order book and liquidation features; regime filter (HMM).
- Prometheus, Grafana and MLflow; drift monitoring.
- Widen the universe toward 50-100 coins if results hold.

## Pass/fail criteria

- Out-of-sample directional accuracy of 52-58% is realistic; consistently above 65% almost always means leakage.
- Positive expectancy after fees, slippage and funding.
- Stable results across months and coins, not one lucky period.
- A maximum drawdown you could tolerate in real money.
