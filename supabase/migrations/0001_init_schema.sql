-- TenThousand: core schema
-- Time is stored in seconds (bigint) to avoid floating point drift.
-- 10,000 hours = 36,000,000 seconds.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  created_at timestamptz not null default now()
);

do $$
begin
  if not exists (select 1 from pg_type where typname = 'goal_event_type') then
    create type goal_event_type as enum (
      'created', 'start', 'resume', 'pause', 'auto_pause', 'decay', 'achieved', 'archived'
    );
  end if;
end$$;

create table if not exists public.goals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (char_length(title) between 1 and 120),

  -- Canonical confirmed time. Only ever mutated by the security-definer
  -- functions in 0002_timer_engine.sql, never directly by clients.
  accumulated_seconds bigint not null default 0 check (accumulated_seconds >= 0),

  -- Set while the goal is actively running; null while paused/archived/achieved.
  started_at timestamptz,

  -- Set the moment the goal enters a paused state. Anchor for the
  -- 72-hour inactivity decay window.
  last_paused_at timestamptz,

  -- Anchor used to make decay application idempotent/incremental across
  -- repeated calls (on-fetch evaluation and the cron sweep both call the
  -- same function, so this prevents double-decaying the same window).
  last_decay_applied_at timestamptz,

  is_running boolean not null default false,
  is_archived boolean not null default false,
  is_achieved boolean not null default false,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint goals_not_both_running_and_done
    check (not (is_running and (is_archived or is_achieved))),
  constraint goals_achieved_not_running
    check (not (is_achieved and started_at is not null))
);

create index if not exists goals_user_id_idx on public.goals(user_id);

-- Used by the cron sweep to cheaply find candidates without a full scan.
create index if not exists goals_running_idx
  on public.goals(started_at)
  where is_running and not is_archived and not is_achieved;

create index if not exists goals_paused_idx
  on public.goals(last_paused_at)
  where not is_running and not is_archived and not is_achieved and last_paused_at is not null;

create table if not exists public.timer_logs (
  id uuid primary key default gen_random_uuid(),
  goal_id uuid not null references public.goals(id) on delete cascade,
  event_type goal_event_type not null,
  event_at timestamptz not null default now(),
  delta_seconds bigint not null default 0,
  accumulated_seconds_after bigint not null,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists timer_logs_goal_id_idx on public.timer_logs(goal_id, event_at desc);

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists goals_touch_updated_at on public.goals;
create trigger goals_touch_updated_at
  before update on public.goals
  for each row execute function public.touch_updated_at();

-- Auto-provision a profile row (and enforce one-account-per-email via the
-- unique constraint above) whenever Supabase Auth creates a user, whether
-- via Google OAuth or email/password.
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_auth_user();
