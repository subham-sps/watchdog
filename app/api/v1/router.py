from fastapi import APIRouter
from app.api.v1 import health, sources, events, alerts, metrics

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router, tags=["health"])
api_router.include_router(sources.router, tags=["sources"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(alerts.router, tags=["alerts"])
api_router.include_router(metrics.router, tags=["metrics"])
