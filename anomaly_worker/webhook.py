"""
Webhook dispatcher — fires an HTTP POST to WEBHOOK_URL when an alert is created.
Retries once on network errors or 5xx responses. Failures are logged but never
crash the scanner — a missed webhook is not worth aborting a scan cycle.
"""
from __future__ import annotations

import logging
from datetime import timezone

import httpx

from app.core.config import settings
from app.models.alert import Alert

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0)
_RETRIES = 1


async def fire_webhook(alert: Alert, extra: dict) -> None:
    payload = {
        "alert_id": str(alert.id),
        "rule_name": alert.rule_name,
        "severity": alert.severity,
        "message": alert.message,
        "source_id": str(alert.source_id) if alert.source_id else None,
        "fired_at": alert.created_at.astimezone(timezone.utc).isoformat(),
        **{k: v for k, v in extra.items() if isinstance(v, (int, float, str, bool, type(None)))},
    }

    for attempt in range(1 + _RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(settings.webhook_url, json=payload)
                if resp.status_code < 500:
                    logger.info("Webhook delivered (status=%s)", resp.status_code)
                    return
                logger.warning(
                    "Webhook returned %s (attempt %d/%d)",
                    resp.status_code, attempt + 1, 1 + _RETRIES,
                )
        except httpx.RequestError as exc:
            logger.warning(
                "Webhook request error (attempt %d/%d): %s",
                attempt + 1, 1 + _RETRIES, exc,
            )

    logger.error("Webhook failed after %d attempt(s) — alert still written to DB", 1 + _RETRIES)
