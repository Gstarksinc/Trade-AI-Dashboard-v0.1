# ADR 010: Dashboard as a Strictly Read-Only Gateway Client

## Status
Accepted

## Context
Web dashboards often contain client-side order routing, local localStorage caching of trade state, or direct connections to external exchange APIs. In algorithmic trading systems, this creates security vulnerabilities, split-brain trade states, and unauthorized trade mutations.

## Decision
Architect the Next.js 14 dashboard as a **strictly read-only presentation client**:
1. Zero direct connections to Binance or external crypto APIs.
2. Connects exclusively to internal `api-gateway:8000` via REST and Server-Sent Events (`/events/stream`).
3. Zero mutate endpoints or local state computation; UI renders solely what the backend authoritative state machine dictates.

## Consequences
- **Positive**: Clean separation of concerns; zero risk of client-side order tampering; unified auditability.
- **Negative**: User cannot execute manual discretionary trades from the dashboard UI (which aligns with our 100% automated algorithmic research scope).
