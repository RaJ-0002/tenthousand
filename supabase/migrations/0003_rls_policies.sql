-- Row Level Security.
--
-- Design: clients get direct SELECT on their own rows (for the dashboard
-- read path / Realtime subscriptions), but NO direct INSERT/UPDATE/DELETE
-- policies on goals or timer_logs. Every mutation must go through the
-- security-definer functions in 0002_timer_engine.sql, which run as the
-- function owner and therefore bypass RLS -- that's the enforcement point
-- for "no manual reset/delete of goals" and for the anti-cheat timestamp
-- rules. Direct table writes from a client are simply not possible.

alter table public.profiles enable row level security;
alter table public.goals enable row level security;
alter table public.timer_logs enable row level security;

create policy "profiles: select own"
  on public.profiles for select
  using (auth.uid() = id);

create policy "goals: select own"
  on public.goals for select
  using (auth.uid() = user_id);

create policy "timer_logs: select own"
  on public.timer_logs for select
  using (
    exists (
      select 1 from public.goals g
       where g.id = timer_logs.goal_id
         and g.user_id = auth.uid()
    )
  );

-- No insert/update/delete policies for `authenticated` on any of the three
-- tables above -- default-deny. create_goal/start_goal/pause_goal/etc and
-- delete_my_account (0004) are security definer and are the only write path.
