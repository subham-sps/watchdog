"""
Webhook receiver FastAPI app.

Accepts incoming webhook POSTs from the anomaly worker (or any other sender),
stores them in a ring buffer, and exposes a read API for the dashboard.

No auth on POST /hook — this service is internal to the Docker network.
The anomaly worker is the only expected caller.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel

from webhook_receiver.store import WebhookStore

app = FastAPI(title="Watchdog Webhook Receiver", version="1.0.0")
store = WebhookStore()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WebhookEntryOut(BaseModel):
    id: str
    received_at: str
    payload: dict[str, Any]
    source_ip: str


def _entry_to_out(entry) -> WebhookEntryOut:
    return WebhookEntryOut(
        id=entry.id,
        received_at=entry.received_at.isoformat(),
        payload=entry.payload,
        source_ip=entry.source_ip,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/hook", status_code=status.HTTP_202_ACCEPTED)
async def receive_hook(request: Request, body: dict[str, Any]) -> dict[str, str]:
    source_ip = request.client.host if request.client else ""
    entry = store.add(payload=body, source_ip=source_ip)
    return {"status": "accepted", "id": entry.id}


@app.get("/hooks", response_model=list[WebhookEntryOut])
async def list_hooks(limit: int = Query(20, ge=1, le=200)) -> list[WebhookEntryOut]:
    return [_entry_to_out(e) for e in store.list(limit=limit)]


@app.get("/hooks/{hook_id}", response_model=WebhookEntryOut)
async def get_hook(hook_id: str) -> WebhookEntryOut:
    entry = store.get(hook_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hook not found")
    return _entry_to_out(entry)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "stored": store.count()}
