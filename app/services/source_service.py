import uuid
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.event import Source
from app.schemas.event import SourceCreate


async def create_source(db: AsyncSession, data: SourceCreate) -> Source:
    source = Source(name=data.name, description=data.description)
    db.add(source)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source with name '{data.name}' already exists",
        )
    return source


async def list_sources(db: AsyncSession) -> list[Source]:
    result = await db.execute(select(Source).order_by(Source.created_at.desc()))
    return list(result.scalars().all())


async def get_source(db: AsyncSession, source_id: uuid.UUID) -> Source:
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return source


async def get_or_create_source(db: AsyncSession, name: str) -> Source:
    result = await db.execute(select(Source).where(Source.name == name))
    source = result.scalar_one_or_none()
    if source:
        return source
    source = Source(name=name)
    db.add(source)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # Race condition: another request created it between our SELECT and INSERT
        result = await db.execute(select(Source).where(Source.name == name))
        source = result.scalar_one()
    return source
