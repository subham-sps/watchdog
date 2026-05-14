"""
Dashboard tests.
Uses the existing `client` fixture (routes through test DB session).
Dashboard routes are unauthenticated — no auth_headers needed.
Webhook receiver calls are mocked with httpx.
"""
import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.alert import Alert
from app.models.event import Event


# ---------------------------------------------------------------------------
# Full page
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_returns_200(client):
    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Watchdog" in resp.text


@pytest.mark.asyncio
async def test_dashboard_contains_htmx_partials(client):
    resp = await client.get("/dashboard")
    assert "hx-get" in resp.text
    assert "/dashboard/partials/metrics" in resp.text
    assert "/dashboard/partials/trend" in resp.text


# ---------------------------------------------------------------------------
# Metrics partial
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metrics_partial_returns_html(client):
    resp = await client.get("/dashboard/partials/metrics")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_metrics_partial_shows_event_count(client, auth_headers):
    await client.post("/api/v1/events", json={"level": "error", "message": "m"}, headers=auth_headers)
    resp = await client.get("/dashboard/partials/metrics")
    assert "1" in resp.text


@pytest.mark.asyncio
async def test_metrics_partial_shows_active_alerts(client, db_session):
    alert = Alert(
        rule_name="test-rule", severity="warning",
        message="test", acknowledged=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.flush()
    resp = await client.get("/dashboard/partials/metrics")
    assert resp.status_code == 200
    assert "1" in resp.text


# ---------------------------------------------------------------------------
# Trend partial
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trend_partial_returns_canvas(client):
    resp = await client.get("/dashboard/partials/trend")
    assert resp.status_code == 200
    assert "<canvas" in resp.text


@pytest.mark.asyncio
async def test_trend_partial_contains_chart_data(client):
    resp = await client.get("/dashboard/partials/trend")
    assert "new Chart" in resp.text
    assert "labels" in resp.text
    # Data array should be present
    assert "datasets" in resp.text


@pytest.mark.asyncio
async def test_trend_data_length_matches_lookback_plus_one(client):
    from app.core.config import settings
    resp = await client.get("/dashboard/partials/trend")
    # Extract the counts JSON from the rendered HTML
    import re
    match = re.search(r"data:\s*(\[[\d,\s]*\])", resp.text)
    assert match, "Could not find counts data array in trend partial"
    counts = json.loads(match.group(1))
    assert len(counts) == settings.anomaly_lookback_windows + 1


# ---------------------------------------------------------------------------
# Events partial
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_events_partial_returns_html(client):
    resp = await client.get("/dashboard/partials/events")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_events_partial_shows_ingested_event(client, auth_headers):
    await client.post(
        "/api/v1/events",
        json={"level": "critical", "message": "dashboard-test-event"},
        headers=auth_headers,
    )
    resp = await client.get("/dashboard/partials/events")
    assert "dashboard-test-event" in resp.text
    assert "critical" in resp.text


# ---------------------------------------------------------------------------
# Alerts partial
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alerts_partial_returns_html(client):
    resp = await client.get("/dashboard/partials/alerts")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_alerts_partial_shows_unacked_alert(client, db_session):
    alert = Alert(
        rule_name="zscore_spike_global", severity="warning",
        message="Big spike detected", acknowledged=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.flush()
    resp = await client.get("/dashboard/partials/alerts")
    assert "zscore_spike_global" in resp.text
    assert "Ack" in resp.text


@pytest.mark.asyncio
async def test_acknowledge_via_dashboard_returns_updated_fragment(client, db_session, auth_headers):
    alert = Alert(
        rule_name="test-rule", severity="warning",
        message="ack me", acknowledged=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.flush()

    resp = await client.post(f"/dashboard/alerts/{alert.id}/acknowledge")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Alert is now acked so should not appear in active alerts
    assert "ack me" not in resp.text


# ---------------------------------------------------------------------------
# Webhooks partial (server-side fetch)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhooks_partial_fetches_server_side(client):
    mock_hooks = [
        {
            "id": str(uuid.uuid4()),
            "received_at": "2026-05-14T06:12:00+00:00",
            "payload": {"rule_name": "zscore_spike_global", "severity": "warning", "z_score": 4.2},
            "source_ip": "172.18.0.3",
        }
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_hooks

    with patch("app.dashboard.router.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_http

        resp = await client.get("/dashboard/partials/webhooks")

    assert resp.status_code == 200
    assert "zscore_spike_global" in resp.text
    assert "warning" in resp.text


@pytest.mark.asyncio
async def test_zscore_partial_returns_html(client):
    resp = await client.get("/dashboard/partials/zscore")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_zscore_partial_shows_building_with_no_data(client):
    """No events in DB → not enough history → status=building."""
    resp = await client.get("/dashboard/partials/zscore")
    assert resp.status_code == 200
    assert "BUILDING" in resp.text.upper() or "building" in resp.text


@pytest.mark.asyncio
async def test_zscore_partial_shows_current_count(client, auth_headers):
    """After ingesting events, current_count should appear in the partial."""
    await client.post(
        "/api/v1/events/batch",
        json=[{"level": "error", "message": f"z-test {i}"} for i in range(5)],
        headers=auth_headers,
    )
    resp = await client.get("/dashboard/partials/zscore")
    assert resp.status_code == 200
    assert "events" in resp.text


@pytest.mark.asyncio
async def test_zscore_partial_shows_threshold(client):
    from app.core.config import settings
    resp = await client.get("/dashboard/partials/zscore")
    assert str(settings.anomaly_zscore_threshold) in resp.text


@pytest.mark.asyncio
async def test_zscore_partial_shows_window_info(client):
    from app.core.config import settings
    resp = await client.get("/dashboard/partials/zscore")
    assert str(settings.anomaly_window_minutes) in resp.text


@pytest.mark.asyncio
async def test_webhooks_partial_graceful_on_receiver_down(client):
    import httpx as real_httpx

    with patch("app.dashboard.router.httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=real_httpx.ConnectError("refused"))
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_http

        resp = await client.get("/dashboard/partials/webhooks")

    assert resp.status_code == 200                  # never a 500
    assert "unavailable" in resp.text.lower()
