# ADR 005: Strict Stop-Loss-First Rule on Same-Bar Ambiguity

## Status
Accepted

## Context
In historical backtesting and live price evaluation, a high-volatility price bar or tick spike can touch or breach both the upper Take Profit barrier and the lower Stop Loss barrier within the same bar period. Assuming Take Profit hit first introduces massive lookahead bias and artificially inflates backtested Sharpe ratios.

## Decision
Mandate a conservative **Stop-Loss-First (SL-First) Disambiguation Rule** across all evaluation engines, labeling functions, and paper execution services:
Whenever both Take Profit and Stop Loss barriers are breached within the same bar or tick range, the system **strictly assumes Stop Loss was hit first**.

## Consequences
- **Positive**: Eliminates optimistic survivorship bias; aligns simulated paper fills with worst-case institutional execution reality.
- **Negative**: Slightly reduces theoretical win rate during extreme high-volatility spikes.
