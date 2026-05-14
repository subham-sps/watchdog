# Watchdog Project — Prompt Audit Log

---

## Turn 1 — 2026-05-14 (Session Start)

**Prompt:**
> Lead Architect mode: ON. We are building a Python-based, API-first Intelligent Observability & Event Watchdog using a postgres database and a dashboard.
> Rules:
> • No Manual Edits: You provide all logic and fixes. I will not edit any code.
> • Audit Log: You must maintain a file named prompts.md. After every turn, update that file (or provide the text block) with the prompt I just used.
> • Time-Check: Start a timer. Goal is an MVP in 4-6 hours (Max window: 16h). Report 'Elapsed Time' at the end of every response. Acknowledge and let's start.

**Action:** Project initialized. CLAUDE.md, README, .env.example, Dockerfile, docker-compose scaffold created.

---

## Turn 2 — 2026-05-14

**Prompt:**
> Please analyze this codebase and create a CLAUDE.md file...

**Action:** CLAUDE.md created with commands, architecture table, data flow, anomaly detection description, and env var reference.

---

## Turn 3 — 2026-05-14

**Prompt:**
> lets plan the project first and discuss on it, here are my thoughts.
> I'm building an "Observability Watchdog" — a Python FastAPI app that ingests logs, detects error spikes using z-scores, fires webhook alerts, and shows a live dashboard. Fully containerized with Postgres.
> I am thinking five services as of now : postgres, api, anomaly-worker, log-generator with profile, webhook-receiver.

**Action:** Architecture discussed. Five-service split confirmed. Anomaly worker writes directly to Postgres (shared DB, no HTTP coupling).

---

## Turn 4 — 2026-05-14

**Prompt:**
> the anomaly-worker writes directly to postgres

**Action:** Confirmed. Data ownership table finalized. Z-score strategy discussed — rolling window global + per-source proposed.

---

## Turn 5 — 2026-05-14

**Prompt:**
> go with rolling window, global + per-source for now for z-score for the whole system

**Action:** Z-score strategy locked. Build order proposed (6 services + docker-compose). Awaiting confirmation to build.

---

## Turn 6 — 2026-05-14

**Prompt:**
> before you proceed, whats your plan?

**Action:** Detailed plan presented: all files, test coverage, key decisions (UUIDs, client-supplied occurred_at, fingerprint field, get_or_create source, SQLite for tests).

---

## Turn 7 — 2026-05-14

**Prompt:**
> implement these three changes before you execute:
> - Drop SQLite for tests. Just use a watchdog_test database on the same Postgres container you already have.
> - Remove lifespan table creation. You have Alembic - use it.
> - Add a unique constraint on Source.name so the 409 for duplicates is enforced at the DB level.

**Action:** All three changes acknowledged and incorporated into plan. Rationale confirmed for each.

---

## Turn 8 — 2026-05-14

**Prompt:**
> yes, go ahead

**Action:** Full Service 1 (Core + API) built:
- `app/core/`: config, database, security
- `app/models/`: Source (UniqueConstraint on name), Event, Alert
- `app/schemas/`: event, alert, metrics
- `app/services/`: event_service, source_service (IntegrityError → 409), alert_service
- `app/api/v1/`: health, sources, events, alerts, metrics, router
- `app/main.py`: FastAPI lifespan (scheduler only, no DDL)
- `alembic/`: env.py (async), script.py.mako, 0001_initial_schema migration
- `tests/`: conftest (watchdog_test Postgres + SAVEPOINT rollback), test_health, test_sources, test_events, test_alerts, test_metrics
- `pytest.ini`: asyncio_mode = auto

---

## Turn 9 — 2026-05-14

**Prompt:**
> [IDE diagnostics: asyncpg, alembic, apscheduler, pytest-asyncio not installed]

**Action:** `pip install -r requirements.txt` executed. All packages installed successfully.

---

## Turn 10 — 2026-05-14

**Prompt:**
> lets test this first before proceeding to 2nd service. create a postgres db container and test it

**Action:**
- Docker Desktop started. Port 5432 conflict found (mythoplay-db from another project).
- Chose Option B: watchdog Postgres on port 5433 to avoid touching other projects.
- Updated docker-compose.yml, .env, .env.example, alembic.ini, config.py to use port 5433.
- Created `.env`, started `watchdog-db-1` container, created `watchdog_test` DB.
- Ran `alembic upgrade head` on both `watchdog` and `watchdog_test`.
- Three conftest iterations to fix: (1) raw SAVEPOINT SQL conflicting with asyncpg manually-started transactions, (2) cross-event-loop "Future attached to different loop" caused by module-level engine shared across per-test function-scoped event loops.
- Final fix: per-test function-scoped engine + `join_transaction_mode="create_savepoint"` + `asyncio_default_fixture_loop_scope = function` in pytest.ini.
- Result: **29/29 passed, 0 warnings, 4.72s.**

---
