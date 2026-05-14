# Watchdog — Intelligent Observability & Event Watchdog

A Python-based, API-first observability platform that ingests logs, detects anomalies using z-score analysis, fires webhook alerts, and visualises everything on a live dashboard.

---

## How It Works

Watchdog continuously monitors event streams for statistical anomalies. Rather than relying on fixed rate thresholds ("alert if > 100 errors/min"), it uses **z-score analysis** — comparing the current event rate against a rolling baseline. This means it adapts to your traffic patterns and alerts only when something genuinely unusual is happening.

### The Detection Loop

```
Every ANOMALY_WINDOW_MINUTES:

  1. Count events in the current window
  2. Count events in each of the last ANOMALY_LOOKBACK_WINDOWS windows → baseline
  3. Compute z = (current - mean) / stddev
  4. If z >= ANOMALY_ZSCORE_THRESHOLD  →  fire alert + webhook
  5. If z < 1.5 for 2 consecutive cycles  →  auto-resolve the alert
```

The same calculation runs **globally** (all traffic) and **per-source** (each registered source independently), so a single misbehaving service doesn't get buried by healthy traffic.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Docker Network                                 │
│                                                                         │
│  ┌──────────────┐   POST /events/batch   ┌─────────────────────────┐   │
│  │ log-generator│ ─────────────────────► │                         │   │
│  │              │                        │       api  :8000        │   │
│  │ profiles:    │                        │                         │   │
│  │  normal      │                        │  FastAPI + Jinja2/HTMX  │   │
│  │  burst       │   ◄── REST + HTML ──── │  /api/v1/*              │   │
│  │  spike       │                        │  /dashboard             │   │
│  │  noisy       │                        └──────────┬──────────────┘   │
│  └──────────────┘                                   │                  │
│                                                      │ SQLAlchemy async │
│  ┌──────────────┐   reads events                    ▼                  │
│  │anomaly-worker│ ◄────────────────────  ┌─────────────────────────┐   │
│  │              │                        │                         │   │
│  │ z-score scan │   writes alerts        │   PostgreSQL  :5433     │   │
│  │ every 1 min  │ ──────────────────────►│                         │   │
│  │              │                        │  events                 │   │
│  └──────┬───────┘                        │  sources                │   │
│         │                                │  alerts                 │   │
│         │ POST /hook                     └─────────────────────────┘   │
│         ▼                                                               │
│  ┌──────────────┐                                                       │
│  │  webhook-    │   GET /hooks (server-side fetch by api)               │
│  │  receiver    │ ◄─────────────────────────────────────────────────   │
│  │  :9000       │                                                       │
│  │              │   in-memory ring buffer (last 200 webhooks)           │
│  └──────────────┘                                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
         ▲
         │  Browser (HTMX polling every 10s)
         │  http://localhost:8000/dashboard
```

### Services

| Service | Port | Role |
|---------|------|------|
| `api` | 8000 | FastAPI: event ingestion REST API + Jinja2/HTMX dashboard |
| `db` | 5433 | PostgreSQL — sole source of truth for events, sources, alerts |
| `anomaly-worker` | — | Standalone process: z-score scanner, alert writer, webhook dispatcher |
| `log-generator` | — | Synthetic traffic generator with configurable profiles |
| `webhook-receiver` | 9000 | Lightweight HTTP sink for incoming webhook payloads |

### Data Flow

```
[Client / log-generator]
        │
        │  POST /api/v1/events/batch  (X-API-Key header)
        ▼
[API — event_service.ingest_batch()]
        │
        │  INSERT INTO events
        ▼
[PostgreSQL]
        │
        │  SELECT count(*) per window  (every ANOMALY_WINDOW_MINUTES)
        ▼
[anomaly-worker — scanner.scan()]
        │
        ├─ z-score below threshold  →  check open alerts → auto-resolve if calm
        │
        └─ z-score >= threshold  ────────────────────────────────────────┐
                                                                         │
        ┌────────────────────────────────────────────────────────────────┘
        │
        ├─  INSERT INTO alerts
        │
        └─  POST /hook  (WEBHOOK_TYPE: watchdog | slack | generic)
                │
                ▼
        [webhook-receiver — ring buffer]
                │
                ▼  (server-side fetch by API dashboard partial)
        [Browser dashboard — /dashboard/partials/webhooks]
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| API framework | FastAPI 0.115 + Uvicorn |
| ORM | SQLAlchemy 2.0 (async, asyncpg) |
| Migrations | Alembic |
| Config | pydantic-settings (`.env` file) |
| Scheduler | APScheduler 3.10 (in-process, anomaly worker) |
| Dashboard | Jinja2 + HTMX (server-rendered, no JS framework) |
| Charts | Chart.js 4.4 (CDN) |
| HTTP client | httpx (log-generator + webhook dispatch + server-side fetch) |
| Database | PostgreSQL 15 |
| Tests | pytest + pytest-asyncio, real Postgres (`watchdog_test` DB) |
| Containers | Docker + Docker Compose |

---

## Quick Start

### Prerequisites
- Docker Desktop running
- Python 3.11+ (for running tests locally)

### 1. Start the full stack

```bash
docker-compose up --build
```

This starts all 5 services. On first run it:
- Creates the Postgres database
- Runs Alembic migrations (`alembic upgrade head`)
- Starts the API on port 8000
- Starts the webhook receiver on port 9000
- Starts the anomaly worker (scans every minute)
- Starts the log generator (`burst` profile by default)

### 2. Open the dashboard

```
http://localhost:8000/dashboard
```

The dashboard auto-refreshes every 10 seconds via HTMX.

### 3. Explore the API

Interactive docs available at:
```
http://localhost:8000/docs
```

All API endpoints under `/api/v1/` require the `X-API-Key` header:
```bash
curl -H "X-API-Key: dev-key-1234" http://localhost:8000/api/v1/metrics
```

---

## API Reference

### Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/events` | Ingest a single event |
| `POST` | `/api/v1/events/batch` | Ingest up to 500 events in one request |
| `GET` | `/api/v1/events` | List events (filterable by level, source, time range) |
| `GET` | `/api/v1/events/{id}` | Get a single event |

**Ingest example:**
```bash
curl -X POST http://localhost:8000/api/v1/events/batch \
  -H "X-API-Key: dev-key-1234" \
  -H "Content-Type: application/json" \
  -d '[
    {"level": "error",   "message": "Database connection timeout", "payload": {"host": "db-01"}},
    {"level": "warning", "message": "High memory usage",           "payload": {"host": "web-01", "mem_pct": 87}}
  ]'
```

**Valid levels:** `debug` · `info` · `warning` · `error` · `critical`

### Sources

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/sources` | Register a named source (e.g. "payment-service") |
| `GET` | `/api/v1/sources` | List all sources |

Sources are created automatically by the log generator. When ingesting events you can attach a `source_id` (UUID) to group events by service.

### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/alerts` | List alerts (`?acknowledged=false` for active only) |
| `POST` | `/api/v1/alerts/{id}/acknowledge` | Acknowledge an alert |

### Metrics & Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/metrics` | Total events, last-hour count, by-level breakdown, active alerts, source count |
| `GET` | `/api/v1/health` | Database connectivity check |

---

## Dashboard

The dashboard at `http://localhost:8000/dashboard` has five live panels:

| Panel | Refresh | What it shows |
|-------|---------|---------------|
| **Metrics Bar** | 10s | Total events, last-hour events, active alert count, source count |
| **Event Rate Trend** | 10s | Bar chart of events per window (last N windows), current window highlighted |
| **Z-Score Monitor** | 10s | Current count vs baseline mean/stddev, live z-score bar with threshold marker, per-window history strip |
| **Recent Events** | 10s | Last 50 events with level badge, source name, message |
| **Active Alerts** | 10s | Unacknowledged alerts with one-click Ack button (no page reload via HTMX) |
| **Webhook Log** | 15s | Last 20 webhooks received by the receiver (fetched server-side) |

---

## Configuration

All configuration is via environment variables (or `.env` file). Copy `.env.example` to `.env` to get started.

### Key variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://watchdog:watchdog@localhost:5433/watchdog` | Postgres connection string |
| `BOOTSTRAP_API_KEYS` | `dev-key-1234` | Comma-separated valid API keys |
| `ANOMALY_WINDOW_MINUTES` | `1` | Size of each detection window in minutes |
| `ANOMALY_LOOKBACK_WINDOWS` | `6` | Number of past windows used to build the baseline |
| `ANOMALY_ZSCORE_THRESHOLD` | `1.8` | Z-score value that triggers an alert |
| `ALERT_COOLDOWN_MINUTES` | `1` | Minimum gap between alerts for the same rule+source |
| `WEBHOOK_URL` | `http://webhook-receiver:9000/hook` | Where to POST alert webhooks |
| `WEBHOOK_TYPE` | `watchdog` | Payload format: `watchdog` · `slack` · `generic` |
| `WEBHOOK_RECEIVER_URL` | `http://webhook-receiver:9000` | Used by the dashboard to fetch webhook logs server-side |
| `PROFILE` | `burst` | Log generator profile: `normal` · `burst` · `spike` · `noisy` |

### Tuning for faster alerts (demo / development)

```env
ANOMALY_WINDOW_MINUTES=1
ANOMALY_LOOKBACK_WINDOWS=6
ANOMALY_ZSCORE_THRESHOLD=1.8
ALERT_COOLDOWN_MINUTES=1
PROFILE=burst
```

### Tuning for production-like behaviour

```env
ANOMALY_WINDOW_MINUTES=5
ANOMALY_LOOKBACK_WINDOWS=6
ANOMALY_ZSCORE_THRESHOLD=3.0
ALERT_COOLDOWN_MINUTES=10
PROFILE=normal
```

---

## Log Generator Profiles

The log generator (`PROFILE` env var) simulates different traffic patterns:

| Profile | Rate | Burst behaviour | Best for |
|---------|------|----------------|----------|
| `normal` | 36 events/min | None — flat steady traffic | Building a clean baseline |
| `burst` | 36/min + 8× spikes | Every 3 min, all sources, 45s duration | Recurring alert demo |
| `spike` | 36/min + 20× spike | Once only on `app-server`, then calm | One-shot meltdown demo |
| `noisy` | 360 events/min | None | Stress testing |

Switch profiles at runtime without rebuilding:
```bash
# Edit docker-compose.yml → PROFILE: spike
docker-compose up -d log-generator
```

---

## Webhook Adapters

Set `WEBHOOK_TYPE` on the `anomaly-worker` service to change the outbound payload format:

| Type | Use case | Payload format |
|------|----------|---------------|
| `watchdog` | Internal webhook receiver | Full JSON with z-score, counts, metadata |
| `slack` | Slack Incoming Webhooks | Block Kit message with emoji + context line |
| `generic` | Zapier · Make · n8n · custom | Flat JSON — `title`, `severity`, `text`, `fired_at` |

No code change or rebuild needed — just update the env var and restart the worker.

---

## Running Tests

Tests use a real `watchdog_test` Postgres database (same container, separate DB). Each test wraps DB operations in a transaction that rolls back after the test.

```bash
# Start the DB container first
docker-compose up -d db

# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run a specific service's tests
pytest tests/test_anomaly_scanner.py -v

# Run a single test
pytest tests/test_events.py::test_batch_ingest_events -v
```

**Test DB setup (first time only):**
```bash
# Create the test database
docker exec watchdog-db-1 psql -U watchdog -c "CREATE DATABASE watchdog_test OWNER watchdog;"

# Run migrations on the test DB
DATABASE_URL=postgresql+asyncpg://watchdog:watchdog@localhost:5433/watchdog_test alembic upgrade head
```

**Current test coverage: 120 tests across 9 files — 0 failures.**

---

## Project Structure

```
watchdog/
├── app/                        # FastAPI application
│   ├── api/v1/                 # REST endpoints (events, sources, alerts, metrics, health)
│   ├── core/                   # Config, database engine, API key security
│   ├── dashboard/              # Jinja2 templates, HTMX partials, static CSS
│   ├── models/                 # SQLAlchemy ORM models (Event, Source, Alert)
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/               # Business logic (event_service, alert_service, source_service)
│   └── main.py                 # FastAPI app entrypoint
├── anomaly_worker/             # Standalone anomaly detection process
│   ├── detector.py             # Pure z-score logic (no I/O, fully unit-testable)
│   ├── scanner.py              # DB queries, alert writing, auto-resolution
│   ├── webhook.py              # HTTP dispatch with retry
│   ├── adapters.py             # watchdog / slack / generic payload builders
│   └── main.py                 # APScheduler entry point
├── log_generator/              # Synthetic traffic generator
│   ├── profiles.py             # Traffic profile definitions (normal, burst, spike, noisy)
│   ├── generator.py            # Batch event builder, burst/spike logic
│   └── main.py                 # asyncio entry point
├── webhook_receiver/           # Lightweight webhook sink
│   ├── store.py                # Thread-safe ring buffer (last 200 webhooks)
│   ├── app.py                  # FastAPI: POST /hook, GET /hooks, GET /health
│   └── main.py                 # Uvicorn entry point on port 9000
├── alembic/                    # Database migrations
│   └── versions/0001_initial_schema.py
├── tests/                      # 120 tests across all services
├── docker-compose.yml          # All 5 services
├── Dockerfile                  # Shared image (command override per service)
├── requirements.txt
└── .env.example
```
