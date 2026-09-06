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
        )


settings = Settings.from_env
