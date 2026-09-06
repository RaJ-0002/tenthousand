-- Compliant account deletion (Google Play policy requires an in-app path).
--
-- Hard delete, no soft-delete/backup path: goals and timer_logs cascade off
-- profiles/auth.users via the FKs declared in 0001, and this function
-- additionally removes the auth.users row itself so the email becomes
-- available again and the user cannot dodge the "no goal reset" rule by
-- deleting and recreating an account under the same address.
--
-- Deleting from auth.users normally requires the Supabase service-role key
-- (auth.admin.deleteUser) called from a trusted server. Since this project
-- has no separate backend server, this function does it in-database: it
-- runs as SECURITY DEFINER owned by the `postgres` role, which has the
-- necessary privileges on the `auth` schema, so the client only ever needs
-- its own session (no service-role key is ever shipped to the app).

create or replace function public.delete_my_account()
returns void
language plpgsql
security definer
set search_path = public, auth
as $$
declare
  v_uid uuid := auth.uid();
begin
  if v_uid is null then
    raise exception 'not authenticated';
  end if;

  -- goals cascade-delete timer_logs; profiles cascade-delete is redundant
  -- with the auth.users delete below but kept explicit for clarity/safety.
  delete from public.goals where user_id = v_uid;
  delete from public.profiles where id = v_uid;
  delete from auth.users where id = v_uid;
end;
$$;

grant execute on function public.delete_my_account() to authenticated;
