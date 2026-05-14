"""
Webhook payload adapters.

Each adapter takes an Alert ORM object and an extras dict (z_score,
current_count, baseline_mean, etc.) and returns a JSON-serialisable dict
shaped for the target system.

Adding a new target:
  1. Write a build_<name>_payload function.
  2. Register it in ADAPTERS.
  3. Set WEBHOOK_TYPE=<name> in the environment.
"""
from __future__ import annotations

from datetime import timezone
from typing import Any

from app.models.alert import Alert


def build_watchdog_payload(alert: Alert, extra: dict[str, Any]) -> dict[str, Any]:
    """Our own schema — consumed by the internal webhook-receiver service."""
    return {
        "alert_id": str(alert.id),
        "rule_name": alert.rule_name,
        "severity": alert.severity,
        "message": alert.message,
        "source_id": str(alert.source_id) if alert.source_id else None,
        "fired_at": alert.created_at.astimezone(timezone.utc).isoformat(),
        **{k: v for k, v in extra.items() if isinstance(v, (int, float, str, bool, type(None)))},
    }


def build_slack_payload(alert: Alert, extra: dict[str, Any]) -> dict[str, Any]:
    """Slack Incoming Webhooks format using Block Kit."""
    severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(
        alert.severity, "⚪"
    )
    z_score = extra.get("z_score", "n/a")
    mean = extra.get("baseline_mean", "n/a")
    current = extra.get("current_count", "n/a")
    fired_at = alert.created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    source_line = f"source `{alert.source_id}`  •  " if alert.source_id else ""

    return {
        "text": f"{severity_emoji} Watchdog alert: {alert.rule_name}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji} {alert.rule_name}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Severity:* {alert.severity}\n"
                        f"*Message:* {alert.message}"
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"{source_line}"
                            f"z={z_score}  •  mean={mean}  •  current={current}  •  fired {fired_at}"
                        ),
                    }
                ],
            },
        ],
    }


def build_generic_payload(alert: Alert, extra: dict[str, Any]) -> dict[str, Any]:
    """
    Minimal flat payload compatible with most generic webhook receivers
    (Zapier, Make, n8n, custom HTTP triggers, etc.).
    """
    return {
        "alert_id": str(alert.id),
        "title": alert.rule_name,
        "severity": alert.severity,
        "text": alert.message,
        "source_id": str(alert.source_id) if alert.source_id else None,
        "fired_at": alert.created_at.astimezone(timezone.utc).isoformat(),
        "z_score": extra.get("z_score"),
        "current_count": extra.get("current_count"),
        "baseline_mean": extra.get("baseline_mean"),
    }


ADAPTERS: dict[str, Any] = {
    "watchdog": build_watchdog_payload,
    "slack": build_slack_payload,
    "generic": build_generic_payload,
}
