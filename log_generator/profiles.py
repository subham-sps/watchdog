"""
Traffic profiles — pure data, no I/O.

Each profile defines the shape of simulated traffic. The generator reads
a profile and decides how many events to emit per tick, which level to use,
and which source to target.

Fields:
  events_per_minute   Baseline emission rate across all sources.
  level_weights       Weighted distribution of log levels (must sum to 100).
  source_names        Sources to rotate through. The generator round-robins
                      them during normal traffic.
  burst_every_minutes How often (in minutes) a burst starts. None = no bursts.
  burst_multiplier    How many times the normal rate to emit during a burst.
  burst_duration_secs How long each burst lasts (seconds).
  spike_source        If set, only this source is elevated during a burst.
                      All other sources continue at the normal rate.
                      If None, all sources are elevated equally.
  burst_once          If True, the burst fires exactly once then never again.
                      Use for spike profiles that should melt down once then
                      return to calm. burst profile uses False (recurring).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    name: str
    events_per_minute: int
    level_weights: dict[str, int]
    source_names: list[str]
    burst_every_minutes: int | None = None
    burst_multiplier: float = 1.0
    burst_duration_secs: int = 30
    spike_source: str | None = None
    burst_once: bool = False

    def __post_init__(self):
        if sum(self.level_weights.values()) != 100:
            raise ValueError(f"Profile '{self.name}': level_weights must sum to 100")
        if self.burst_once and self.burst_every_minutes is None:
            raise ValueError(f"Profile '{self.name}': burst_once=True requires burst_every_minutes")
        if self.spike_source and self.spike_source not in self.source_names:
            raise ValueError(
                f"Profile '{self.name}': spike_source '{self.spike_source}' "
                f"not in source_names {self.source_names}"
            )


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------

NORMAL = Profile(
    name="normal",
    events_per_minute=12,
    level_weights={"debug": 20, "info": 60, "warning": 15, "error": 4, "critical": 1},
    source_names=["app-server", "worker", "scheduler"],
)

BURST = Profile(
    name="burst",
    events_per_minute=12,
    level_weights={"debug": 10, "info": 40, "warning": 30, "error": 15, "critical": 5},
    source_names=["app-server", "worker", "scheduler"],
    burst_every_minutes=3,
    burst_multiplier=8.0,
    burst_duration_secs=45,
    spike_source=None,   # all sources elevated
    burst_once=False,
)

SPIKE = Profile(
    name="spike",
    events_per_minute=12,
    level_weights={"debug": 5, "info": 15, "warning": 20, "error": 45, "critical": 15},
    source_names=["app-server", "worker", "scheduler"],
    burst_every_minutes=1,
    burst_multiplier=20.0,
    burst_duration_secs=60,
    spike_source="app-server",  # only app-server melts down
    burst_once=True,
)

NOISY = Profile(
    name="noisy",
    events_per_minute=120,
    level_weights={"debug": 20, "info": 20, "warning": 20, "error": 20, "critical": 20},
    source_names=["app-server", "worker", "scheduler", "gateway", "cache"],
)

PROFILES: dict[str, Profile] = {
    p.name: p for p in [NORMAL, BURST, SPIKE, NOISY]
}
