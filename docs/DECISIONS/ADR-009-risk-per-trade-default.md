# ADR 009: 0.5% Fixed-Fractional ATR Risk Sizing & PostgreSQL Advisory Locking

## Status
Accepted

## Context
High leverage and static lot sizing cause rapid portfolio ruin in volatile cryptocurrency markets. Furthermore, concurrent evaluations across multiple pairs can inadvertently over-allocate portfolio margin.

## Decision
1. Standardize on **Fixed-Fractional Volatility Risk Sizing**: Every trade risks exactly **0.5% of account equity** (`0.005`) to the $1.0\times\text{ATR}$ stop distance.
2. Hard-cap leverage at **3.0x**.
3. Enforce a PostgreSQL transaction-level advisory lock (`SELECT pg_advisory_xact_lock(888888);`) in `risk-service` so that margin availability, portfolio exposure caps ($\le 100\%$), and cluster caps ($\le 30\%$) are checked and reserved atomically.

## Consequences
- **Positive**: Strict risk bounds; zero margin race conditions across pairs; asymptotic ruin probability minimized.
- **Negative**: Serializes concurrent risk transactions by a few milliseconds.
