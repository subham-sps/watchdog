# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Rules

- **No Manual Edits:** All code is provided and maintained exclusively by Claude. The human operator will not edit files directly.
- **Audit Log:** Every turn must append the user's prompt to `prompts.md` with a turn number and timestamp.
- **Elapsed Time:** Report elapsed session time at the end of every response (session started 2026-05-14).

## Commands

### Setup
```bash
# Start PostgreSQL only
docker-compose up -d db

# Install Python dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start dev server (hot reload)
uvicorn app.main:app --reload --port 8000
```

### Full stack via Docker
```bash
docker-compose up --build
```

### Database migrations
```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "describe change"

# Apply migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

### Tests
```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_events.py

# Run a single test by name
pytest tests/test_events.py::test_ingest_event -v
```

## Architecture

**Stack:** FastAPI + SQLAlchemy (async, asyncpg) + PostgreSQL + Jinja2/HTMX dashboard. Auth via `X-API-Key` header.

### Key layers

| Layer | Path | Role |
|-------|------|------|
| Config | `app/core/config.py` | `Settings` (pydantic-settings), reads `.env`. Single `settings` singleton. |
| Database | `app/core/database.py` | Async SQLAlchemy engine, `AsyncSessionLocal`, `Base`, `get_db()` dependency. |
| Security | `app/core/security.py` | `require_api_key` FastAPI dependency — validates against `settings.api_keys`. |
| Models | `app/models/` | SQLAlchemy ORM: `Source`, `Event`, `Alert`. UUIDs as PKs. |
| Schemas | `app/schemas/` | Pydantic v2 I/O contracts. `EventCreate`/`EventRead`, `AlertRead`, `MetricsSummary`. |
| Services | `app/services/` | Business logic (event ingestion, anomaly detection, alert creation). |
| API | `app/api/` | FastAPI routers, mounted under `/api/v1`. |
| Tasks | `app/tasks/` | APScheduler background jobs (anomaly scan, alert cleanup). |
| Dashboard | `app/dashboard/` | Jinja2 templates + static assets, served at `/dashboard`. |

### Data flow

1. Client POSTs to `/api/v1/events` with `X-API-Key` header.
2. `require_api_key` dependency validates the key.
3. Router calls `EventService.ingest(db, payload)` which writes to `events` table.
4. APScheduler job runs every N minutes, calls `AnomalyService.scan(db)`.
5. If a spike is detected, `AlertService.create(db, ...)` writes to `alerts` table.
6. Dashboard polls `/api/v1/metrics` and `/api/v1/alerts` via HTMX for live updates.

### Anomaly detection logic

Spike detection compares the event count in the last `ANOMALY_WINDOW_MINUTES` against the rolling average of the preceding windows. If the ratio exceeds `ANOMALY_SPIKE_MULTIPLIER`, an alert fires. Alerts are suppressed during the `ALERT_COOLDOWN_MINUTES` window to prevent flooding (implemented in `app/services/anomaly.py`).

### Environment variables

All config lives in `.env` / environment. See `.env.example` for the full list. Key ones:
- `DATABASE_URL` — asyncpg connection string
- `BOOTSTRAP_API_KEYS` — comma-separated valid API keys
- `ANOMALY_WINDOW_MINUTES`, `ANOMALY_SPIKE_MULTIPLIER`, `ALERT_COOLDOWN_MINUTES` — tuning knobs
