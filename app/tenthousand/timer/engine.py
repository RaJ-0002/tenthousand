"""Pure-Python mirror of the SQL timer engine (supabase/migrations/0002_timer_engine.sql).

This module is NOT authoritative. It exists for two things only:
  1. Smooth client-side display between server syncs (e.g. ticking a running
     goal's counter every second without hitting the network).
  2. Unit tests that pin down the auto-pause/decay math against the spec.

The server (evaluate_goal in Postgres) is always the source of truth; the
app must reconcile against the server's response on every fetch/mutation
and never persist a value computed only here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

SECONDS_PER_HOUR = 3600
GOAL_HOURS = 10_000
GOAL_SECONDS = GOAL_HOURS * SECONDS_PER_HOUR  # 36,000,000
AUTO_PAUSE_SECONDS = 6 * SECONDS_PER_HOUR  # 21,600
INACTIVITY_THRESHOLD_SECONDS = 72 * SECONDS_PER_HOUR  # 259,200
DECAY_RATE = 0.5


@dataclass(frozen=True)
class GoalState:
    accumulated_seconds: int
    is_running: bool
    started_at: datetime | None
    last_paused_at: datetime | None
    last_decay_applied_at: datetime | None
    is_archived: bool = False
    is_achieved: bool = False


def compute_running_credit(started_at: datetime, now: datetime) -> tuple[int, bool]:
    """Seconds to credit for a run in progress, clamped to the 6h cap.

    Returns (seconds, hit_auto_pause_cap).
    """
    raw = (now - started_at).total_seconds()
    if raw >= AUTO_PAUSE_SECONDS:
        return AUTO_PAUSE_SECONDS, True
    return max(0, int(raw)), False


def compute_decayed_total(
    accumulated_seconds: int,
    last_paused_at: datetime,
    last_decay_applied_at: datetime | None,
    now: datetime,
) -> int:
    """Accumulated seconds after applying reverse-decay, floored at zero.

    Decay only kicks in once the goal has been paused for more than 72h,
    and runs at 0.5x real time from that point on. `last_decay_applied_at`
    anchors the window so repeated calls (server on-fetch, cron sweep,
    client display) never double-count an already-applied window.
    """
    paused_seconds = (now - last_paused_at).total_seconds()
    if paused_seconds <= INACTIVITY_THRESHOLD_SECONDS:
        return accumulated_seconds

    threshold_mark = last_paused_at + timedelta(seconds=INACTIVITY_THRESHOLD_SECONDS)
    anchor = max(last_decay_applied_at or last_paused_at, threshold_mark)
    window_seconds = max(0.0, (now - anchor).total_seconds())
    decay_seconds = math.floor(window_seconds * DECAY_RATE)
    return max(0, accumulated_seconds - decay_seconds)


def live_display_seconds(state: GoalState, now: datetime | None = None) -> int:
    """Best-effort seconds to show in the UI right now, without a round trip."""
    now = now or datetime.now(timezone.utc)

    if state.is_archived or state.is_achieved:
        return min(state.accumulated_seconds, GOAL_SECONDS)

    if state.is_running and state.started_at is not None:
        credit, _hit_cap = compute_running_credit(state.started_at, now)
        total = state.accumulated_seconds + credit
    elif not state.is_running and state.last_paused_at is not None:
        total = compute_decayed_total(
            state.accumulated_seconds, state.last_paused_at, state.last_decay_applied_at, now
        )
    else:
        total = state.accumulated_seconds

    return min(total, GOAL_SECONDS)


def progress_fraction(seconds: int) -> float:
    return min(1.0, max(0.0, seconds / GOAL_SECONDS))


def format_hms(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:,}:{minutes:02d}:{secs:02d}"
