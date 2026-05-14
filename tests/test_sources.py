import pytest


@pytest.mark.asyncio
async def test_create_source(client, auth_headers):
    resp = await client.post("/api/v1/sources", json={"name": "app-server", "description": "Main app"}, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "app-server"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_duplicate_source_returns_409(client, auth_headers):
    payload = {"name": "unique-source"}
    await client.post("/api/v1/sources", json=payload, headers=auth_headers)
    resp = await client.post("/api/v1/sources", json=payload, headers=auth_headers)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_sources_empty(client, auth_headers):
    resp = await client.get("/api/v1/sources", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_sources_contains_created(client, auth_headers):
    await client.post("/api/v1/sources", json={"name": "listed-source"}, headers=auth_headers)
    resp = await client.get("/api/v1/sources", headers=auth_headers)
    names = [s["name"] for s in resp.json()]
    assert "listed-source" in names


@pytest.mark.asyncio
async def test_create_source_requires_auth(client):
    resp = await client.post("/api/v1/sources", json={"name": "no-auth"})
    assert resp.status_code == 401
