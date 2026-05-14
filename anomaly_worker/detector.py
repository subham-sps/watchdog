"""
Pure z-score anomaly detector — no DB, no side effects.

Takes a list of historical window counts (baseline) and the current window
count, returns a ZScoreResult or None if detection is not possible.

Rules:
  - Minimum 4 baseline windows required (< 4 → None)
  - Zero standard deviation → None (no variance, can't detect anomaly)
  - z = (current - mean) / stddev
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ZScoreResult:
    z_score: float
    current_count: int
    baseline_mean: float
    baseline_stddev: float
    is_spike: bool


MIN_BASELINE_WINDOWS = 4


def compute_zscore(
    baseline_counts: list[int],
    current_count: int,
    threshold: float,
) -> ZScoreResult | None:
    """
    Args:
        baseline_counts: event counts for each of the N preceding windows.
        current_count:   event count for the window being evaluated.
        threshold:       z-score value at or above which is_spike=True.

    Returns:
        ZScoreResult if computable, None otherwise.
    """
    if len(baseline_counts) < MIN_BASELINE_WINDOWS:
        return None

    n = len(baseline_counts)
    mean = sum(baseline_counts) / n
    variance = sum((x - mean) ** 2 for x in baseline_counts) / n
    stddev = math.sqrt(variance)

    if stddev == 0:
        return None

    z = (current_count - mean) / stddev

    return ZScoreResult(
        z_score=round(z, 4),
        current_count=current_count,
        baseline_mean=round(mean, 4),
        baseline_stddev=round(stddev, 4),
        is_spike=(z >= threshold),
    )
