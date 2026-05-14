import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.alert import AlertRead
from app.services import alert_service

router = APIRouter()


@router.get("/alerts", response_model=list[AlertRead], dependencies=[Depends(require_api_key)])
async def list_alerts(
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await alert_service.list_alerts(db, acknowledged=acknowledged, limit=limit, offset=offset)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRead, dependencies=[Depends(require_api_key)])
async def acknowledge_alert(alert_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await alert_service.acknowledge_alert(db, alert_id)
