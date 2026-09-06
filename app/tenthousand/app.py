from __future__ import annotations

import asyncio

import flet as ft

from .auth.screens import AuthScreen
from .auth.service import AuthResult, AuthService
from .goals.screens import DashboardScreen
from .goals.service import GoalsService
from .ui.theme import configure_page

TICK_SECONDS = 1


class TenThousandApp:
    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self._auth_service = AuthService()
        self._goals_service = GoalsService()
        self._dashboard: DashboardScreen | None = None
        self._tick_task: asyncio.Task | None = None

        configure_page(page)
        self._show_auth()

    def _show_auth(self) -> None:
        self._stop_ticking()
        self.page.controls.clear()
        self.page.add(AuthScreen(self._auth_service, on_authenticated=self._on_authenticated))
        self.page.update()

    def _on_authenticated(self, result: AuthResult) -> None:
        self._show_dashboard()

    def _show_dashboard(self) -> None:
        self.page.controls.clear()
        self._dashboard = DashboardScreen(self._goals_service, on_delete_account=self._on_delete_account)
        self.page.add(self._dashboard)
        self.page.update()
        self._start_ticking()

    def _on_delete_account(self) -> None:
        self._auth_service.delete_account()
        self._show_auth()

    def _start_ticking(self) -> None:
        self._tick_task = self.page.run_task(self._tick_loop)

    def _stop_ticking(self) -> None:
        if self._tick_task is not None:
            self._tick_task.cancel()
            self._tick_task = None

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_SECONDS)
            if self._dashboard is not None:
                self._dashboard.tick()


def main(page: ft.Page) -> None:
    TenThousandApp(page)
