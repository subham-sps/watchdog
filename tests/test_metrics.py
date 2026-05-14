import pytest


@pytest.mark.asyncio
async def test_metrics_shape(client, auth_headers):
    resp = await client.get("/api/v1/metrics", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events" in data
    assert "events_last_hour" in data
    assert "events_by_level" in data
    assert "active_alerts" in data
    assert "total_sources" in data


@pytest.mark.asyncio
async def test_metrics_counts_ingested_events(client, auth_headers):
    before = (await client.get("/api/v1/metrics", headers=auth_headers)).json()["total_events"]
    await client.post("/api/v1/events", json={"level": "error", "message": "m1"}, headers=auth_headers)
    await client.post("/api/v1/events", json={"level": "info", "message": "m2"}, headers=auth_headers)
    after = (await client.get("/api/v1/metrics", headers=auth_headers)).json()["total_events"]
    assert after == before + 2


@pytest.mark.asyncio
async def test_metrics_events_by_level(client, auth_headers):
    await client.post("/api/v1/events", json={"level": "critical", "message": "crit event"}, headers=auth_headers)
    resp = await client.get("/api/v1/metrics", headers=auth_headers)
    assert resp.json()["events_by_level"].get("critical", 0) >= 1


@pytest.mark.asyncio
async def test_metrics_counts_sources(client, auth_headers):
    before = (await client.get("/api/v1/metrics", headers=auth_headers)).json()["total_sources"]
    await client.post("/api/v1/sources", json={"name": "metrics-source-test"}, headers=auth_headers)
    after = (await client.get("/api/v1/metrics", headers=auth_headers)).json()["total_sources"]
    assert after == before + 1


@pytest.mark.asyncio
async def test_metrics_requires_auth(client):
    resp = await client.get("/api/v1/metrics")
    assert resp.status_code == 401
