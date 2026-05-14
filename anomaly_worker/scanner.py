"""
Scanner — DB layer for anomaly detection.

Each scan() call:
1. Computes z-scores globally and per-source.
2. Fires alerts for spikes (subject to cooldown).
3. Auto-resolves open alerts whose z-score has been below 1.5 for 2
   consecutive cycles. Resolution is determined by re-querying the DB
   for the previous two windows — no in-memory state, survives restarts.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func, and_

from app.core.config import settings
from app.models.event import Event
from app.models.alert import Alert
from anomaly_worker.detector import compute_zscore, MIN_BASELINE_WINDOWS
from anomaly_worker.webhook import fire_webhook

logger = logging.getLogger(__name__)

RESOLVE_THRESHOLD = 1.5
RESOLVE_CONSECUTIVE = 2


def _window_bounds(
    window_index: int, window_minutes: int, now: datetime
) -> tuple[datetime, datetime]:
    """
    Returns (start, end) for a window offset from now.
    window_index=0 → current window, 1 → one window ago, etc.
    """
    end = now - timedelta(minutes=window_index * window_minutes)
    start = end - timedelta(minutes=window_minutes)
    return start, end


async def _count_events(
    db: AsyncSession,
    start: datetime,
    end: datetime,
    source_id: Optional[uuid.UUID] = None,
) -> int:
    filters = [Event.occurred_at >= start, Event.occurred_at < end]
    if source_id is not None:
        filters.append(Event.source_id == source_id)
    result = await db.execute(
        select(func.count(Event.id)).where(and_(*filters))
    )
    return result.scalar_one()


async def _get_window_counts(
    db: AsyncSession,
    n_windows: int,
    window_minutes: int,
    now: datetime,
    source_id: Optional[uuid.UUID] = None,
) -> tuple[list[int], int]:
    """Returns (baseline_counts[oldest→newest], current_count)."""
    current_start, current_end = _window_bounds(0, window_minutes, now)
    current_count = await _count_events(db, current_start, current_end, source_id)

    baseline = []
    for i in range(1, n_windows + 1):
        start, end = _window_bounds(i, window_minutes, now)
        count = await _count_events(db, start, end, source_id)
        baseline.append(count)

    return baseline, current_count


async def _is_in_cooldown(
    db: AsyncSession,
    rule_name: str,
    source_id: Optional[uuid.UUID],
) -> bool:
    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=settings.alert_cooldown_minutes
    )
    filters = [
        Alert.rule_name == rule_name,
        Alert.acknowledged == False,  # noqa: E712
        Alert.resolved_at == None,    # noqa: E711
        Alert.created_at >= cooldown_cutoff,
    ]
    if source_id is not None:
        filters.append(Alert.source_id == source_id)
    else:
        filters.append(Alert.source_id == None)  # noqa: E711

    result = await db.execute(select(func.count(Alert.id)).where(and_(*filters)))
    return result.scalar_one() > 0


async def _maybe_fire_alert(
    db: AsyncSession,
    rule_name: str,
    message: str,
    severity: str,
    source_id: Optional[uuid.UUID],
    extra: dict,
) -> Optional[Alert]:
    if await _is_in_cooldown(db, rule_name, source_id):
        logger.debug("Cooldown active for %s source=%s — skipping", rule_name, source_id)
        return None

    alert = Alert(
        source_id=source_id,
        rule_name=rule_name,
        severity=severity,
        message=message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    await db.flush()

    await fire_webhook(alert, extra)
    logger.info("Alert fired: %s source=%s", rule_name, source_id)
    return alert


async def _auto_resolve_alerts(
    db: AsyncSession,
    window_minutes: int,
    now: datetime,
    source_id: Optional[uuid.UUID] = None,
    rule_name: Optional[str] = None,
) -> None:
    """
    For each open alert matching the criteria, check if the last
    RESOLVE_CONSECUTIVE windows all had z-score below RESOLVE_THRESHOLD.
    Resolution is computed fresh from the DB — no in-memory state needed.
    """
    stmt = select(Alert).where(
        Alert.acknowledged == False,  # noqa: E712
        Alert.resolved_at == None,    # noqa: E711
    )
    if rule_name:
        stmt = stmt.where(Alert.rule_name == rule_name)
    if source_id is not None:
        stmt = stmt.where(Alert.source_id == source_id)

    result = await db.execute(stmt)
    open_alerts = result.scalars().all()

    for alert in open_alerts:
        # Re-query baseline for the last N+RESOLVE_CONSECUTIVE windows
        baseline, _ = await _get_window_counts(
            db,
            settings.anomaly_lookback_windows + RESOLVE_CONSECUTIVE,
            window_minutes,
            now,
            source_id=alert.source_id,
        )
        # Evaluate the most recent RESOLVE_CONSECUTIVE windows
        low_count = 0
        for i in range(RESOLVE_CONSECUTIVE):
            start, end = _window_bounds(i + 1, window_minutes, now)
            cnt = await _count_events(db, start, end, alert.source_id)
            recent_baseline = baseline[RESOLVE_CONSECUTIVE:]
            result_z = compute_zscore(
                recent_baseline, cnt, threshold=RESOLVE_THRESHOLD
            )
            # If result is None (insufficient data) or z < threshold → counts as low
            if result_z is None or not result_z.is_spike:
                low_count += 1

        if low_count >= RESOLVE_CONSECUTIVE:
            alert.resolved_at = datetime.now(timezone.utc)
            await db.flush()
            logger.info("Auto-resolved alert %s (rule=%s)", alert.id, alert.rule_name)


async def scan(db: AsyncSession) -> None:
    """Run one full anomaly scan cycle: global + per-source."""
    now = datetime.now(timezone.utc)
    window_minutes = settings.anomaly_window_minutes
    lookback = settings.anomaly_lookback_windows
    threshold = settings.anomaly_zscore_threshold

    # --- Global scan ---
    baseline, current = await _get_window_counts(db, lookback, window_minutes, now)
    result = compute_zscore(baseline, current, threshold)

    if result is not None:
        if result.is_spike:
            await _maybe_fire_alert(
                db,
                rule_name="zscore_spike_global",
                message=(
                    f"Global error spike: {current} events in last {window_minutes}m "
                    f"(z={result.z_score}, mean={result.baseline_mean:.1f})"
                ),
                severity="warning",
                source_id=None,
                extra=result.__dict__,
            )
        else:
            await _auto_resolve_alerts(
                db, window_minutes, now, source_id=None, rule_name="zscore_spike_global"
            )

    # --- Per-source scan ---
    # Find all sources that had events in the current window
    current_start, current_end = _window_bounds(0, window_minutes, now)
    active_sources = (
        await db.execute(
            select(Event.source_id)
            .where(
                Event.source_id != None,  # noqa: E711
                Event.occurred_at >= current_start,
                Event.occurred_at < current_end,
            )
            .distinct()
        )
    ).scalars().all()

    for source_id in active_sources:
        baseline, current = await _get_window_counts(
            db, lookback, window_minutes, now, source_id=source_id
        )
        result = compute_zscore(baseline, current, threshold)

        if result is not None:
            if result.is_spike:
                await _maybe_fire_alert(
                    db,
                    rule_name="zscore_spike_per_source",
                    message=(
                        f"Spike on source {source_id}: {current} events "
                        f"(z={result.z_score}, mean={result.baseline_mean:.1f})"
                    ),
                    severity="warning",
                    source_id=source_id,
                    extra=result.__dict__,
                )
            else:
                await _auto_resolve_alerts(
                    db, window_minutes, now,
                    source_id=source_id,
                    rule_name="zscore_spike_per_source",
                )

    await db.commit()
    logger.info("Scan complete — now=%s", now.isoformat())
