# Database Architecture & Domain Data Model

> **Database Engine**: PostgreSQL 16 with TimescaleDB extension enabled.
> **Database Name**: `trade_ai` (with scratch DB `trade_ai_scratch` for isolated restore testing).
> **Migration Engine**: Alembic single runner (`libs/database/migrations/`).

---

## 1. Domain Schema Architecture

The database enforces domain-driven service boundaries across six isolated PostgreSQL schemas:

```
trade_ai
├── market_data        # Raw market feeds, candles, funding rates, open interest
├── feature_store      # Point-in-time causal technical & derivatives indicator matrices
├── model_registry     # Model artifacts, experiment trials, shadow predictions, drift reports
├── signals_ledger     # Authoritative signal state machine with optimistic locking
├── paper_execution    # Paper trades, simulated fills, fees, funding accruals, PnL
└── outbox             # Transactional Outbox pattern for guaranteed event dispatch
```

---

## 2. Entity-Relationship Diagram (Mermaid)

```mermaid
erDiagram
    market_data_symbols {
        text symbol PK
        text base_asset
        boolean is_active
        timestamptz onboard_date
        timestamptz updated_at
    }

    market_data_candles {
        text symbol PK
        text timeframe PK
        timestamptz open_time PK
        timestamptz close_time
        double_precision open
        double_precision high
        double_precision low
        double_precision close
        double_precision volume
        double_precision quote_volume
        int trades_count
        double_precision taker_buy_base
        double_precision taker_buy_quote
        boolean is_closed
    }

    market_data_funding_rates {
        text symbol PK
        timestamptz funding_time PK
        double_precision funding_rate
        double_precision mark_price
    }

    feature_store_features {
        text symbol PK
        text timeframe PK
        timestamptz candle_open_time PK
        text feature_set_version PK
        jsonb features
        timestamptz created_at
    }

    model_registry_models {
        text version PK
        text stage
        text algorithm
        text feature_set_version
        jsonb metrics
        text artifact_path
        timestamptz created_at
    }

    model_registry_experiments {
        bigserial id PK
        text experiment_id UK
        text symbol
        text timeframe
        text model_name
        double_precision prob_threshold
        double_precision meta_threshold
        int holdout_trades
        double_precision holdout_net_ev_pct
        double_precision holdout_sharpe
        double_precision pbo
        double_precision dsr
        text status
        text notes
        timestamptz created_at
    }

    model_registry_shadow_predictions {
        bigserial id PK
        text model_version
        text symbol
        text timeframe
        timestamptz candle_open_time
        text direction
        double_precision probability
        double_precision meta_probability
        double_precision current_price
        timestamptz created_at
    }

    signals_ledger_signals {
        bigserial id PK
        timestamptz candle_open_time
        text symbol
        text timeframe
        text direction
        double_precision probability
        double_precision meta_probability
        double_precision entry
        double_precision stop_loss
        double_precision take_profit
        double_precision atr
        text model_version
        text status
        int version
        timestamptz created_at
    }

    paper_execution_paper_trades {
        bigserial id PK
        bigint signal_id FK
        timestamptz opened_at
        timestamptz closed_at
        text symbol
        text timeframe
        text direction
        double_precision entry
        double_precision exit_price
        double_precision leverage
        double_precision fees
        double_precision funding
        double_precision pnl_pct
        double_precision pnl_usd
        text exit_reason
    }

    outbox_events {
        bigserial id PK
        text event_id UK
        text stream
        text event_type
        text idempotency_key UK
        jsonb payload
        text status
        timestamptz created_at
        timestamptz published_at
    }

    market_data_candles ||--o{ feature_store_features : "produces"
    model_registry_models ||--o{ signals_ledger_signals : "generates"
    signals_ledger_signals ||--o{ paper_execution_paper_trades : "executes"
```

---

## 3. Detailed Schema & Table Specifications

### 1. `market_data` Domain
Owned exclusively by `market-collector`.

#### `market_data.candles` (TimescaleDB Hypertable)
- **Primary Key**: `(symbol, timeframe, open_time)`
- **Chunk Interval**: `INTERVAL '30 days'`
- **Compression**: Enabled. Segmented by `symbol, timeframe`; ordered by `open_time DESC`. Compression policy triggers after 30 days.
- **Index**: `candles_open_time_idx` (`open_time DESC`).

#### `market_data.funding_rates` (TimescaleDB Hypertable)
- **Primary Key**: `(symbol, funding_time)`
- **Chunk Interval**: `INTERVAL '90 days'`
- **Columns**: `symbol` (text), `funding_time` (timestamptz), `funding_rate` (float8), `mark_price` (float8).

#### `market_data.open_interest` (TimescaleDB Hypertable)
- **Primary Key**: `(symbol, timeframe, timestamp)`
- **Chunk Interval**: `INTERVAL '30 days'`

#### `market_data.taker_volume` (TimescaleDB Hypertable)
- **Primary Key**: `(symbol, period, ts)`
- **Chunk Interval**: `INTERVAL '30 days'`

---

### 2. `feature_store` Domain
Owned exclusively by `feature-service`.

#### `feature_store.features` (TimescaleDB Hypertable)
- **Primary Key**: `(symbol, timeframe, candle_open_time, feature_set_version)`
- **Chunk Interval**: `INTERVAL '30 days'`
- **Payload**: `features` (`jsonb`) storing 48 causal point-in-time technical and derivatives indicators.

---

### 3. `model_registry` Domain
Owned jointly by `training-service` and `model-service`.

#### `model_registry.models`
Stores production model promotion status, checksums, and evaluation metrics.
- **Primary Key**: `version` (text) (e.g. `LGBM-V31-BTCUSDT-1h-20261111120000`).
- **Columns**:
  - `stage`: `"champion"` | `"challenger"` | `"retired"`.
  - `algorithm`: `"lightgbm_calibrated_platt"`.
  - `feature_set_version`: `"v1.0.0"`.
  - `metrics`: JSON payload containing holdout metrics, CPCV distributions, PBO, DSR, ECE, and gate decisions.
  - `artifact_path`: Relative filesystem path to serialized joblib bundles.

#### `model_registry.experiments`
Automated quantitative trial registry tracking every parameter grid and threshold search. Provides the ground truth trial count for Bailey & López de Prado's Deflated Sharpe Ratio.
- **Primary Key**: `id` (`bigserial`).
- **Unique Constraint**: `experiment_id` (`text UNIQUE`, e.g. `EXP-209`).
- **Columns**: `symbol`, `timeframe`, `model_name`, `prob_threshold`, `meta_threshold`, `holdout_trades`, `holdout_net_ev_pct`, `holdout_sharpe`, `pbo`, `dsr`, `status`, `notes`.

#### `model_registry.shadow_predictions`
Logs out-of-sample forward predictions for shadow models running in production without capital risk.
- **Primary Key**: `id` (`bigserial`).
- **Unique Constraint**: `uq_shadow_prediction (model_version, symbol, timeframe, candle_open_time)`.

#### `model_registry.drift_reports`
Tracks Population Stability Index (PSI) and Wasserstein distance distribution drift.
- **Primary Key**: `id` (`bigserial`).
- **Foreign Key**: `model_version REFERENCES model_registry.models(version)`.

---

### 4. `signals_ledger` Domain
Owned exclusively by `signal-service`.

#### `signals_ledger.signals`
Server-authoritative signal registry governed by optimistic concurrency control.
- **Primary Key**: `id` (`bigserial`).
- **Unique Constraint**: `uq_signal_instance UNIQUE (symbol, timeframe, candle_open_time, direction)`.
- **Concurrency Control**: `version` (`integer NOT NULL DEFAULT 1`). Every state transition executes an atomic version increment:
  ```sql
  UPDATE signals_ledger.signals
  SET status = :new_status, version = version + 1
  WHERE id = :id AND version = :current_version
  RETURNING version;
  ```
- **Indexes**:
  - `idx_signals_status` (`status, created_at DESC`).
  - `idx_signals_symbol` (`symbol, created_at DESC`).

---

### 5. `paper_execution` Domain
Owned exclusively by `paper-exec-service`.

#### `paper_execution.paper_trades`
Stores simulated order executions, leverage, fee deductions, and realized PnL.
- **Primary Key**: `id` (`bigserial`).
- **Foreign Key**: `signal_id REFERENCES signals_ledger.signals(id)`.
- **Integrity Rule**: Partial unique index guaranteeing that a signal can have at most one active open trade at any time:
  ```sql
  CREATE UNIQUE INDEX one_open_trade_per_signal
  ON paper_execution.paper_trades (signal_id)
  WHERE closed_at IS NULL;
  ```
- **Index**: `idx_trades_closed_at` (`closed_at DESC`).

---

### 6. `outbox` Domain
Provides the **Transactional Outbox Pattern** guaranteeing at-least-once event publication across the distributed system.

#### `outbox.events`
- **Primary Key**: `id` (`bigserial`).
- **Unique Constraints**: `event_id` (`text UNIQUE`), `idempotency_key` (`text UNIQUE`).
- **Index**: `idx_outbox_pending (status, id ASC) WHERE status = 'pending'`.
- **Lifecycle**: Services insert domain rows and outbox records within a single database transaction. An outbox background worker polls `status = 'pending'`, publishes to Redis Streams, and marks `status = 'published'` with `published_at = now()`.

