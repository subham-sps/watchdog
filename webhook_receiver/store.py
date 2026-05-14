"""
In-memory ring buffer for received webhook payloads.

Thread-safe via a Lock. When the buffer reaches MAX_ENTRIES the oldest
entry is silently evicted (deque maxlen behaviour). No persistence —
intentional: the receiver is an observability tool, not a durable store.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

MAX_ENTRIES = 200


@dataclass
class WebhookEntry:
    id: str
    received_at: datetime
    payload: dict[str, Any]
    source_ip: str


class WebhookStore:
    def __init__(self, maxlen: int = MAX_ENTRIES) -> None:
        self._entries: deque[WebhookEntry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._maxlen = maxlen

    def add(self, payload: dict[str, Any], source_ip: str = "") -> WebhookEntry:
        entry = WebhookEntry(
            id=str(uuid.uuid4()),
            received_at=datetime.now(timezone.utc),
            payload=payload,
            source_ip=source_ip,
        )
        with self._lock:
            self._entries.appendleft(entry)   # newest first
        return entry

    def list(self, limit: int = 20) -> list[WebhookEntry]:
        with self._lock:
            return list(self._entries)[:limit]

    def get(self, entry_id: str) -> WebhookEntry | None:
        with self._lock:
            for entry in self._entries:
                if entry.id == entry_id:
                    return entry
        return None

    def count(self) -> int:
        with self._lock:
            return len(self._entries)
