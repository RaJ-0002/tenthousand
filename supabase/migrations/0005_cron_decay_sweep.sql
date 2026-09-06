-- Scheduled processing: settles state for goals even if their owner never
-- opens the app -- otherwise a user could dodge the 6h auto-pause notice or
-- let decay silently under/over-run between visits. Reuses evaluate_goal()
-- so the math lives in exactly one place.

create extension if not exists pg_cron;

create or replace function public.sweep_goal_timers()
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  r record;
begin
  -- Goals that have been running past the 6h cap.
  for r in
    select id from public.goals
     where is_running
       and not is_archived
       and not is_achieved
       and started_at <= now() - make_interval(secs => public._auto_pause_seconds())
  loop
    perform public.evaluate_goal(r.id);
  end loop;

  -- Goals paused past the 72h decay threshold.
  for r in
    select id from public.goals
     where not is_running
       and not is_archived
       and not is_achieved
       and last_paused_at is not null
       and last_paused_at <= now() - make_interval(secs => public._inactivity_threshold_seconds())
  loop
    perform public.evaluate_goal(r.id);
  end loop;
end;
$$;

-- Runs as the postgres role (no `authenticated` grant needed/wanted here).
select cron.schedule(
  'goal-timer-sweep',
  '*/15 * * * *',
  $$select public.sweep_goal_timers();$$
);
