from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.event import SourceCreate, SourceRead
from app.services import source_service

router = APIRouter()


@router.post("/sources", response_model=SourceRead, status_code=201, dependencies=[Depends(require_api_key)])
async def create_source(data: SourceCreate, db: AsyncSession = Depends(get_db)):
    return await source_service.create_source(db, data)


@router.get("/sources", response_model=list[SourceRead], dependencies=[Depends(require_api_key)])
async def list_sources(db: AsyncSession = Depends(get_db)):
    return await source_service.list_sources(db)
