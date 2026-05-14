"""
Generator — builds event batches and POSTs them to the Watchdog API.

One tick = TICK_SECONDS seconds. Per tick the generator:
  1. Determines which sources are bursting (respects spike_source + burst_once).
  2. For each source, computes how many events to emit this tick.
  3. Builds a batch payload and fires ONE POST /api/v1/events/batch.
  4. Logs outcome; never raises on API errors.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from log_generator.profiles import Profile

logger = logging.getLogger(__name__)


@dataclass
class GeneratorState:
    profile: Profile
    api_url: str
    api_key: str
    tick_seconds: int = 5
    _source_index: int = 0
    _burst_fired: bool = False       # latch for burst_once profiles
    _started_at: float = field(default_factory=time.monotonic)

    def _elapsed_seconds(self) -> float:
        return time.monotonic() - self._started_at

    def _is_bursting(self) -> bool:
        p = self.profile
        if p.burst_every_minutes is None:
            return False
        if p.burst_once and self._burst_fired:
            return False

        elapsed = self._elapsed_seconds()
        cycle = p.burst_every_minutes * 60
        position_in_cycle = elapsed % cycle

        if position_in_cycle < p.burst_duration_secs:
            if p.burst_once and not self._burst_fired:
                self._burst_fired = True
                logger.info("burst_once latch triggered for profile '%s'", p.name)
            return True
        return False

    def _pick_level(self) -> str:
        levels = list(self.profile.level_weights.keys())
        weights = list(self.profile.level_weights.values())
        return random.choices(levels, weights=weights, k=1)[0]

    def _events_for_source(self, source: str, bursting: bool) -> int:
        p = self.profile
        base_per_tick = (p.events_per_minute / 60) * self.tick_seconds

        if not bursting:
            count = base_per_tick
        elif p.spike_source is not None and source != p.spike_source:
            # Only the spike_source gets the burst; others stay calm
            count = base_per_tick
        else:
            count = base_per_tick * p.burst_multiplier

        # Stochastic rounding: e.g. 2.3 → 2 with 70% chance, 3 with 30%
        floored = int(count)
        remainder = count - floored
        return floored + (1 if random.random() < remainder else 0)

    def build_batch(self) -> list[dict[str, Any]]:
        bursting = self._is_bursting()
        batch: list[dict[str, Any]] = []

        for source in self.profile.source_names:
            n = self._events_for_source(source, bursting)
            for _ in range(n):
                batch.append({
                    "level": self._pick_level(),
                    "message": f"[{source}] synthetic log event",
                    "source_id": None,   # API resolves source by name via payload tag
                    "payload": {"source_name": source, "profile": self.profile.name},
                })

        return batch

    async def tick(self) -> None:
        batch = self.build_batch()
        if not batch:
            return

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.post(
                    f"{self.api_url}/api/v1/events/batch",
                    json=batch,
                    headers={"X-API-Key": self.api_key},
                )
                if resp.status_code == 201:
                    logger.debug("Batch sent: %d events (bursting=%s)", len(batch), self._is_bursting())
                else:
                    logger.warning("Batch POST returned %s: %s", resp.status_code, resp.text[:200])
        except httpx.RequestError as exc:
            logger.warning("Batch POST failed (will retry next tick): %s", exc)
