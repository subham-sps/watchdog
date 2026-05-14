from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.dashboard.router import dashboard_router
from app.core.config import settings
import logging

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "dashboard" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Watchdog API starting up")
    yield
    logger.info("Watchdog API shutting down")


app = FastAPI(
    title="Watchdog — Observability API",
    version="1.0.0",
    description="API-first observability platform: event ingestion, anomaly detection, alerting.",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(api_router)
app.include_router(dashboard_router)
