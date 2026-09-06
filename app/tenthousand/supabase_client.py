"""Single shared Supabase client for the app process.

Only ever constructed with the anon key. RLS + the security-definer RPCs in
supabase/migrations are what make that safe -- see 0003_rls_policies.sql.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from .config import settings


@lru_cache(maxsize=1)
def get_client() -> Client:
    s = settings()
    return create_client(s.supabase_url, s.supabase_anon_key)
