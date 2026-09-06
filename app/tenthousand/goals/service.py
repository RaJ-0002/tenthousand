"""Client-side wrapper around the goal RPCs in supabase/migrations/0002.

Every mutating call here is a thin passthrough to a security-definer
Postgres function -- this module has no timer math of its own. That keeps
the anti-cheat boundary at the database, not the client.
"""

from __future__ import annotations

from ..supabase_client import get_client
from .models import Goal


class GoalsService:
    def __init__(self) -> None:
        self._client = get_client()

    def list_goals(self, include_archived: bool = False) -> list[Goal]:
        res = self._client.rpc(
            "list_my_goals", {"p_include_archived": include_archived}
        ).execute()
        return [Goal.from_row(row) for row in res.data]

    def create_goal(self, title: str) -> Goal:
        res = self._client.rpc("create_goal", {"p_title": title}).execute()
        return Goal.from_row(res.data[0] if isinstance(res.data, list) else res.data)

    def start(self, goal_id: str) -> Goal:
        return self._call_returning_goal("start_goal", goal_id)

    def resume(self, goal_id: str) -> Goal:
        return self._call_returning_goal("resume_goal", goal_id)

    def pause(self, goal_id: str) -> Goal:
        return self._call_returning_goal("pause_goal", goal_id)

    def archive(self, goal_id: str) -> Goal:
        return self._call_returning_goal("archive_goal", goal_id)

    def mark_achieved(self, goal_id: str) -> Goal:
        return self._call_returning_goal("mark_goal_achieved", goal_id)

    def _call_returning_goal(self, rpc_name: str, goal_id: str) -> Goal:
        res = self._client.rpc(rpc_name, {"p_goal_id": goal_id}).execute()
        row = res.data[0] if isinstance(res.data, list) else res.data
        return Goal.from_row(row)
