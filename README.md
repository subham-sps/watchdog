# Watchdog — Intelligent Observability & Event Watchdog

API-first observability platform with event ingestion, anomaly detection, alerting, and a real-time dashboard.

## Stack
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (async), Alembic
- **Database:** PostgreSQL 15+
- **Dashboard:** FastAPI + Jinja2 + HTMX (server-side rendered, no heavy JS framework)
- **Task Queue:** APScheduler (in-process, upgradeable to Celery)
- **Auth:** API key based (header: `X-API-Key`)

## Architecture

```
watchdog/
├── app/
│   ├── api/           # REST endpoints
│   ├── core/          # Config, DB, security
│   ├── models/        # SQLAlchemy ORM models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   ├── tasks/         # Background jobs
│   └── dashboard/     # Jinja2 templates + static
├── alembic/           # DB migrations
├── tests/
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Quick Start

```bash
# 1. Start PostgreSQL
docker-compose up -d db

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Run migrations
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/events` | Ingest a new event |
| GET | `/api/v1/events` | List events (filterable) |
| GET | `/api/v1/events/{id}` | Get event detail |
| GET | `/api/v1/alerts` | List active alerts |
| POST | `/api/v1/alerts/{id}/acknowledge` | Ack an alert |
| GET | `/api/v1/sources` | List event sources |
| POST | `/api/v1/sources` | Register a source |
| GET | `/api/v1/metrics` | Aggregated metrics |
| GET | `/api/v1/health` | Health check |
| GET | `/dashboard` | Web dashboard |

## Environment Variables

See `.env.example` for all configuration options.
