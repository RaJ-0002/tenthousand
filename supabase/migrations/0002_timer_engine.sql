-- TenThousand: server-authoritative timer engine.
-- All timestamps used here are Postgres server time (now()), never a
-- client-supplied value. This is the anti-cheat boundary: clients can only
-- ever trigger a state *transition* (start/pause/resume/archive/achieve);
-- the resulting numbers are always computed from server clock + stored
-- timestamps inside these security-definer functions.
--
-- Constants:
--   10,000 hours          = 36,000,000 seconds
--   6-hour auto-pause cap = 21,600 seconds
--   72-hour decay floor   = 259,200 seconds
--   decay rate            = 0.5x real time

create or replace function public._goal_seconds_10000() returns bigint
  language sql immutable as $$ select 36000000::bigint $$;

create or replace function public._auto_pause_seconds() returns bigint
  language sql immutable as $$ select 21600::bigint $$;

create or replace function public._inactivity_threshold_seconds() returns bigint
  language sql immutable as $$ select 259200::bigint $$;

-- Settles pending state (6h auto-pause, 72h+ decay) for a single goal as of
-- now(). Called at the top of every mutating RPC below, by the on-fetch
-- evaluation RPC used by the client, and by the cron sweep — so it must be
-- idempotent no matter how many times or how often it's invoked.
create or replace function public.evaluate_goal(p_goal_id uuid)
returns public.goals
language plpgsql
security definer
set search_path = public
as $$
declare
  g public.goals;
  v_now timestamptz := now();
  v_run_seconds numeric;
  v_paused_seconds numeric;
  v_decay_anchor timestamptz;
  v_decay_window_seconds numeric;
  v_decay_seconds bigint;
begin
  select * into g from public.goals where id = p_goal_id for update;
  if not found then
    raise exception 'goal % not found', p_goal_id;
  end if;

  if g.is_archived or g.is_achieved then
    return g;
  end if;

  -- Rule: continuous 6-hour auto-pause.
  if g.is_running then
    v_run_seconds := extract(epoch from (v_now - g.started_at));
    if v_run_seconds >= public._auto_pause_seconds() then
      g.accumulated_seconds := g.accumulated_seconds + public._auto_pause_seconds();
      g.last_paused_at := g.started_at + make_interval(secs => public._auto_pause_seconds());
      g.last_decay_applied_at := g.last_paused_at;
      g.started_at := null;
      g.is_running := false;

      insert into public.timer_logs (goal_id, event_type, event_at, delta_seconds, accumulated_seconds_after, metadata)
      values (g.id, 'auto_pause', v_now, public._auto_pause_seconds(), g.accumulated_seconds,
              jsonb_build_object('reason', 'continuous_6h_limit', 'notify', true));

      if g.accumulated_seconds >= public._goal_seconds_10000() then
        g.accumulated_seconds := public._goal_seconds_10000();
        g.is_achieved := true;
        insert into public.timer_logs (goal_id, event_type, event_at, delta_seconds, accumulated_seconds_after)
        values (g.id, 'achieved', v_now, 0, g.accumulated_seconds);
      end if;
    end if;
  end if;

  -- Rule: 3-day (72h) inactivity reverse-decay at 0.5x, floored at zero.
  if not g.is_running and not g.is_achieved and g.last_paused_at is not null then
    v_paused_seconds := extract(epoch from (v_now - g.last_paused_at));
    if v_paused_seconds > public._inactivity_threshold_seconds() then
      v_decay_anchor := greatest(
        coalesce(g.last_decay_applied_at, g.last_paused_at),
        g.last_paused_at + make_interval(secs => public._inactivity_threshold_seconds())
      );
      v_decay_window_seconds := greatest(0, extract(epoch from (v_now - v_decay_anchor)));
      v_decay_seconds := floor(v_decay_window_seconds * 0.5);
      if v_decay_seconds > 0 then
        g.accumulated_seconds := greatest(0, g.accumulated_seconds - v_decay_seconds);
        g.last_decay_applied_at := v_now;
        insert into public.timer_logs (goal_id, event_type, event_at, delta_seconds, accumulated_seconds_after, metadata)
        values (g.id, 'decay', v_now, -v_decay_seconds, g.accumulated_seconds,
                jsonb_build_object('paused_seconds', v_paused_seconds));
      end if;
    end if;
  end if;

  update public.goals set
    accumulated_seconds   = g.accumulated_seconds,
    started_at            = g.started_at,
    last_paused_at        = g.last_paused_at,
    last_decay_applied_at = g.last_decay_applied_at,
    is_running             = g.is_running,
    is_achieved             = g.is_achieved
  where id = g.id;

  return g;
end;
$$;

grant execute on function public.evaluate_goal(uuid) to authenticated;

-- Creation. Deliberately only accepts a title; every other column starts
-- from its schema default so a client can never seed accumulated time.
create or replace function public.create_goal(p_title text)
returns public.goals
language plpgsql
security definer
set search_path = public
as $$
declare
  g public.goals;
begin
  insert into public.goals (user_id, title)
  values (auth.uid(), p_title)
  returning * into g;

  insert into public.timer_logs (goal_id, event_type, event_at, delta_seconds, accumulated_seconds_after)
  values (g.id, 'created', now(), 0, 0);

  return g;
end;
$$;

grant execute on function public.create_goal(text) to authenticated;

create or replace function public._assert_owns_goal(p_goal_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.goals where id = p_goal_id and user_id = auth.uid()
  ) then
    raise exception 'not authorized for goal %', p_goal_id;
  end if;
end;
$$;

-- [Start] / [Resume]: identical mechanics — begin a fresh run from now().
-- Exposed as two names because the UI/spec distinguish them, but both call
-- the same settle-then-transition logic.
create or replace function public.start_goal(p_goal_id uuid)
returns public.goals
language plpgsql
security definer
set search_path = public
as $$
declare
  g public.goals;
begin
  perform public._assert_owns_goal(p_goal_id);
  g := public.evaluate_goal(p_goal_id);

  if g.is_archived then
    raise exception 'cannot start an archived goal; unarchive is not supported by design';
  end if;
  if g.is_achieved then
    raise exception 'goal already achieved';
  end if;
  if g.is_running then
    return g; -- no-op, already running
  end if;

  update public.goals
     set started_at = now(),
         last_paused_at = null,
         last_decay_applied_at = null,
         is_running = true
   where id = p_goal_id
   returning * into g;

  insert into public.timer_logs (goal_id, event_type, event_at, delta_seconds, accumulated_seconds_after)
  values (g.id, (case when g.accumulated_seconds = 0 then 'start' else 'resume' end)::goal_event_type,
          now(), 0, g.accumulated_seconds);

  return g;
end;
$$;

grant execute on function public.start_goal(uuid) to authenticated;

create or replace function public.resume_goal(p_goal_id uuid)
returns public.goals
language sql
security definer
set search_path = public
as $$
  select public.start_goal(p_goal_id);
$$;

grant execute on function public.resume_goal(uuid) to authenticated;

-- [Pause]: finalize the current run into accumulated_seconds.
create or replace function public.pause_goal(p_goal_id uuid)
returns public.goals
language plpgsql
security definer
set search_path = public
as $$
declare
  g public.goals;
  v_now timestamptz := now();
  v_elapsed bigint;
begin
  perform public._assert_owns_goal(p_goal_id);
  g := public.evaluate_goal(p_goal_id); -- settles any 6h auto-pause first

  if not g.is_running then
    return g; -- already paused/auto-paused/achieved/archived; nothing to do
  end if;

  v_elapsed := least(
    public._auto_pause_seconds(),
    floor(extract(epoch from (v_now - g.started_at)))
  );

  update public.goals
     set accumulated_seconds = least(public._goal_seconds_10000(), g.accumulated_seconds + v_elapsed),
         started_at = null,
         last_paused_at = v_now,
         last_decay_applied_at = v_now,
         is_running = false
   where id = p_goal_id
   returning * into g;

  insert into public.timer_logs (goal_id, event_type, event_at, delta_seconds, accumulated_seconds_after)
  values (g.id, 'pause', v_now, v_elapsed, g.accumulated_seconds);

  if g.accumulated_seconds >= public._goal_seconds_10000() then
    update public.goals set is_achieved = true where id = p_goal_id returning * into g;
    insert into public.timer_logs (goal_id, event_type, event_at, delta_seconds, accumulated_seconds_after)
    values (g.id, 'achieved', v_now, 0, g.accumulated_seconds);
  end if;

  return g;
end;
$$;

grant execute on function public.pause_goal(uuid) to authenticated;

-- [Archive]: hides from the active dashboard without touching accumulated
-- time. If the goal is currently running, its in-flight time is finalized
-- first (same math as pause) so no running time is silently lost.
create or replace function public.archive_goal(p_goal_id uuid)
returns public.goals
language plpgsql
security definer
set search_path = public
as $$
declare
  g public.goals;
begin
  perform public._assert_owns_goal(p_goal_id);
  g := public.evaluate_goal(p_goal_id);

  if g.is_running then
    g := public.pause_goal(p_goal_id);
  end if;

  update public.goals
     set is_archived = true
   where id = p_goal_id
   returning * into g;

  insert into public.timer_logs (goal_id, event_type, event_at, delta_seconds, accumulated_seconds_after)
  values (g.id, 'archived', now(), 0, g.accumulated_seconds);

  return g;
end;
$$;

grant execute on function public.archive_goal(uuid) to authenticated;

-- [Mark as Achieved]: explicit user completion, independent of the 10,000h
-- auto-trigger. Finalizes any in-flight running time first.
create or replace function public.mark_goal_achieved(p_goal_id uuid)
returns public.goals
language plpgsql
security definer
set search_path = public
as $$
declare
  g public.goals;
begin
  perform public._assert_owns_goal(p_goal_id);
  g := public.evaluate_goal(p_goal_id);

  if g.is_running then
    g := public.pause_goal(p_goal_id);
  end if;

  if g.is_achieved then
    return g;
  end if;

  update public.goals
     set is_achieved = true
   where id = p_goal_id
   returning * into g;

  insert into public.timer_logs (goal_id, event_type, event_at, delta_seconds, accumulated_seconds_after)
  values (g.id, 'achieved', now(), 0, g.accumulated_seconds);

  return g;
end;
$$;

grant execute on function public.mark_goal_achieved(uuid) to authenticated;

-- Convenience for the client: list the caller's goals after settling each
-- one's pending state, so the dashboard always reflects server-computed
-- reality on open, per the "evaluated state transition on fetch" rule.
create or replace function public.list_my_goals(p_include_archived boolean default false)
returns setof public.goals
language plpgsql
security definer
set search_path = public
as $$
declare
  r public.goals;
begin
  for r in
    select * from public.goals
     where user_id = auth.uid()
       and (p_include_archived or not is_archived)
     order by created_at asc
  loop
    return next public.evaluate_goal(r.id);
  end loop;
  return;
end;
$$;

grant execute on function public.list_my_goals(boolean) to authenticated;
