import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.event import Event
from app.schemas.event import EventCreate


async def ingest(db: AsyncSession, data: EventCreate) -> Event:
    event = Event(
        source_id=data.source_id,
        level=data.level,
        message=data.message,
        payload=data.payload,
        fingerprint=data.fingerprint,
        occurred_at=data.occurred_at or datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    return event


async def ingest_batch(db: AsyncSession, items: list[EventCreate]) -> list[Event]:
    now = datetime.now(timezone.utc)
    events = [
        Event(
            source_id=item.source_id,
            level=item.level,
            message=item.message,
            payload=item.payload,
            fingerprint=item.fingerprint,
            occurred_at=item.occurred_at or now,
        )
        for item in items
    ]
    db.add_all(events)
    await db.flush()
    return events


async def list_events(
    db: AsyncSession,
    source_id: Optional[uuid.UUID] = None,
    level: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Event]:
    filters = []
    if source_id:
        filters.append(Event.source_id == source_id)
    if level:
        filters.append(Event.level == level.lower())
    if since:
        filters.append(Event.occurred_at >= since)
    if until:
        filters.append(Event.occurred_at <= until)

    stmt = (
        select(Event)
        .where(and_(*filters) if filters else True)
        .order_by(Event.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_event(db: AsyncSession, event_id: uuid.UUID) -> Event:
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event
