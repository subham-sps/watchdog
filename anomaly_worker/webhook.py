"""
Webhook dispatcher.

Selects the outbound payload format via WEBHOOK_TYPE (watchdog | slack | generic),
then POSTs to WEBHOOK_URL. Retries once on network errors or 5xx responses.
Failures are logged but never crash the scanner.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.models.alert import Alert
from anomaly_worker.adapters import ADAPTERS

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0)
_RETRIES = 1


async def fire_webhook(alert: Alert, extra: dict[str, Any]) -> None:
    webhook_type = settings.webhook_type.lower()
    build_payload = ADAPTERS.get(webhook_type)
    if build_payload is None:
        logger.error(
            "Unknown WEBHOOK_TYPE '%s'. Valid options: %s. Skipping webhook.",
            webhook_type,
            list(ADAPTERS),
        )
        return

    payload = build_payload(alert, extra)

    for attempt in range(1 + _RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(settings.webhook_url, json=payload)
                if resp.status_code < 500:
                    logger.info(
                        "Webhook delivered (type=%s status=%s)",
                        webhook_type, resp.status_code,
                    )
                    return
                logger.warning(
                    "Webhook returned %s (type=%s attempt=%d/%d)",
                    resp.status_code, webhook_type, attempt + 1, 1 + _RETRIES,
                )
        except httpx.RequestError as exc:
            logger.warning(
                "Webhook request error (type=%s attempt=%d/%d): %s",
                webhook_type, attempt + 1, 1 + _RETRIES, exc,
            )

    logger.error(
        "Webhook failed after %d attempt(s) (type=%s) — alert still written to DB",
        1 + _RETRIES, webhook_type,
    )
