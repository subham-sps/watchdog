"""
Anomaly worker entry point.

Runs as a standalone process (not inside FastAPI). Uses APScheduler to call
scanner.scan() on a fixed interval. Alembic migrations are expected to have
already run (docker-compose entrypoint handles this).
"""
import asyncio
import logging
import os
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import settings
from anomaly_worker.scanner import scan

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def run_scan() -> None:
    async with SessionLocal() as db:
        try:
            await scan(db)
        except Exception:
            logger.exception("Scan cycle failed")


def main() -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_scan,
        trigger="interval",
        minutes=settings.anomaly_window_minutes,
        id="anomaly_scan",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Anomaly worker started — scan interval=%dm, threshold=%.1f, lookback=%d windows",
        settings.anomaly_window_minutes,
        settings.anomaly_zscore_threshold,
        settings.anomaly_lookback_windows,
    )

    loop = asyncio.get_event_loop()
    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Anomaly worker shutting down")
    finally:
        scheduler.shutdown(wait=False)
        loop.run_until_complete(engine.dispose())


if __name__ == "__main__":
    main()
