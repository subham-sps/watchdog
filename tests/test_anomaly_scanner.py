"""
Integration tests for the anomaly scanner.

Each test seeds events directly into the DB (using the test session),
then calls scanner.scan() and asserts the resulting alert rows.
Webhook calls are mocked — we verify the call was made with the right payload.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from app.models.event import Event, Source
from app.models.alert import Alert
from anomaly_worker.scanner import scan
from app.core.config import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(minutes_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)


async def _seed_events(
    db_session,
    count: int,
    minutes_ago: int = 0,
    source_id=None,
    level: str = "error",
):
    for _ in range(count):
        event = Event(
            source_id=source_id,
            level=level,
            message="test event",
            occurred_at=_ts(minutes_ago),
        )
        db_session.add(event)
    await db_session.flush()


async def _seed_baseline(db_session, counts: list[int], window_minutes: int, source_id=None):
    """Seed historical windows. counts[0] = oldest window."""
    n = len(counts)
    for i, count in enumerate(counts):
        # window index: oldest = n, newest baseline = 1
        window_index = n - i
        midpoint_ago = int(window_minutes * window_index + window_minutes / 2)
        await _seed_events(db_session, count, minutes_ago=midpoint_ago, source_id=source_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scan_no_alert_when_no_events(db_session):
    with patch("anomaly_worker.scanner.fire_webhook", new_callable=AsyncMock):
        await scan(db_session)
    result = await db_session.execute(__import__("sqlalchemy").select(Alert))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_scan_no_alert_on_zero_stddev_baseline(db_session):
    """
    All baseline windows empty (system just started, no history) → stddev=0
    → compute_zscore returns None → no alert even with a current spike.
    """
    # No baseline events seeded — all 6 lookback windows are empty (count=0)
    await _seed_events(db_session, count=200)  # current window spike

    with patch("anomaly_worker.scanner.fire_webhook", new_callable=AsyncMock) as mock_wh:
        await scan(db_session)

    mock_wh.assert_not_called()
    from sqlalchemy import select
    result = await db_session.execute(select(Alert))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_scan_fires_alert_on_global_spike(db_session):
    """6 stable baseline windows then a large spike → global alert."""
    w = settings.anomaly_window_minutes
    await _seed_baseline(db_session, counts=[3, 5, 7, 4, 6, 5], window_minutes=w)
    await _seed_events(db_session, count=200)  # huge spike in current window

    with patch("anomaly_worker.scanner.fire_webhook", new_callable=AsyncMock) as mock_wh:
        await scan(db_session)

    mock_wh.assert_called_once()
    payload_alert = mock_wh.call_args[0][0]
    assert payload_alert.rule_name == "zscore_spike_global"

    from sqlalchemy import select
    alerts = (await db_session.execute(select(Alert))).scalars().all()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "zscore_spike_global"
    assert alerts[0].resolved_at is None


@pytest.mark.asyncio
async def test_scan_respects_cooldown(db_session):
    """Second scan within cooldown window must not create a duplicate alert."""
    w = settings.anomaly_window_minutes
    await _seed_baseline(db_session, counts=[3, 5, 7, 4, 6, 5], window_minutes=w)
    await _seed_events(db_session, count=200)

    with patch("anomaly_worker.scanner.fire_webhook", new_callable=AsyncMock) as mock_wh:
        await scan(db_session)
        await scan(db_session)  # second scan — still in cooldown

    assert mock_wh.call_count == 1

    from sqlalchemy import select
    alerts = (await db_session.execute(select(Alert))).scalars().all()
    assert len(alerts) == 1


@pytest.mark.asyncio
async def test_scan_per_source_fires_only_spiking_source(db_session):
    """Source A spikes, Source B is stable — only Source A gets an alert."""
    w = settings.anomaly_window_minutes

    src_a = Source(name="source-a")
    src_b = Source(name="source-b")
    db_session.add_all([src_a, src_b])
    await db_session.flush()

    # Stable baseline for both
    await _seed_baseline(db_session, counts=[3, 5, 7, 4, 6, 5], window_minutes=w, source_id=src_a.id)
    await _seed_baseline(db_session, counts=[3, 5, 7, 4, 6, 5], window_minutes=w, source_id=src_b.id)

    # Spike only on A
    await _seed_events(db_session, count=200, source_id=src_a.id)
    await _seed_events(db_session, count=5, source_id=src_b.id)

    with patch("anomaly_worker.scanner.fire_webhook", new_callable=AsyncMock):
        await scan(db_session)

    from sqlalchemy import select
    alerts = (await db_session.execute(select(Alert))).scalars().all()
    source_ids = {str(a.source_id) for a in alerts}
    assert str(src_a.id) in source_ids
    assert str(src_b.id) not in source_ids


@pytest.mark.asyncio
async def test_scan_auto_resolves_open_alert(db_session):
    """
    Pre-existing open alert + calm current scan → alert is auto-resolved.

    Design: we can't advance real time in a unit test, so we pre-create the
    open alert and verify that a scan with a calm current window (z < 1.5 for
    2 recent windows) sets resolved_at. This isolates the auto-resolve logic
    from the spike-detection path.
    """
    from sqlalchemy import select

    w = settings.anomaly_window_minutes

    # Pre-create an open alert representing a spike that fired earlier
    existing_alert = Alert(
        rule_name="zscore_spike_global",
        severity="warning",
        message="Past spike",
        acknowledged=False,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=w * 3),
    )
    db_session.add(existing_alert)
    await db_session.flush()

    # Seed 8 historical windows. Windows 1 and 2 get counts 6 and 4 respectively
    # (the last two entries in the list). Against windows 3-8 (mean≈5, stddev≈1.3),
    # z(window1)≈0.78 and z(window2)≈-0.78 — both below the 1.5 resolve threshold.
    # No events in the current window → global z is very negative → is_spike=False
    # → _auto_resolve_alerts is called.
    await _seed_baseline(db_session, counts=[3, 5, 7, 4, 6, 5, 4, 6], window_minutes=w)

    with patch("anomaly_worker.scanner.fire_webhook", new_callable=AsyncMock):
        await scan(db_session)

    await db_session.refresh(existing_alert)
    assert existing_alert.resolved_at is not None


@pytest.mark.asyncio
async def test_webhook_payload_contains_zscore(db_session):
    """Webhook payload must include z_score, current_count, baseline_mean."""
    w = settings.anomaly_window_minutes
    await _seed_baseline(db_session, counts=[3, 5, 7, 4, 6, 5], window_minutes=w)
    await _seed_events(db_session, count=200)

    with patch("anomaly_worker.scanner.fire_webhook", new_callable=AsyncMock) as mock_wh:
        await scan(db_session)

    assert mock_wh.called
    extra = mock_wh.call_args[0][1]
    assert "z_score" in extra
    assert "current_count" in extra
    assert "baseline_mean" in extra
    assert extra["current_count"] == 200
