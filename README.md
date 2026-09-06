# TenThousand

A 10,000-hour goal tracker. Python + Flet (compiles to Web and Android)
on top of Supabase (Postgres, Auth, `pg_cron`). No separate backend
server or TypeScript/Deno Edge Functions — all server-authoritative logic
(timers, 6h auto-pause, 72h reverse-decay, hard account deletion) lives in
Postgres functions, so it can't be bypassed by the client.

## Layout

```
supabase/migrations/   Schema + timer engine + RLS + cron, run in order
app/                    Flet app (Python)
tests/                  Pure-Python unit tests for the timer math
docs/                   Architecture notes
```

## Why this stack

- **Flet**: lets the whole client be Python while still producing a real
  Android APK and a Web build, per the "cross-platform Web + Android" ask.
- **Supabase**: Postgres (not Firestore) makes the interval/decay math and
  the account-deletion cascade simple to express correctly with row locks
  (`for update`) and `check` constraints. `pg_cron` lets the scheduled
  sweep run entirely in SQL, so nothing outside Postgres needs
  credentials to mutate goal state.

## Setup

### 1. Create a Supabase project
Create a project at supabase.com, then note its Project URL and anon key
(Project Settings → API).

### 2. Run the migrations
Using the Supabase CLI, from the repo root:
```
supabase link --project-ref YOUR-PROJECT-REF
supabase db push
```
This runs `supabase/migrations/0001`–`0005` in order. `0005` enables the
`pg_cron` extension and schedules `sweep_goal_timers()` every 15 minutes —
confirm `pg_cron` is available on your plan/region (it is on all Supabase
Postgres instances at the time of writing).

### 3. Enable Google OAuth (optional, for "Continue with Google")
1. In Google Cloud Console, create an OAuth client (Web application) with
   authorized redirect URI `https://YOUR-PROJECT-REF.supabase.co/auth/v1/callback`.
2. In Supabase Dashboard → Authentication → Providers → Google, enable it
   and paste that client's ID/secret.
3. In Supabase Dashboard → Authentication → URL Configuration, add
   `APP_BASE_URL` (see below, `http://127.0.0.1:8550` for local dev) under
   **Redirect URLs**. Supabase only redirects back to URLs on this list —
   anything else silently falls back to the default Site URL instead.

Supabase Auth links a Google sign-in to the same `auth.users` row as an
email/password account sharing that email, which is what gives you "one
account per email" across both methods.

### 4. Configure the app
```
cd app
cp .env.example .env
# fill in SUPABASE_URL / SUPABASE_ANON_KEY / APP_BASE_URL
pip install -e .
```
Never put the Supabase **service_role** key in this app — only the anon
key. The security-definer functions (including account deletion) run with
elevated privilege *inside* Postgres precisely so the client never needs
that key.

Run the local dev server on the fixed port matching `APP_BASE_URL` so the
Google OAuth redirect resolves correctly:
```
flet run main.py --web --port 8550
```

### 5. Run it
```
cd app
flet run main.py          # desktop dev preview
flet run main.py --web    # web dev preview
```

### 6. Build for release
```
flet build web
flet build apk            # Android, for Google Play
```

## Tests
```
pip install -r requirements-dev.txt
pytest tests/ -v
```
These pin the timer math (6h clamp, 72h+ decay at 0.5x, zero floor)
against the spec's worked example: 10 accumulated hours decay to 0 over
20 hours past the 72-hour mark. The Postgres functions in
`0002_timer_engine.sql` implement the same formulas — the Python module
(`app/tenthousand/timer/engine.py`) is a client-side mirror for smooth UI
ticking, never the source of truth.

## What's scaffolded vs. what's next

Done: schema, RLS, all timer-transition RPCs (`start_goal`, `pause_goal`,
`resume_goal`, `archive_goal`, `mark_goal_achieved`, `list_my_goals`),
decay/auto-pause engine, cron sweep, hard-delete account RPC, dark-mode
dashboard with progress bars and the five allowed controls, email/password
+ OTP reset + Google OAuth-URL auth screens, unit tests.

Not yet wired: the actual OAuth redirect completion inside the Flet
webview (needs a real Supabase project + Google OAuth client to test
against), a toast/snackbar wired to the `auto_pause` realtime event for
the "auto-paused after 6 hours" notification (the log row and metadata
flag already exist server-side in `timer_logs`), and Play Store listing
assets.
