"""
Log generator entry point.

Environment variables:
  WATCHDOG_API_URL   Base URL of the Watchdog API  (default: http://localhost:8000)
  WATCHDOG_API_KEY   API key for X-API-Key header  (default: dev-key-1234)
  PROFILE            Traffic profile name           (default: normal)
  TICK_SECONDS       Seconds between ticks          (default: 5)
"""
import asyncio
import logging
import os
import sys

from log_generator.profiles import PROFILES
from log_generator.generator import GeneratorState

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def run() -> None:
    profile_name = os.getenv("PROFILE", "normal")
    if profile_name not in PROFILES:
        logger.error("Unknown profile '%s'. Available: %s", profile_name, list(PROFILES))
        sys.exit(1)

    profile = PROFILES[profile_name]
    tick_seconds = int(os.getenv("TICK_SECONDS", "5"))
    api_url = os.getenv("WATCHDOG_API_URL", "http://localhost:8000").rstrip("/")
    api_key = os.getenv("WATCHDOG_API_KEY", "dev-key-1234")

    state = GeneratorState(
        profile=profile,
        api_url=api_url,
        api_key=api_key,
        tick_seconds=tick_seconds,
    )

    logger.info(
        "Log generator started — profile=%s tick=%ds api=%s",
        profile.name, tick_seconds, api_url,
    )

    while True:
        await state.tick()
        await asyncio.sleep(tick_seconds)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Log generator stopped")


if __name__ == "__main__":
    main()
