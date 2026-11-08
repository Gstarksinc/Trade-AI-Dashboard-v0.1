# Trade AI Dashboard v0.1

A self-hosted crypto futures signal system and dashboard: Binance Futures market data, a LightGBM prediction model with meta-labeling, risk-managed entry/stop/target levels, a Next.js dashboard and Telegram alerts. **Paper trading only. It does not place orders.**

> Engineering project, not financial advice. Leveraged futures can lose money quickly. Validate with at least 2-3 months of forward paper trading before relying on any signal.

## Status

| Area | State |
|---|---|
| Docker Compose stack (TimescaleDB, Redis, FastAPI) | Done |
| Database schema (6 hypertables, signals, paper trades) | Done |
| API `/health` | Done |
| Next.js dashboard (live health, sample data until API endpoints exist) | Done |
| API endpoints `/summary`, `/signals`, `/equity`, `/status` | Planned |
| Collector (Binance backfill and live streams) | Planned |
| Features, labeling, models, backtest, risk engine | Planned |
| Telegram notifier | Planned |

See [docs/ROADMAP.md](docs/ROADMAP.md) for the build order.

## Stack

| Layer | Choice |
|---|---|
| Language / API | Python 3.11, FastAPI |
| Market data | Binance Futures public API, data.binance.vision bulk files |
| Universe ranking | CoinGecko Demo API (daily) |
| Indicators | TA-Lib |
| Model | LightGBM (calibrated) plus a meta-labeling classifier |
| Sentiment | FinBERT or CryptoBERT (Phase 2, only if it helps out-of-sample) |
| Database / cache | PostgreSQL 16 with TimescaleDB, Redis 7 |
| Dashboard | Next.js 14 |
| Alerts | Telegram Bot API |
| Deployment | Docker Compose on Debian 12/13 |

## Quick start (Debian)

```bash
git clone https://github.com/Gstarksinc/Trade-AI-Dashboard-v0.1.git /opt/signals
cd /opt/signals
bash scripts/gen_env.sh            # creates .env with random passwords
docker compose up -d --build       # db, redis, api
curl -s http://127.0.0.1:8000/health
docker compose --profile full up -d --build dashboard
```

The dashboard listens on `127.0.0.1:3000`. Reach it with an SSH tunnel: `ssh -L 3000:127.0.0.1:3000 user@SERVER_IP`, then open `http://localhost:3000`.

Full machine preparation (users, SSH, firewall, Docker, time sync, backups) is in [docs/SETUP_DEBIAN.md](docs/SETUP_DEBIAN.md).

## Repository layout

```
docker-compose.yml        services and profiles
.env.example              configuration template (copy via scripts/gen_env.sh)
docker/python.Dockerfile  Python image with TA-Lib built from source
db/init/001_schema.sql    TimescaleDB schema (runs on first start of an empty volume)
api/                      FastAPI service
dashboard/                Next.js dashboard
collector/ features/ labeling/ models/ backtest/ risk/ notifier/   planned modules
scripts/                  gen_env.sh, backup.sh
docs/                     setup, architecture, dashboard API contract, roadmap
```

## Docker Compose profiles

| Command | Starts |
|---|---|
| `docker compose up -d` | db, redis, api |
| `docker compose --profile full up -d` | adds collector, notifier, dashboard (once their code exists) |
| `docker compose --profile train run --rm trainer` | one-off training run |

## Documentation

- [Debian setup guide](docs/SETUP_DEBIAN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Dashboard API contract](docs/DASHBOARD_API.md)
- [Roadmap and pass/fail criteria](docs/ROADMAP.md)
