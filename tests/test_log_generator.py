"""
Unit tests for the log generator.
No DB, no real HTTP — generator logic and profile correctness only.
"""
import pytest
import random
from unittest.mock import AsyncMock, MagicMock, patch

from log_generator.profiles import Profile, PROFILES, NORMAL, BURST, SPIKE, NOISY
from log_generator.generator import GeneratorState


# ---------------------------------------------------------------------------
# Profile validation
# ---------------------------------------------------------------------------

def test_all_builtin_profiles_level_weights_sum_to_100():
    for name, profile in PROFILES.items():
        total = sum(profile.level_weights.values())
        assert total == 100, f"Profile '{name}' level_weights sum to {total}, expected 100"


def test_profile_rejects_weights_not_summing_to_100():
    with pytest.raises(ValueError, match="sum to 100"):
        Profile(
            name="bad",
            events_per_minute=10,
            level_weights={"info": 50, "error": 30},  # sums to 80
            source_names=["src"],
        )


def test_profile_rejects_burst_once_without_burst_every():
    with pytest.raises(ValueError, match="burst_every_minutes"):
        Profile(
            name="bad",
            events_per_minute=10,
            level_weights={"info": 100},
            source_names=["src"],
            burst_once=True,
            burst_every_minutes=None,
        )


def test_profile_rejects_spike_source_not_in_source_names():
    with pytest.raises(ValueError, match="spike_source"):
        Profile(
            name="bad",
            events_per_minute=10,
            level_weights={"info": 100},
            source_names=["src-a"],
            burst_every_minutes=5,
            spike_source="nonexistent",
        )


def test_spike_profile_has_burst_once():
    assert SPIKE.burst_once is True


def test_burst_profile_does_not_have_burst_once():
    assert BURST.burst_once is False


def test_normal_profile_has_no_burst():
    assert NORMAL.burst_every_minutes is None


# ---------------------------------------------------------------------------
# Level weight distribution
# ---------------------------------------------------------------------------

def test_pick_level_respects_weights():
    """Over 2000 draws the level distribution should be within ±10pp of declared weights."""
    random.seed(42)
    state = GeneratorState(profile=NORMAL, api_url="http://x", api_key="k")
    draws = [state._pick_level() for _ in range(2000)]
    for level, weight in NORMAL.level_weights.items():
        actual_pct = draws.count(level) / len(draws) * 100
        assert abs(actual_pct - weight) < 10, (
            f"Level '{level}': expected ~{weight}%, got {actual_pct:.1f}%"
        )


def test_pick_level_only_returns_declared_levels():
    state = GeneratorState(profile=NORMAL, api_url="http://x", api_key="k")
    for _ in range(100):
        assert state._pick_level() in NORMAL.level_weights


# ---------------------------------------------------------------------------
# Burst / spike_source targeting
# ---------------------------------------------------------------------------

def _make_state(profile: Profile, elapsed: float = 0.0) -> GeneratorState:
    state = GeneratorState(profile=profile, api_url="http://x", api_key="k", tick_seconds=5)
    # Monkey-patch elapsed so we can control burst timing
    state._started_at = state._started_at - elapsed
    return state


def test_normal_profile_never_bursts():
    state = _make_state(NORMAL, elapsed=0)
    assert state._is_bursting() is False
    state2 = _make_state(NORMAL, elapsed=999)
    assert state2._is_bursting() is False


def test_burst_profile_is_bursting_at_start_of_cycle():
    # At elapsed=0, position_in_cycle=0 < burst_duration_secs → bursting
    state = _make_state(BURST, elapsed=0)
    assert state._is_bursting() is True


def test_burst_profile_not_bursting_after_duration():
    # After burst_duration_secs have passed, no longer bursting
    state = _make_state(BURST, elapsed=BURST.burst_duration_secs + 1)
    assert state._is_bursting() is False


def test_spike_source_targets_only_nominated_source():
    """During a burst, only the spike_source gets elevated; others stay at base rate."""
    state = _make_state(SPIKE, elapsed=0)  # bursting at t=0
    assert state._is_bursting() is True

    # spike_source should get burst_multiplier × base rate
    spike_count = state._events_for_source(SPIKE.spike_source, bursting=True)
    # calm source should get base rate only
    calm_source = next(s for s in SPIKE.source_names if s != SPIKE.spike_source)
    calm_count = state._events_for_source(calm_source, bursting=True)

    # Use large tick to make counts deterministic enough for comparison
    big_state = GeneratorState(
        profile=SPIKE, api_url="http://x", api_key="k", tick_seconds=60
    )
    big_state._started_at -= 0  # t=0, bursting
    spike_big = big_state._events_for_source(SPIKE.spike_source, bursting=True)
    calm_big = big_state._events_for_source(calm_source, bursting=True)
    assert spike_big > calm_big * 2, (
        f"spike_source ({spike_big}) should be >> calm source ({calm_big})"
    )


def test_burst_once_fires_exactly_once():
    """burst_once profile: _is_bursting() returns True once, then always False."""
    state = _make_state(SPIKE, elapsed=0)  # inside first burst window
    first = state._is_bursting()
    assert first is True
    assert state._burst_fired is True

    # Subsequent calls within the burst window still return False (latch is set)
    second = state._is_bursting()
    assert second is False

    # Even if we reset elapsed to be inside another cycle, still False
    state._started_at -= SPIKE.burst_every_minutes * 60  # jump to next cycle
    third = state._is_bursting()
    assert third is False


def test_build_batch_contains_all_sources():
    state = GeneratorState(
        profile=NORMAL, api_url="http://x", api_key="k", tick_seconds=60
    )
    batch = state.build_batch()
    source_names_in_batch = {e["payload"]["source_name"] for e in batch}
    for src in NORMAL.source_names:
        assert src in source_names_in_batch


def test_build_batch_payload_schema():
    """Every event in the batch must have the fields EventCreate requires."""
    state = GeneratorState(
        profile=NORMAL, api_url="http://x", api_key="k", tick_seconds=60
    )
    batch = state.build_batch()
    assert len(batch) > 0
    for event in batch:
        assert "level" in event
        assert "message" in event
        assert event["level"] in {"debug", "info", "warning", "error", "critical"}
        assert isinstance(event["message"], str) and event["message"]


# ---------------------------------------------------------------------------
# HTTP behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tick_posts_batch_to_api():
    state = GeneratorState(
        profile=NORMAL, api_url="http://watchdog:8000", api_key="test-key", tick_seconds=60
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 201

    with patch("log_generator.generator.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await state.tick()

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert "/api/v1/events/batch" in call_kwargs[0][0]
    assert call_kwargs[1]["headers"]["X-API-Key"] == "test-key"
    sent_batch = call_kwargs[1]["json"]
    assert isinstance(sent_batch, list)
    assert len(sent_batch) > 0


@pytest.mark.asyncio
async def test_tick_survives_api_500():
    state = GeneratorState(
        profile=NORMAL, api_url="http://watchdog:8000", api_key="k", tick_seconds=60
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("log_generator.generator.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Should not raise
        await state.tick()


@pytest.mark.asyncio
async def test_tick_survives_connection_error():
    import httpx as real_httpx
    state = GeneratorState(
        profile=NORMAL, api_url="http://unreachable:9999", api_key="k", tick_seconds=60
    )

    with patch("log_generator.generator.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=real_httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Should not raise
        await state.tick()
