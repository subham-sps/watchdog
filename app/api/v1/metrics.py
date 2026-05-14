from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.alert import MetricsSummary
from app.services import alert_service

router = APIRouter()


@router.get("/metrics", response_model=MetricsSummary, dependencies=[Depends(require_api_key)])
async def get_metrics(db: AsyncSession = Depends(get_db)):
    return await alert_service.get_metrics(db)
