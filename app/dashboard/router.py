"""
Dashboard router — server-rendered pages + HTMX partials.

All routes are unauthenticated (internal tool).
The /partials/webhooks endpoint fetches from webhook-receiver server-side
because the browser cannot resolve Docker-internal hostnames directly.
"""
from __future__ import annotations

import uuid as _uuid
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.event import Event
from app.models.alert import Alert
from app.services import alert_service, event_service

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Custom filter so templates can format large numbers
templates.env.filters["format_number"] = lambda v: f"{v:,}"

dashboard_router = APIRouter(prefix="/dashboard")

_WEBHOOK_TIMEOUT = httpx.Timeout(3.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _window_bounds(index: int, now: datetime) -> tuple[datetime, datetime]:
    w = settings.anomaly_window_minutes
    end = now - timedelta(minutes=index * w)
    start = end - timedelta(minutes=w)
    return start, end


async def _event_count_for_window(db: AsyncSession, start: datetime, end: datetime) -> int:
    result = await db.execute(
        __import__("sqlalchemy").select(func.count(Event.id)).where(
            and_(Event.occurred_at >= start, Event.occurred_at < end)
        )
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Full page
# ---------------------------------------------------------------------------

@dashboard_router.get("", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {
        "refresh_seconds": settings.dashboard_refresh_seconds,
        "window_minutes": settings.anomaly_window_minutes,
        "lookback_windows": settings.anomaly_lookback_windows,
    })


# ---------------------------------------------------------------------------
# Partials
# ---------------------------------------------------------------------------

@dashboard_router.get("/partials/metrics", response_class=HTMLResponse)
async def partial_metrics(request: Request, db: AsyncSession = Depends(get_db)):
    metrics = await alert_service.get_metrics(db)
    return templates.TemplateResponse(request, "partials/metrics.html", {
        "metrics": metrics,
    })


@dashboard_router.get("/partials/trend", response_class=HTMLResponse)
async def partial_trend(request: Request, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    n = settings.anomaly_lookback_windows + 1   # include current window
    counts = []
    labels = []

    for i in range(n - 1, -1, -1):             # oldest → newest
        start, end = _window_bounds(i, now)
        count = await _event_count_for_window(db, start, end)
        counts.append(count)
        if i == 0:
            labels.append("now")
        else:
            ago = i * settings.anomaly_window_minutes
            labels.append(f"-{ago}m")

    # Colour current window differently so it stands out
    colors = ["rgba(99,102,241,0.6)"] * (n - 1) + ["rgba(99,102,241,1.0)"]

    return templates.TemplateResponse(request, "partials/trend.html", {
        "labels": labels,
        "counts": counts,
        "colors": colors,
        "chart_id": str(_uuid.uuid4())[:8],     # unique id avoids canvas reuse conflicts
    })


@dashboard_router.get("/partials/events", response_class=HTMLResponse)
async def partial_events(request: Request, db: AsyncSession = Depends(get_db)):
    events = await event_service.list_events(db, limit=50)
    return templates.TemplateResponse(request, "partials/events.html", {
        "events": events,
    })


@dashboard_router.get("/partials/alerts", response_class=HTMLResponse)
async def partial_alerts(request: Request, db: AsyncSession = Depends(get_db)):
    alerts = await alert_service.list_alerts(db, acknowledged=False, limit=50)
    return templates.TemplateResponse(request, "partials/alerts.html", {
        "alerts": alerts,
    })


@dashboard_router.get("/partials/webhooks", response_class=HTMLResponse)
async def partial_webhooks(request: Request):
    """
    Fetches webhook entries from the receiver server-side.
    The browser cannot reach Docker-internal hostnames directly.
    Returns a graceful fallback fragment if the receiver is down.
    """
    try:
        async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
            resp = await client.get(f"{settings.webhook_receiver_url}/hooks?limit=20")
            hooks = resp.json() if resp.status_code == 200 else []
        return templates.TemplateResponse(request, "partials/webhooks.html", {
            "hooks": hooks,
            "unavailable": False,
            "error": None,
        })
    except httpx.RequestError as exc:
        return templates.TemplateResponse(request, "partials/webhooks.html", {
            "hooks": [],
            "unavailable": True,
            "error": str(exc),
        })


# ---------------------------------------------------------------------------
# Acknowledge alert (returns refreshed alerts partial for HTMX swap)
# ---------------------------------------------------------------------------

@dashboard_router.post("/alerts/{alert_id}/acknowledge", response_class=HTMLResponse)
async def ack_alert(request: Request, alert_id: _uuid.UUID, db: AsyncSession = Depends(get_db)):
    await alert_service.acknowledge_alert(db, alert_id)
    alerts = await alert_service.list_alerts(db, acknowledged=False, limit=50)
    return templates.TemplateResponse(request, "partials/alerts.html", {
        "alerts": alerts,
    })
