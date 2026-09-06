"""Auth flows: Google OAuth, email/password, email OTP password reset,
and account deletion.

This wraps Supabase Auth (gotrue-py). "One account per email" is enforced
server-side by the unique constraint on public.profiles.email plus Supabase
Auth's own unique constraint on auth.users.email -- signing up with an email
that already has a Google-linked account (or vice versa) is rejected by
Supabase Auth's identity linking, not by anything in this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..supabase_client import get_client


@dataclass(frozen=True)
class AuthResult:
    user_id: str
    email: str


class EmailConfirmationRequired(Exception):
    """Raised when sign-up succeeded but Supabase Auth requires the user to
    confirm their email before a session (and thus a usable JWT) exists.

    Until confirmed, the Supabase client has no access token, so every RPC
    call runs as the anonymous role and auth.uid() is null server-side --
    this must never be treated as "signed in".
    """


class AuthService:
    def __init__(self) -> None:
        self._client = get_client()

    # --- Email / password -------------------------------------------------

    def sign_up_with_password(self, email: str, password: str) -> AuthResult:
        res = self._client.auth.sign_up({"email": email, "password": password})
        if res.session is None:
            raise EmailConfirmationRequired(
                "Account created. Check your email to confirm it, then sign in."
            )
        return AuthResult(user_id=res.user.id, email=res.user.email)

    def sign_in_with_password(self, email: str, password: str) -> AuthResult:
        res = self._client.auth.sign_in_with_password({"email": email, "password": password})
        return AuthResult(user_id=res.user.id, email=res.user.email)

    def request_password_reset_otp(self, email: str) -> None:
        """Sends a one-time code to `email`. Confirm with `verify_reset_otp`."""
        self._client.auth.sign_in_with_otp({"email": email, "options": {"should_create_user": False}})

    def verify_reset_otp(self, email: str, token: str, new_password: str) -> AuthResult:
        res = self._client.auth.verify_otp({"email": email, "token": token, "type": "email"})
        self._client.auth.update_user({"password": new_password})
        return AuthResult(user_id=res.user.id, email=res.user.email)

    # --- Google OAuth --------------------------------------------------
    # Flet's web/Android targets open the returned URL in a browser/webview;
    # the redirect back into the app completes the session. Wire the actual
    # redirect handling in ui screens once a Supabase project + OAuth client
    # exist (needs real credentials, see README "Google OAuth setup").

    def google_oauth_url(self, redirect_to: str) -> str:
        res = self._client.auth.sign_in_with_oauth(
            {"provider": "google", "options": {"redirect_to": redirect_to}}
        )
        return res.url

    # --- Session / deletion -------------------------------------------

    def sign_out(self) -> None:
        self._client.auth.sign_out()

    def current_user(self) -> AuthResult | None:
        session = self._client.auth.get_session()
        if session is None or session.user is None:
            return None
        return AuthResult(user_id=session.user.id, email=session.user.email)

    def delete_account(self) -> None:
        """Hard-deletes the current user's profile, goals, timer_logs and
        auth record via the delete_my_account() RPC (0004_account_deletion.sql).
        Irreversible -- no backup/restore path, by design.
        """
        self._client.rpc("delete_my_account").execute()
        self.sign_out()
