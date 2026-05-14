import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.alert import Alert
from app.models.event import Event, Source
from app.schemas.alert import MetricsSummary


async def create_alert(
    db: AsyncSession,
    rule_name: str,
    message: str,
    severity: str = "warning",
    source_id: Optional[uuid.UUID] = None,
) -> Alert:
    alert = Alert(
        source_id=source_id,
        rule_name=rule_name,
        severity=severity,
        message=message,
    )
    db.add(alert)
    await db.flush()
    return alert


async def list_alerts(
    db: AsyncSession,
    acknowledged: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Alert]:
    filters = []
    if acknowledged is not None:
        filters.append(Alert.acknowledged == acknowledged)

    stmt = (
        select(Alert)
        .where(and_(*filters) if filters else True)
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def acknowledge_alert(db: AsyncSession, alert_id: uuid.UUID) -> Alert:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if not alert.acknowledged:
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc)
        await db.flush()
    return alert


async def get_metrics(db: AsyncSession) -> MetricsSummary:
    total_events = (await db.execute(select(func.count(Event.id)))).scalar_one()

    one_hour_ago = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    from datetime import timedelta
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    events_last_hour = (
        await db.execute(
            select(func.count(Event.id)).where(Event.occurred_at >= one_hour_ago)
        )
    ).scalar_one()

    level_rows = (
        await db.execute(
            select(Event.level, func.count(Event.id)).group_by(Event.level)
        )
    ).all()
    events_by_level = {row[0]: row[1] for row in level_rows}

    active_alerts = (
        await db.execute(
            select(func.count(Alert.id)).where(Alert.acknowledged == False)  # noqa: E712
        )
    ).scalar_one()

    total_sources = (await db.execute(select(func.count(Source.id)))).scalar_one()

    return MetricsSummary(
        total_events=total_events,
        events_last_hour=events_last_hour,
        events_by_level=events_by_level,
        active_alerts=active_alerts,
        total_sources=total_sources,
    )
