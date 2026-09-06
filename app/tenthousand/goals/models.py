from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Goal:
    id: str
    user_id: str
    title: str
    accumulated_seconds: int
    started_at: datetime | None
    last_paused_at: datetime | None
    last_decay_applied_at: datetime | None
    is_running: bool
    is_archived: bool
    is_achieved: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict) -> "Goal":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            accumulated_seconds=int(row["accumulated_seconds"]),
            started_at=_parse_ts(row.get("started_at")),
            last_paused_at=_parse_ts(row.get("last_paused_at")),
            last_decay_applied_at=_parse_ts(row.get("last_decay_applied_at")),
            is_running=bool(row["is_running"]),
            is_archived=bool(row["is_archived"]),
            is_achieved=bool(row["is_achieved"]),
            created_at=_parse_ts(row["created_at"]),
            updated_at=_parse_ts(row["updated_at"]),
        )
