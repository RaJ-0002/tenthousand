from __future__ import annotations

import flet as ft

from ..ui import theme
from .models import Goal
from .service import GoalsService
from .widgets import GoalCard


class DashboardScreen(ft.Column):
    def __init__(self, goals_service: GoalsService, on_delete_account: callable) -> None:
        super().__init__(expand=True, spacing=0)
        self._service = goals_service
        self._on_delete_account = on_delete_account
        self._cards: dict[str, GoalCard] = {}

        self._title_field = ft.TextField(
            hint_text="New goal title (e.g. Master Python)",
            expand=True,
            bgcolor=theme.SURFACE,
            border_color=theme.BORDER,
            color=theme.TEXT_PRIMARY,
        )
        self._list_column = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self._show_archived = ft.Switch(label="Show archived", value=False, on_change=self._reload_sync)

        self.controls = [
            ft.Container(
                padding=20,
                content=ft.Column(
                    spacing=16,
                    controls=[
                        ft.Row(
                            [
                                ft.Text("TenThousand", size=26, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_FOREVER_OUTLINED,
                                    icon_color=theme.DANGER,
                                    tooltip="Delete account",
                                    on_click=self._confirm_delete_account,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Row([self._title_field, ft.FilledButton("Add goal", on_click=self._create_goal)]),
                        self._show_archived,
                    ],
                ),
            ),
            ft.Container(content=self._list_column, padding=ft.Padding.symmetric(horizontal=20), expand=True),
        ]

    def did_mount(self) -> None:
        self.page.run_task(self.reload)

    async def reload(self) -> None:
        goals = self._service.list_goals(include_archived=self._show_archived.value)
        self._render(goals)

    def _reload_sync(self, e: ft.ControlEvent) -> None:
        self.page.run_task(self.reload)

    def _render(self, goals: list[Goal]) -> None:
        self._list_column.controls.clear()
        self._cards.clear()
        for g in goals:
            card = GoalCard(
                g,
                on_start=self._start,
                on_pause=self._pause,
                on_resume=self._resume,
                on_archive=self._archive,
                on_achieve=self._achieve,
            )
            self._cards[g.id] = card
            self._list_column.controls.append(card)
        if self.page:
            self.update()

    def _create_goal(self, e: ft.ControlEvent) -> None:
        title = self._title_field.value.strip()
        if not title:
            return
        self._service.create_goal(title)
        self._title_field.value = ""
        self.page.run_task(self.reload)

    def _start(self, goal: Goal) -> None:
        self._service.start(goal.id)
        self.page.run_task(self.reload)

    def _pause(self, goal: Goal) -> None:
        self._service.pause(goal.id)
        self.page.run_task(self.reload)

    def _resume(self, goal: Goal) -> None:
        self._service.resume(goal.id)
        self.page.run_task(self.reload)

    def _archive(self, goal: Goal) -> None:
        self._service.archive(goal.id)
        self.page.run_task(self.reload)

    def _achieve(self, goal: Goal) -> None:
        self._service.mark_achieved(goal.id)
        self.page.run_task(self.reload)

    def tick(self) -> None:
        """Called on a timer to smoothly update running goals' displayed
        time client-side, without a network round trip. Does NOT mutate
        anything server-side -- see timer/engine.py.
        """
        for card in self._cards.values():
            if card.goal.is_running:
                card.refresh(card.goal)
        if self.page:
            self.update()

    def _confirm_delete_account(self, e: ft.ControlEvent) -> None:
        def confirm(e2: ft.ControlEvent) -> None:
            self.page.pop_dialog()
            self._on_delete_account()

        def cancel(e2: ft.ControlEvent) -> None:
            self.page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete account?"),
            content=ft.Text(
                "This permanently deletes your profile and every goal's recorded "
                "hours. There is no backup and no way to undo this."
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel),
                ft.FilledButton("Delete permanently", on_click=confirm, bgcolor=theme.DANGER),
            ],
        )
        self.page.show_dialog(dlg)
