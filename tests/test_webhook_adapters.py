"""
Unit tests for webhook payload adapters.
Pure functions — no DB, no HTTP.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.models.alert import Alert
from anomaly_worker.adapters import (
    build_watchdog_payload,
    build_slack_payload,
    build_generic_payload,
    ADAPTERS,
)


def _make_alert(source_id=None) -> Alert:
    alert = Alert()
    alert.id = uuid.uuid4()
    alert.rule_name = "zscore_spike_global"
    alert.severity = "warning"
    alert.message = "Global error spike: 200 events (z=4.2, mean=8.1)"
    alert.source_id = source_id
    alert.created_at = datetime(2026, 5, 14, 6, 12, 0, tzinfo=timezone.utc)
    alert.acknowledged = False
    alert.resolved_at = None
    return alert


_EXTRA = {
    "z_score": 4.2,
    "current_count": 200,
    "baseline_mean": 8.1,
    "baseline_stddev": 1.5,
    "is_spike": True,
}


# ---------------------------------------------------------------------------
# ADAPTERS registry
# ---------------------------------------------------------------------------

def test_all_three_adapters_registered():
    assert set(ADAPTERS.keys()) == {"watchdog", "slack", "generic"}


# ---------------------------------------------------------------------------
# watchdog adapter
# ---------------------------------------------------------------------------

def test_watchdog_payload_required_fields():
    alert = _make_alert()
    p = build_watchdog_payload(alert, _EXTRA)
    for field in ("alert_id", "rule_name", "severity", "message", "fired_at"):
        assert field in p, f"Missing field: {field}"


def test_watchdog_payload_values():
    alert = _make_alert()
    p = build_watchdog_payload(alert, _EXTRA)
    assert p["alert_id"] == str(alert.id)
    assert p["rule_name"] == "zscore_spike_global"
    assert p["severity"] == "warning"
    assert p["z_score"] == 4.2
    assert p["current_count"] == 200
    assert p["source_id"] is None


def test_watchdog_payload_with_source_id():
    src = uuid.uuid4()
    alert = _make_alert(source_id=src)
    p = build_watchdog_payload(alert, _EXTRA)
    assert p["source_id"] == str(src)


def test_watchdog_payload_excludes_non_scalar_extras():
    alert = _make_alert()
    extra_with_obj = {**_EXTRA, "nested": {"key": "val"}, "lst": [1, 2]}
    p = build_watchdog_payload(alert, extra_with_obj)
    assert "nested" not in p
    assert "lst" not in p


# ---------------------------------------------------------------------------
# slack adapter
# ---------------------------------------------------------------------------

def test_slack_payload_has_text_and_blocks():
    alert = _make_alert()
    p = build_slack_payload(alert, _EXTRA)
    assert "text" in p
    assert "blocks" in p
    assert isinstance(p["blocks"], list)
    assert len(p["blocks"]) >= 2


def test_slack_payload_text_mentions_rule():
    alert = _make_alert()
    p = build_slack_payload(alert, _EXTRA)
    assert "zscore_spike_global" in p["text"]


def test_slack_payload_blocks_contain_severity():
    alert = _make_alert()
    p = build_slack_payload(alert, _EXTRA)
    full_text = str(p["blocks"])
    assert "warning" in full_text


def test_slack_payload_context_contains_zscore():
    alert = _make_alert()
    p = build_slack_payload(alert, _EXTRA)
    context_block = next(b for b in p["blocks"] if b["type"] == "context")
    context_text = str(context_block)
    assert "4.2" in context_text


def test_slack_payload_source_id_shown_when_present():
    src = uuid.uuid4()
    alert = _make_alert(source_id=src)
    p = build_slack_payload(alert, _EXTRA)
    assert str(src) in str(p["blocks"])


def test_slack_payload_no_source_line_when_none():
    alert = _make_alert(source_id=None)
    p = build_slack_payload(alert, _EXTRA)
    # "source" word should not appear in context block when source_id is None
    context_block = next(b for b in p["blocks"] if b["type"] == "context")
    assert "source" not in str(context_block).lower()


# ---------------------------------------------------------------------------
# generic adapter
# ---------------------------------------------------------------------------

def test_generic_payload_flat_structure():
    alert = _make_alert()
    p = build_generic_payload(alert, _EXTRA)
    for field in ("alert_id", "title", "severity", "text", "fired_at", "z_score", "current_count", "baseline_mean"):
        assert field in p, f"Missing field: {field}"


def test_generic_payload_values():
    alert = _make_alert()
    p = build_generic_payload(alert, _EXTRA)
    assert p["title"] == "zscore_spike_global"
    assert p["severity"] == "warning"
    assert p["z_score"] == 4.2
    assert p["current_count"] == 200
    assert p["source_id"] is None


def test_generic_payload_source_id_when_present():
    src = uuid.uuid4()
    alert = _make_alert(source_id=src)
    p = build_generic_payload(alert, _EXTRA)
    assert p["source_id"] == str(src)


def test_generic_payload_fired_at_is_iso():
    alert = _make_alert()
    p = build_generic_payload(alert, _EXTRA)
    assert p["fired_at"].startswith("2026-05-14")
    assert "T" in p["fired_at"]
