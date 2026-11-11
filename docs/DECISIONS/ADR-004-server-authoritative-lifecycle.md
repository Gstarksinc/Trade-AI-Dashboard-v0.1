# ADR 004: Server-Authoritative Signal Lifecycle with Optimistic Locking

## Status
Accepted

## Context
Early prototypes allowed client browsers to trigger state transitions via `/api/signals/transition` proxy endpoints. This introduced race conditions, potential client manipulation, and desynchronization between database records and live market reality.

## Decision
Establish a **Server-Authoritative Lifecycle**:
1. All signal state transitions are initiated solely by internal backend services (`risk-service`, `paper-exec-service`, and `signal-service`).
2. Client-side state transition routes were completely excised.
3. Every state transition in `signals_ledger.signals` is guarded by an atomic optimistic lock (`version = version + 1 WHERE id = :id AND version = :current_version`).

## Consequences
- **Positive**: Complete elimination of client-induced state corruption; guaranteed idempotence; zero concurrency race conditions.
- **Negative**: Rejected transitions due to version collisions must be handled cleanly by callers (retried or logged).
