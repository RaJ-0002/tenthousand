"""App configuration loaded from environment (.env in local dev)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_anon_key: str
    google_web_client_id: str | None
    app_base_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set (see .env.example). "
                "Only the anon key belongs in this app -- never the service_role key."
            )
        return cls(
            supabase_url=url,
            supabase_anon_key=key,
            google_web_client_id=os.environ.get("GOOGLE_WEB_CLIENT_ID"),
            # Used as the OAuth redirect target. Flet's Page.url exposes the
            # internal ws:// transport address, not a browser-usable http(s)
            # URL, so this must be set explicitly to wherever the app is
            # actually reachable -- and it must match (or be listed under)
            # Supabase's Auth > URL Configuration > Redirect URLs, or
            # Supabase silently falls back to its default Site URL.
            app_base_url=os.environ.get("APP_BASE_URL", "http://127.0.0.1:8550"),
        )


settings = Settings.from_env
