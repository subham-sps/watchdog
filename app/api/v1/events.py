import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.event import EventCreate, EventRead
from app.services import event_service

router = APIRouter()


@router.post("/events", response_model=EventRead, status_code=201, dependencies=[Depends(require_api_key)])
async def ingest_event(data: EventCreate, db: AsyncSession = Depends(get_db)):
    return await event_service.ingest(db, data)


@router.get("/events", response_model=list[EventRead], dependencies=[Depends(require_api_key)])
async def list_events(
    source_id: Optional[uuid.UUID] = Query(None),
    level: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await event_service.list_events(
        db,
        source_id=source_id,
        level=level,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )


@router.get("/events/{event_id}", response_model=EventRead, dependencies=[Depends(require_api_key)])
async def get_event(event_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await event_service.get_event(db, event_id)
