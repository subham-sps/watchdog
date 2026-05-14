import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_ingest_event(client, auth_headers):
    resp = await client.post(
        "/api/v1/events",
        json={"level": "error", "message": "Something broke"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["level"] == "error"
    assert data["message"] == "Something broke"
    assert "id" in data
    assert "occurred_at" in data


@pytest.mark.asyncio
async def test_ingest_event_invalid_level(client, auth_headers):
    resp = await client.post(
        "/api/v1/events",
        json={"level": "verbose", "message": "Bad level"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_event_empty_message(client, auth_headers):
    resp = await client.post(
        "/api/v1/events",
        json={"level": "info", "message": "   "},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ingest_event_requires_auth(client):
    resp = await client.post("/api/v1/events", json={"message": "test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ingest_event_with_payload(client, auth_headers):
    resp = await client.post(
        "/api/v1/events",
        json={"level": "warning", "message": "High CPU", "payload": {"cpu": 95.5, "host": "web-01"}},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["payload"]["host"] == "web-01"


@pytest.mark.asyncio
async def test_ingest_event_with_custom_occurred_at(client, auth_headers):
    ts = "2026-01-01T00:00:00Z"
    resp = await client.post(
        "/api/v1/events",
        json={"level": "info", "message": "Past event", "occurred_at": ts},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["occurred_at"].startswith("2026-01-01")


@pytest.mark.asyncio
async def test_list_events(client, auth_headers):
    for i in range(3):
        await client.post("/api/v1/events", json={"level": "info", "message": f"event {i}"}, headers=auth_headers)
    resp = await client.get("/api/v1/events", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 3


@pytest.mark.asyncio
async def test_list_events_filter_by_level(client, auth_headers):
    await client.post("/api/v1/events", json={"level": "critical", "message": "crit"}, headers=auth_headers)
    await client.post("/api/v1/events", json={"level": "debug", "message": "dbg"}, headers=auth_headers)
    resp = await client.get("/api/v1/events?level=critical", headers=auth_headers)
    assert resp.status_code == 200
    assert all(e["level"] == "critical" for e in resp.json())


@pytest.mark.asyncio
async def test_get_event_by_id(client, auth_headers):
    create = await client.post("/api/v1/events", json={"level": "info", "message": "find me"}, headers=auth_headers)
    event_id = create.json()["id"]
    resp = await client.get(f"/api/v1/events/{event_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == event_id


@pytest.mark.asyncio
async def test_get_event_not_found(client, auth_headers):
    resp = await client.get("/api/v1/events/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_events_pagination(client, auth_headers):
    for i in range(5):
        await client.post("/api/v1/events", json={"level": "info", "message": f"page {i}"}, headers=auth_headers)
    page1 = await client.get("/api/v1/events?limit=2&offset=0", headers=auth_headers)
    page2 = await client.get("/api/v1/events?limit=2&offset=2", headers=auth_headers)
    assert len(page1.json()) == 2
    ids_p1 = {e["id"] for e in page1.json()}
    ids_p2 = {e["id"] for e in page2.json()}
    assert ids_p1.isdisjoint(ids_p2)


# ---------------------------------------------------------------------------
# Batch ingest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_ingest_events(client, auth_headers):
    payload = [
        {"level": "info", "message": "batch-1"},
        {"level": "warning", "message": "batch-2"},
        {"level": "error", "message": "batch-3"},
    ]
    resp = await client.post("/api/v1/events/batch", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 3
    levels = {e["level"] for e in data}
    assert levels == {"info", "warning", "error"}


@pytest.mark.asyncio
async def test_batch_ingest_all_appear_in_list(client, auth_headers):
    payload = [{"level": "debug", "message": f"bulk-{i}"} for i in range(10)]
    await client.post("/api/v1/events/batch", json=payload, headers=auth_headers)
    resp = await client.get("/api/v1/events?level=debug&limit=20", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 10


@pytest.mark.asyncio
async def test_batch_empty_list_rejected(client, auth_headers):
    resp = await client.post("/api/v1/events/batch", json=[], headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_invalid_level_rejected(client, auth_headers):
    payload = [
        {"level": "info", "message": "ok"},
        {"level": "INVALID", "message": "bad level"},
    ]
    resp = await client.post("/api/v1/events/batch", json=payload, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_requires_auth(client):
    payload = [{"level": "info", "message": "no key"}]
    resp = await client.post("/api/v1/events/batch", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_batch_single_item_accepted(client, auth_headers):
    resp = await client.post(
        "/api/v1/events/batch",
        json=[{"level": "critical", "message": "solo batch"}],
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 1
