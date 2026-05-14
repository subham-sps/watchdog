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

## Turn 11 — 2026-05-14

**Prompt:**
> Show me your plan for anomaly worker, while I review it you can initialize the github repo and create a github repo named 'watchdog', commit the changes before proceeding.

**Action:** Plan presented. Git repo initialized, initial commit `1d0ed0a` created (46 files, 1564 insertions). GitHub CLI not installed — winget install triggered in background. Remote set to `https://github.com/subham-sps/watchdog.git`.

---

## Turn 12 — 2026-05-14

**Prompt:**
> I am going to push manually, now lets go back to the plan. Concerns:
> - Add auto-resolution (z < 1.5 for 2 consecutive cycles)
> - Minimum baseline to 4 windows
> - Share one Dockerfile (same image, different command in compose)

**Action:** All three changes incorporated into plan. Confirmed and discussed.

---

## Turn 16 — 2026-05-14

**Prompt:**
> show me the plan for log generator now

**Action:** Plan presented with full file list, profile schema, generator logic, docker-compose addition, and 9 planned tests.

---

## Turn 22 — 2026-05-14

**Prompt:**
> show me the plan for the dashboard service please

**Action:** Plan presented: Jinja2+HTMX, 5 partials, trend graph, server-side webhook fetch, Chart.js CDN.

---

## Turn 23 — 2026-05-14

**Prompt:**
> add a trend graph, i like to visualize. The webhook log partial needs to fetch from webhook-receiver:9000 inside the API container using httpx.

**Action:** Both additions incorporated into plan.

---

## Turn 24 — 2026-05-14

**Prompt:**
> lets proceed

**Action:** Full Service 5 (Dashboard) built — see Turn 24 entry for detail.

---

## Turn 25 — 2026-05-14

**Prompt:** lets start the complete stack and test it now

**Action:** Full stack started via docker-compose. All 5 containers healthy. Smoke tests passed across all endpoints. Dashboard confirmed live at localhost:8000/dashboard.

---

## Turn 26 — 2026-05-14

**Prompt:** in the dashboard i see that the source is not getting populated

**Action:** Fixed three issues: generator was sending source_id=null (never wired up source registration), dashboard showed raw UUID not name, network errors incorrectly cached as null blocking retries. Added source registration at startup, selectinload on list_events, template uses event.source.name.

---

## Turn 27 — 2026-05-14

**Prompt:** i dont see any alerts, its been 15mins almost

**Action:** Root cause: ANOMALY_WINDOW_MINUTES=5 + LOOKBACK=6 required 35 min of history. Burst profile fires every 3 min inside the 6-min baseline so mean is always elevated. Fixed: window=1m, threshold=2.5, cooldown=3m. Manually injected 800 events → alert fired (z=13.43, current=839, mean=102.5). Full alert+webhook chain confirmed.

---

## Turn 28–32 — 2026-05-14

**Prompts:** Baseline/burst traffic analysis → PROFILE=normal → 10-window revert → threshold=1.8, cooldown=1m, PROFILE=burst for frequent alerts. Z-Score Monitor panel added to dashboard showing current count, baseline mean, stddev, live z-score bar, threshold marker, history strip. 120/120 tests passing.

---

## Turn 33 — 2026-05-14

**Prompt:** update the readme.md with more information regarding how the application works, its architecture diagram and the flow for the end user on how to interact with the app

**Action:** README completely rewritten with: how-it-works narrative, ASCII architecture diagram, full data flow diagram, stack table, quick start guide, complete API reference with curl examples, dashboard panel descriptions, all configuration variables, profile comparison table, webhook adapter guide, test instructions, and full project structure. — 115/115 passing, 0 warnings:
- `config.py`: webhook_receiver_url added
- `style.css`: dark theme, metrics grid, badges, trend wrap, table styling
- Templates: base.html (HTMX + Chart.js CDN), dashboard.html, metrics/trend/events/alerts/webhooks partials
- `router.py`: full page + 5 partials + ack endpoint; trend queries same windows as anomaly worker; webhooks partial fetches server-side via httpx with graceful fallback
- `main.py`: StaticFiles mount + dashboard router
- 15 dashboard tests covering all partials, trend data shape, server-side fetch mock, receiver-down graceful degradation
- Fixed Starlette TemplateResponse deprecation (request as first param)
- Result: **115/115 passed, 0 warnings, 7.80s**

---

## Turn 17 — 2026-05-14

**Prompt:**
> lets send events in batches... during a spike, only one source can melt down while the others stay calm... add a burst_once flag.

**Action:** Three changes incorporated into plan: batch endpoint, spike_source targeting, burst_once latch.

---

## Turn 19 — 2026-05-14

**Prompt:**
> show me the plan for webhook receiver now

**Action:** Plan presented. Discussion led to adapter pattern question.

---

## Turn 20 — 2026-05-14

**Prompt:**
> if the webhook receiver was a slack or some other webhook would that be supported too?

**Action:** Proposed adapter pattern: WEBHOOK_TYPE env var selects watchdog | slack | generic format. Plan updated.

---

## Turn 21 — 2026-05-14

**Prompt:**
> lets build it, the plan looks solid now

**Action:** Full Service 4 (Webhook Receiver + Adapters) built — first run, zero failures:
- `app/core/config.py`: webhook_type field added
- `anomaly_worker/adapters.py`: watchdog, slack (Block Kit), generic adapters
- `anomaly_worker/webhook.py`: picks adapter by WEBHOOK_TYPE, falls back gracefully
- `webhook_receiver/store.py`: thread-safe deque ring buffer (maxlen=200)
- `webhook_receiver/app.py`: POST /hook (202), GET /hooks, GET /hooks/{id}, GET /health
- `webhook_receiver/main.py`: uvicorn entry point on port 9000
- `docker-compose.yml`: webhook-receiver service + WEBHOOK_TYPE=watchdog on anomaly-worker
- 15 adapter tests + 13 receiver tests (28 new)
- Result: **100/100 passed, 4.42s**

---

## Turn 18 — 2026-05-14

**Prompt:**
> yes..the plan looks good now..lets cook

**Action:** Full Service 3 (Log Generator) built and tested — first run, zero failures:
- `POST /api/v1/events/batch` endpoint + `ingest_batch` service method (6 new API tests)
- `log_generator/profiles.py`: Profile dataclass with spike_source, burst_once, validation
- `log_generator/generator.py`: batch collection, stochastic rounding, targeted source, burst_once latch
- `log_generator/main.py`: asyncio entry point, PROFILE env var
- `docker-compose.yml`: log-generator service (shared image, command override)
- 20 unit tests (no DB, httpx mocked)
- Result: **72/72 passed, 4.11s**

---

## Turn 13 — 2026-05-14

**Prompt:**
> make it a public repo

**Action:** GitHub CLI installed via winget. Auth required interactively — user to push manually.

---

## Turn 14 — 2026-05-14

**Prompt:**
> [gh CLI installed notification + auto mode] yes go ahead

**Action:** Full Service 2 (Anomaly Worker) built and tested:
- `anomaly_worker/detector.py`: pure z-score, MIN_BASELINE=4, stddev=0 guard
- `anomaly_worker/scanner.py`: DB queries, global + per-source scan, cooldown, auto-resolve (2 consecutive low cycles)
- `anomaly_worker/webhook.py`: httpx POST with 1 retry, non-fatal failures
- `anomaly_worker/main.py`: APScheduler entry point, standalone process
- `docker-compose.yml`: anomaly-worker service using shared Dockerfile (command override)
- 11 detector unit tests + 7 scanner integration tests
- Fixed: zero-stddev baseline (all-equal counts), int() truncation in threshold test, auto-resolve test redesigned to pre-create alert (can't advance real time in tests)
- Result: **47/47 passed, 6.26s**

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
