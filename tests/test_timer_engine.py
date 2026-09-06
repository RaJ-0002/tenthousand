import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from tenthousand.timer.engine import (
    AUTO_PAUSE_SECONDS,
    GOAL_SECONDS,
    GoalState,
    compute_decayed_total,
    compute_running_credit,
    format_hms,
    live_display_seconds,
    progress_fraction,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_running_credit_below_cap():
    started = NOW - timedelta(hours=2)
    credit, hit_cap = compute_running_credit(started, NOW)
    assert credit == 2 * 3600
    assert hit_cap is False


def test_running_credit_clamps_at_six_hours():
    started = NOW - timedelta(hours=9)
    credit, hit_cap = compute_running_credit(started, NOW)
    assert credit == AUTO_PAUSE_SECONDS
    assert hit_cap is True


def test_no_decay_before_72h_threshold():
    paused_at = NOW - timedelta(hours=71)
    total = compute_decayed_total(10 * 3600, paused_at, None, NOW)
    assert total == 10 * 3600


def test_decay_exact_spec_example():
    # "10 accumulated hours decay to 0 in 20 hours [past the 72h mark]"
    paused_at = NOW - timedelta(hours=72 + 20)
    total = compute_decayed_total(10 * 3600, paused_at, None, NOW)
    assert total == 0


def test_decay_floors_at_zero_and_never_goes_negative():
    paused_at = NOW - timedelta(hours=72 + 1000)
    total = compute_decayed_total(1 * 3600, paused_at, None, NOW)
    assert total == 0


def test_decay_is_incremental_via_last_decay_applied_at():
    # First evaluation: 10h past the 72h mark decays 5h off a 10h balance.
    paused_at = NOW - timedelta(hours=72 + 10)
    mid = compute_decayed_total(10 * 3600, paused_at, None, NOW)
    assert mid == 5 * 3600

    # A second evaluation anchored at `NOW` (as if the cron already applied
    # decay up to here) with no further elapsed time must not decay again.
    still = compute_decayed_total(mid, paused_at, NOW, NOW)
    assert still == mid


def test_live_display_seconds_running():
    state = GoalState(
        accumulated_seconds=5 * 3600,
        is_running=True,
        started_at=NOW - timedelta(hours=1),
        last_paused_at=None,
        last_decay_applied_at=None,
    )
    assert live_display_seconds(state, NOW) == 6 * 3600


def test_live_display_seconds_clamps_at_goal():
    state = GoalState(
        accumulated_seconds=GOAL_SECONDS - 100,
        is_running=True,
        started_at=NOW - timedelta(hours=1),
        last_paused_at=None,
        last_decay_applied_at=None,
    )
    assert live_display_seconds(state, NOW) == GOAL_SECONDS


def test_progress_fraction():
    assert progress_fraction(0) == 0.0
    assert progress_fraction(GOAL_SECONDS) == 1.0
    assert progress_fraction(GOAL_SECONDS * 2) == 1.0


def test_format_hms():
    assert format_hms(0) == "0:00:00"
    assert format_hms(3661) == "1:01:01"
    assert format_hms(GOAL_SECONDS) == "10,000:00:00"
