# ADR 003: Unified Alembic Migrations with Schema-per-Domain Architecture

## Status
Accepted

## Context
A microservice architecture often struggles between running separate database migrations per service (risking out-of-order schema dependencies and multiple DB connections) versus a monolithic schema (polluting domain boundaries and table namespaces).

## Decision
Implement a single, authoritative Alembic migration suite in `libs/database/migrations/` that provisions isolated PostgreSQL schemas per domain:
- `market_data`, `feature_store`, `model_registry`, `signals_ledger`, `paper_execution`, `outbox`.
Migrations are executed by a dedicated, one-shot `migrator` container before application services start up.

## Consequences
- **Positive**: Strict domain boundary isolation in PostgreSQL; single versioned migration history; zero migration race conditions across services.
- **Negative**: Schema changes across services must be coordinated through centralized migration scripts.
