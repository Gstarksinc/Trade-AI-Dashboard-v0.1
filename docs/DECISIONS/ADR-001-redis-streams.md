# ADR 001: Redis Streams with Consumer Groups over Ephemeral Pub/Sub

## Status
Accepted

## Context
In early prototypes, services communicated via Redis Pub/Sub (`PUBLISH`/`SUBSCRIBE`). Under container restarts, network partitions, or consumer slowdowns, messages published to Pub/Sub channels were permanently lost because Pub/Sub provides no persistence, message buffering, or delivery acknowledgements.

## Decision
Adopt **Redis 7 Streams** with persistent consumer groups as the primary asynchronous message bus:
1. Messages are written to bounded streams (`maxlen=10000`).
2. Consumer groups read with `XREADGROUP`, track pending entries, and explicitly acknowledge receipt via `XACK`.
3. Persistent processing errors trigger retries before routing to a Dead-Letter Queue (`system.dlq`).

## Consequences
- **Positive**: Zero message loss across service restarts; independent consumer scaling; dead-letter triage.
- **Negative**: Requires stream length trimming to prevent memory growth (managed via approximate trimming `~ 10000`).
