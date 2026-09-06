from __future__ import annotations

import flet as ft

from ..ui import theme
from .service import AuthService


class AuthScreen(ft.Column):
    """Email/password sign in + sign up, OTP-based password reset, and a
    Google sign-in button. Kept intentionally simple; wire real redirect
    handling for OAuth once a Supabase project + Google OAuth client exist.
    """

    def __init__(self, auth_service: AuthService, on_authenticated: callable) -> None:
        super().__init__(expand=True, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        self._auth = auth_service
        self._on_authenticated = on_authenticated
        self._mode = "sign_in"  # sign_in | sign_up | reset_request | reset_verify

        self._email = ft.TextField(label="Email", width=340, bgcolor=theme.SURFACE, border_color=theme.BORDER)
        self._password = ft.TextField(label="Password", password=True, can_reveal_password=True, width=340, bgcolor=theme.SURFACE, border_color=theme.BORDER)
        self._otp = ft.TextField(label="OTP code", width=340, visible=False, bgcolor=theme.SURFACE, border_color=theme.BORDER)
        self._error = ft.Text("", color=theme.DANGER, size=12)

        self._primary_button = ft.FilledButton("Sign in", width=340, on_click=self._on_primary)
        self._google_button = ft.OutlinedButton("Continue with Google", width=340, icon=ft.Icons.G_MOBILEDATA, on_click=self._on_google)
        self._switch_mode_button = ft.TextButton("Need an account? Sign up", on_click=self._toggle_sign_up)
        self._forgot_button = ft.TextButton("Forgot password?", on_click=self._start_reset)

        self.controls = [
            ft.Container(
                bgcolor=theme.SURFACE,
                border=ft.Border.all(1, theme.BORDER),
                border_radius=20,
                padding=32,
                content=ft.Column(
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text("TenThousand", size=24, weight=ft.FontWeight.BOLD, color=theme.TEXT_PRIMARY),
                        ft.Text("10,000 hours. One goal at a time.", size=12, color=theme.TEXT_MUTED),
                        self._email,
                        self._password,
                        self._otp,
                        self._error,
                        self._primary_button,
                        self._google_button,
                        ft.Row([self._forgot_button, self._switch_mode_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ],
                ),
            )
        ]

    def _set_error(self, message: str) -> None:
        self._error.value = message
        self.update()

    def _on_primary(self, e: ft.ControlEvent) -> None:
        try:
            if self._mode == "sign_in":
                result = self._auth.sign_in_with_password(self._email.value, self._password.value)
                self._on_authenticated(result)
            elif self._mode == "sign_up":
                result = self._auth.sign_up_with_password(self._email.value, self._password.value)
                self._on_authenticated(result)
            elif self._mode == "reset_request":
                self._auth.request_password_reset_otp(self._email.value)
                self._mode = "reset_verify"
                self._otp.visible = True
                self._primary_button.content = "Verify code & reset"
                self.update()
            elif self._mode == "reset_verify":
                result = self._auth.verify_reset_otp(self._email.value, self._otp.value, self._password.value)
                self._on_authenticated(result)
        except Exception as ex:  # surfaced to the user, not swallowed
            self._set_error(str(ex))

    def _on_google(self, e: ft.ControlEvent) -> None:
        try:
            url = self._auth.google_oauth_url(redirect_to=self.page.route or "/")

            async def _open() -> None:
                await self.page.launch_url(url)

            self.page.run_task(_open)
        except Exception as ex:
            self._set_error(str(ex))

    def _toggle_sign_up(self, e: ft.ControlEvent) -> None:
        self._mode = "sign_up" if self._mode == "sign_in" else "sign_in"
        self._primary_button.content = "Sign up" if self._mode == "sign_up" else "Sign in"
        self._switch_mode_button.content = (
            "Already have an account? Sign in" if self._mode == "sign_up" else "Need an account? Sign up"
        )
        self._otp.visible = False
        self.update()

    def _start_reset(self, e: ft.ControlEvent) -> None:
        self._mode = "reset_request"
        self._primary_button.content = "Send reset code"
        self.update()
