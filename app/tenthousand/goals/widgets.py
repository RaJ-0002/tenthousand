from __future__ import annotations

from typing import Callable

import flet as ft

from ..timer.engine import format_hms, live_display_seconds, progress_fraction
from ..ui import theme
from .models import Goal


class GoalCard(ft.Container):
    """One goal on the dashboard: title, progress ring, live HH:MM:SS, and
    the only controls the spec allows: Start/Pause/Resume/Archive/Achieve.
    Live numbers are computed client-side via timer.engine for smooth
    ticking; the source of truth is whatever the last server response said.
    """

    def __init__(
        self,
        goal: Goal,
        on_start: Callable[[Goal], None],
        on_pause: Callable[[Goal], None],
        on_resume: Callable[[Goal], None],
        on_archive: Callable[[Goal], None],
        on_achieve: Callable[[Goal], None],
    ) -> None:
        super().__init__()
        self.goal = goal
        self._on_start = on_start
        self._on_pause = on_pause
        self._on_resume = on_resume
        self._on_archive = on_archive
        self._on_achieve = on_achieve

        self.bgcolor = theme.SURFACE
        self.border = ft.Border.all(1, theme.BORDER)
        self.border_radius = 16
        self.padding = 20
        self.margin = ft.Margin.only(bottom=12)

        self._time_text = ft.Text(size=28, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY)
        self._progress_bar = ft.ProgressBar(width=None, bgcolor=theme.SURFACE_ALT, color=theme.ACCENT)
        self._status_text = ft.Text(size=12, color=theme.TEXT_MUTED)

        self.content = ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    [
                        ft.Text(goal.title, size=18, weight=ft.FontWeight.W_600, color=theme.TEXT_PRIMARY),
                        self._status_pill(),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self._time_text,
                self._progress_bar,
                self._status_text,
                self._controls_row(),
            ],
        )
        self.refresh(goal)

    def _status_pill(self) -> ft.Container:
        if self.goal.is_achieved:
            label, color = "Achieved", theme.SUCCESS
        elif self.goal.is_running:
            label, color = "Running", theme.ACCENT
        else:
            label, color = "Paused", theme.WARNING
        return ft.Container(
            content=ft.Text(label, size=11, weight=ft.FontWeight.W_600, color=color),
            bgcolor=theme.SURFACE_ALT,
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=999,
        )

    def _controls_row(self) -> ft.Row:
        buttons: list[ft.Control] = []
        if self.goal.is_achieved:
            pass
        elif self.goal.is_running:
            buttons.append(
                ft.FilledButton("Pause", icon=ft.Icons.PAUSE, on_click=lambda e: self._on_pause(self.goal))
            )
        else:
            action, label, icon = (
                (self._on_resume, "Resume", ft.Icons.PLAY_ARROW)
                if self.goal.accumulated_seconds > 0
                else (self._on_start, "Start", ft.Icons.PLAY_ARROW)
            )
            buttons.append(ft.FilledButton(label, icon=icon, on_click=lambda e: action(self.goal)))

        if not self.goal.is_achieved:
            buttons.append(
                ft.OutlinedButton(
                    "Achieve", icon=ft.Icons.FLAG, on_click=lambda e: self._on_achieve(self.goal)
                )
            )
        buttons.append(
            ft.TextButton(
                "Archive",
                icon=ft.Icons.ARCHIVE_OUTLINED,
                on_click=lambda e: self._on_archive(self.goal),
            )
        )
        return ft.Row(buttons, spacing=8)

    def refresh(self, goal: Goal) -> None:
        self.goal = goal
        seconds = live_display_seconds(
            _as_engine_state(goal),
        )
        self._time_text.value = format_hms(seconds)
        self._progress_bar.value = progress_fraction(seconds)
        pct = progress_fraction(seconds) * 100
        self._status_text.value = f"{pct:.4f}% of 10,000 hours"


def _as_engine_state(goal: Goal):
    from ..timer.engine import GoalState

    return GoalState(
        accumulated_seconds=goal.accumulated_seconds,
        is_running=goal.is_running,
        started_at=goal.started_at,
        last_paused_at=goal.last_paused_at,
        last_decay_applied_at=goal.last_decay_applied_at,
        is_archived=goal.is_archived,
        is_achieved=goal.is_achieved,
    )
