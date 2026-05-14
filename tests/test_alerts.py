import pytest
import uuid
from sqlalchemy import insert
from app.models.alert import Alert
from datetime import datetime, timezone


async def _seed_alert(db_session, rule_name="spike-detected", severity="warning"):
    alert = Alert(
        id=uuid.uuid4(),
        rule_name=rule_name,
        severity=severity,
        message="Error spike detected",
        acknowledged=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.flush()
    return alert


@pytest.mark.asyncio
async def test_list_alerts_empty(client, auth_headers):
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_alerts_shows_seeded(client, auth_headers, db_session):
    await _seed_alert(db_session)
    resp = await client.get("/api/v1/alerts", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["rule_name"] == "spike-detected"


@pytest.mark.asyncio
async def test_acknowledge_alert(client, auth_headers, db_session):
    alert = await _seed_alert(db_session)
    resp = await client.post(f"/api/v1/alerts/{alert.id}/acknowledge", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["acknowledged"] is True
    assert data["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_acknowledge_alert_idempotent(client, auth_headers, db_session):
    alert = await _seed_alert(db_session)
    r1 = await client.post(f"/api/v1/alerts/{alert.id}/acknowledge", headers=auth_headers)
    r2 = await client.post(f"/api/v1/alerts/{alert.id}/acknowledge", headers=auth_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["acknowledged_at"] == r2.json()["acknowledged_at"]


@pytest.mark.asyncio
async def test_acknowledge_alert_not_found(client, auth_headers):
    resp = await client.post("/api/v1/alerts/00000000-0000-0000-0000-000000000000/acknowledge", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_alerts_filter_unacknowledged(client, auth_headers, db_session):
    a1 = await _seed_alert(db_session, rule_name="unacked")
    a2 = await _seed_alert(db_session, rule_name="acked")
    await client.post(f"/api/v1/alerts/{a2.id}/acknowledge", headers=auth_headers)
    resp = await client.get("/api/v1/alerts?acknowledged=false", headers=auth_headers)
    names = [a["rule_name"] for a in resp.json()]
    assert "unacked" in names
    assert "acked" not in names


@pytest.mark.asyncio
async def test_alerts_requires_auth(client):
    resp = await client.get("/api/v1/alerts")
    assert resp.status_code == 401
