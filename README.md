# Crypto Market Data Orchestrator

A production-grade distributed task orchestration system built with Django, Celery, and Redis. Aggregates real-time trading pair metadata and price tickers from multiple cryptocurrency exchanges (Binance, Bybit, Hyperliquid) across spot and futures markets.

## Architecture

```
                         ┌─────────────────┐
                         │   Celery Beat    │
                         │  (Scheduler)     │
                         └────────┬─────────┘
                                  │ every 30s
                                  ▼
┌──────────┐         ┌──────────────────────┐         ┌──────────┐
│  Django   │◄───────►│       Redis          │◄───────►│  Celery  │
│  REST API │         │  (Broker + Backend)  │         │  Worker  │
└──────────┘         └──────────────────────┘         └─────┬────┘
      │                                                      │
      │                                               fan-out (group)
      │                                          ┌───────────┼───────────┐
      ▼                                          ▼           ▼           ▼
┌──────────┐                              ┌──────────┐ ┌──────────┐ ┌────────────┐
│ PostgreSQL│◄────── bulk upsert ─────────│ Binance  │ │  Bybit   │ │Hyperliquid │
│          │                              │ spot +   │ │ spot +   │ │ spot +     │
└──────────┘                              │ futures  │ │ futures  │ │ futures    │
                                          └──────────┘ └──────────┘ └────────────┘
```

## Celery Implementation

### Task Topology

The system uses a **fan-out/fan-in** pattern via Celery `group` primitives to parallelize exchange syncing:

```
sync_all_pairs (periodic, every 30s)
  └── group([
        sync_exchange_pairs("binance", "spot"),
        sync_exchange_pairs("binance", "futures"),
        sync_exchange_pairs("bybit", "spot"),
        sync_exchange_pairs("bybit", "futures"),
        sync_exchange_pairs("hyperliquid", "spot"),
        sync_exchange_pairs("hyperliquid", "futures"),
      ])
```

**`sync_all_pairs`** — Periodic task dispatched by Celery Beat every 30 seconds. Reads the configured exchange+market combos from `settings.PAIR_SYNC_EXCHANGES` and fans out a `group` of `sync_exchange_pairs` subtasks for parallel execution.

**`sync_exchange_pairs(exchange, market)`** — Bound task with automatic retry (max 2 retries, 30s delay). Fetches all trading pairs from a single exchange+market endpoint, then performs a bulk upsert against PostgreSQL:
- New pairs are bulk-inserted
- Status changes (active/inactive) are bulk-updated
- Pairs present in DB but absent from the API response are marked inactive (soft-delete)

### Beat Schedule

```python
app.conf.beat_schedule = {
    "sync-all-pairs-every-30-seconds": {
        "task": "market.tasks.sync_all_pairs",
        "schedule": 30.0,
    },
}
```

### Retry Strategy

```python
@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def sync_exchange_pairs(self, exchange, market):
    ...
    except Exception as exc:
        raise self.retry(exc=exc)
```

Tasks use `bind=True` for access to the task instance, enabling `self.retry()` with exponential backoff semantics. Failed tasks retry up to 2 times with a 30-second delay between attempts.

### Broker & Result Backend

Both the message broker and result backend are backed by Redis, configured via environment variables:

```
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

All task payloads are JSON-serialized — no pickle, no security risk.

### Monitoring

Flower is included for real-time Celery monitoring:
- Task success/failure rates
- Worker status and concurrency
- Task execution time distribution
- Active/reserved/scheduled task queues

Accessible at `http://localhost:5555` when running with Docker Compose.

## Exchange Adapter Pattern

Exchanges are implemented using a **Factory + Strategy** pattern:

```
BaseExchange (ABC)
  ├── BinanceExchange    (spot + futures)
  ├── BybitExchange       (spot + futures)
  └── HyperliquidExchange (spot + futures)

ExchangeFactory.register("binance", BinanceExchange)
ExchangeFactory.create("binance")  →  BinanceExchange()
```

Each adapter implements `process_spot()` and `process_futures()` with exchange-specific API parsing. The base class provides:
- Shared HTTP/2 connection pooling via `httpx`
- Retry with exponential backoff via `tenacity` (3 attempts, 2-10s wait)
- In-memory TTL cache (60s) to avoid redundant API calls

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/market/prices/exchanges/` | List supported exchanges for price data |
| `GET` | `/api/market/prices/ticker/?exchange=binance-spot&symbol=BTC` | Live price ticker with optional symbol filter |
| `GET` | `/api/market/pairs/exchanges/` | List registered exchanges and their markets |
| `GET` | `/api/market/pairs/?exchange=binance&market=spot&status=active` | Fetch pairs from exchange API (live proxy) |
| `GET` | `/api/market/tracked/pairs/?exchange=binance-futures&is_active=true` | Query DB-tracked pairs (populated by Celery) |
| `POST` | `/api/market/tracked/sync/` | Manually trigger a full sync across all exchanges |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | Django 4.2, Django REST Framework |
| Task Queue | Celery 5.6 with Redis broker |
| Scheduler | Celery Beat |
| Monitoring | Flower |
| Database | PostgreSQL 16 |
| HTTP Client | httpx (HTTP/2, connection pooling) |
| Retry | tenacity (exponential backoff) |
| Packaging | uv |
| Containers | Docker, Docker Compose |

## Running Locally

```bash
# Clone and start all services
git clone https://github.com/<your-username>/django-task-orchestrator.git
cd django-task-orchestrator
cp .env.example .env
docker compose up --build
```

This starts 6 containers:

| Service | Port | Purpose |
|---------|------|---------|
| `web` | 8000 | Django API server |
| `celery-worker` | — | Task execution |
| `celery-beat` | — | Periodic task scheduler |
| `flower` | 5555 | Celery dashboard |
| `redis` | 6379 | Message broker + result backend |
| `db` | 5432 | PostgreSQL |

### Without Docker

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver          # terminal 1
uv run celery -A config worker -l info     # terminal 2
uv run celery -A config beat -l info       # terminal 3
uv run celery -A config flower --port=5555 # terminal 4
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://127.0.0.1:6379/0` | Redis broker URL |
| `CELERY_RESULT_BACKEND` | `redis://127.0.0.1:6379/0` | Redis result backend URL |
| `DB_NAME` | — | PostgreSQL database name |
| `DB_USER` | — | PostgreSQL user |
| `DB_PASSWORD` | — | PostgreSQL password |
| `DB_HOST` | — | PostgreSQL host |
| `DB_PORT` | — | PostgreSQL port |
| `ALLOWED_HOSTS` | `*` | Django allowed hosts (comma-separated) |

## License

MIT
