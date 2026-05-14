"""
Integration tests for the webhook receiver service.
Uses httpx AsyncClient against the FastAPI app directly — no real network.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from webhook_receiver.app import app, store
from webhook_receiver.store import WebhookStore


@pytest.fixture(autouse=True)
def reset_store():
    """Give each test a fresh store so entries don't bleed between tests."""
    app.state  # ensure app is initialised
    store._entries.clear()
    yield
    store._entries.clear()


@pytest.fixture()
async def rclient():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# POST /hook
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_hook_returns_202(rclient):
    resp = await rclient.post("/hook", json={"alert_id": "abc", "severity": "warning"})
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    assert "id" in resp.json()


@pytest.mark.asyncio
async def test_post_hook_stores_payload(rclient):
    payload = {"alert_id": "xyz", "rule_name": "zscore_spike_global", "severity": "critical"}
    await rclient.post("/hook", json=payload)
    resp = await rclient.get("/hooks")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["payload"]["alert_id"] == "xyz"


@pytest.mark.asyncio
async def test_post_empty_body_rejected(rclient):
    resp = await rclient.post("/hook", content=b"", headers={"Content-Type": "application/json"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_non_json_rejected(rclient):
    resp = await rclient.post("/hook", content=b"not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /hooks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_hooks_newest_first(rclient):
    for i in range(3):
        await rclient.post("/hook", json={"seq": i})
    resp = await rclient.get("/hooks")
    seqs = [e["payload"]["seq"] for e in resp.json()]
    assert seqs == [2, 1, 0]


@pytest.mark.asyncio
async def test_get_hooks_limit_param(rclient):
    for i in range(5):
        await rclient.post("/hook", json={"seq": i})
    resp = await rclient.get("/hooks?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_hooks_empty_when_no_posts(rclient):
    resp = await rclient.get("/hooks")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /hooks/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_hook_by_id(rclient):
    post_resp = await rclient.post("/hook", json={"rule_name": "test"})
    hook_id = post_resp.json()["id"]
    resp = await rclient.get(f"/hooks/{hook_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == hook_id
    assert resp.json()["payload"]["rule_name"] == "test"


@pytest.mark.asyncio
async def test_get_hook_not_found(rclient):
    resp = await rclient.get("/hooks/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_ok(rclient):
    resp = await rclient.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_reports_correct_count(rclient):
    for _ in range(3):
        await rclient.post("/hook", json={"x": 1})
    resp = await rclient.get("/health")
    assert resp.json()["stored"] == 3


# ---------------------------------------------------------------------------
# Ring buffer eviction
# ---------------------------------------------------------------------------

def test_ring_buffer_evicts_oldest():
    s = WebhookStore(maxlen=5)
    for i in range(6):
        s.add({"seq": i}, source_ip="127.0.0.1")
    entries = s.list(limit=10)
    seqs = [e.payload["seq"] for e in entries]
    assert 0 not in seqs         # oldest evicted
    assert 5 in seqs             # newest present
    assert len(entries) == 5


def test_ring_buffer_count_respects_maxlen():
    s = WebhookStore(maxlen=3)
    for i in range(10):
        s.add({"i": i})
    assert s.count() == 3
