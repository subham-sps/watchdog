"""Pure unit tests for the z-score detector — no DB, no async."""
import pytest
from anomaly_worker.detector import compute_zscore, MIN_BASELINE_WINDOWS, ZScoreResult


def test_min_baseline_windows_is_four():
    assert MIN_BASELINE_WINDOWS == 4


def test_returns_none_below_min_baseline():
    assert compute_zscore([10, 10, 10], current_count=50, threshold=3.0) is None


def test_returns_none_on_empty_baseline():
    assert compute_zscore([], current_count=50, threshold=3.0) is None


def test_returns_none_on_zero_stddev():
    # All identical counts → stddev == 0
    assert compute_zscore([10, 10, 10, 10, 10], current_count=10, threshold=3.0) is None


def test_normal_traffic_no_spike():
    baseline = [10, 11, 9, 10, 10]
    result = compute_zscore(baseline, current_count=11, threshold=3.0)
    assert result is not None
    assert result.is_spike is False


def test_spike_detected():
    baseline = [10, 10, 10, 10, 10, 9, 11]
    result = compute_zscore(baseline, current_count=100, threshold=3.0)
    assert result is not None
    assert result.is_spike is True
    assert result.z_score > 3.0


def test_zscore_value_correct():
    # mean=10, stddev=0 would be excluded, use slight variation
    baseline = [8, 10, 12, 10]   # mean=10, variance=2, stddev=sqrt(2)≈1.414
    result = compute_zscore(baseline, current_count=14, threshold=3.0)
    assert result is not None
    import math
    expected_z = (14 - 10) / math.sqrt(2)
    assert abs(result.z_score - round(expected_z, 4)) < 0.001
    assert result.baseline_mean == 10.0
    assert result.current_count == 14


def test_spike_exactly_at_threshold():
    # baseline=[8,10,12,10]: mean=10, stddev=sqrt(2)≈1.414
    # current=15 → z=(15-10)/sqrt(2)≈3.54 >= 3.0
    baseline = [8, 10, 12, 10]
    result = compute_zscore(baseline, current_count=15, threshold=3.0)
    assert result is not None
    assert result.is_spike is True


def test_returns_zscore_result_type():
    baseline = [10, 12, 8, 11, 9]
    result = compute_zscore(baseline, current_count=50, threshold=3.0)
    assert isinstance(result, ZScoreResult)


def test_exactly_four_baseline_windows_allowed():
    baseline = [10, 10, 10, 14]  # exactly MIN_BASELINE_WINDOWS
    result = compute_zscore(baseline, current_count=10, threshold=3.0)
    # Should not return None — 4 windows is sufficient
    assert result is not None


def test_below_threshold_is_not_spike():
    # baseline=[8,10,12,10]: mean=10, stddev=sqrt(2)≈1.414
    # current=11 → z=(11-10)/sqrt(2)≈0.71 < 3.0
    baseline = [8, 10, 12, 10]
    result = compute_zscore(baseline, current_count=11, threshold=3.0)
    assert result is not None
    assert result.is_spike is False
