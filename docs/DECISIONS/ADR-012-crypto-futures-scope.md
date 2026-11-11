# ADR 012: Crypto-Futures-Only Operational Scope

## Status
Accepted

## Context
Initial project roadmaps contemplated multi-market readiness, including crypto spot, equity options, and foreign exchange. Attempting to build an abstraction layer for equities, forex, and futures simultaneously led to premature generalization and bloated domain models.

## Decision
Constrain the immediate operational scope strictly to **Cryptocurrency Futures** (8 Binance USD-M Perpetual Contracts: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `BNBUSDT`, `XRPUSDT`, `DOGEUSDT`, `LINKUSDT`, `TRXUSDT`).
- All data ingestion, funding rate models, margin calculations, and liquidation safeguards are designed specifically for perpetual futures mechanics.
- Multi-asset expansion is formally deferred to future versions after crypto futures alpha is verified.

## Consequences
- **Positive**: Deep specialization on perpetual futures market microstructure; simplified domain models; precise funding fee accounting.
- **Negative**: Cannot trade spot or traditional asset classes without architectural refactoring.

