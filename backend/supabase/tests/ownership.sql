-- Live policy test. Synthetic users/records exist only inside this transaction.
-- Run as postgres in Supabase SQL Editor after the migration. No passwords/tokens.
begin;
create temporary table nephra_test_ids (a uuid, b uuid, record_id uuid) on commit drop;
insert into nephra_test_ids values (gen_random_uuid(), gen_random_uuid(), null);
grant select, update on nephra_test_ids to authenticated;

insert into auth.users (id, aud, role)
select a, 'authenticated', 'authenticated' from nephra_test_ids
union all select b, 'authenticated', 'authenticated' from nephra_test_ids;

select set_config('request.jwt.claims', json_build_object('sub', a, 'role', 'authenticated')::text, true)
from nephra_test_ids;
set local role authenticated;

do $$
declare saved uuid; n integer;
begin
  insert into public.assessments (user_id, task, input, result)
  values (auth.uid(), 'screening', '{"age":56,"sex":0,"bmi":28.2,"diabetes":0}',
    '{"status":"ok","task":"screening","probability":0.1,"model_version":"synthetic-policy-test"}')
  returning id into saved;
  update nephra_test_ids set record_id = saved;
  select count(*) into n from public.assessments where id = saved;
  if n <> 1 then raise exception 'Owner read failed'; end if;

  begin
    insert into public.assessments (user_id, task, input, result)
    select b, 'screening', '{}', '{"status":"ok","task":"screening","probability":0.1}' from nephra_test_ids;
    raise exception 'Cross-user insert was permitted';
  exception when insufficient_privilege then null;
  end;
  begin
    update public.assessments set input = '{}' where id = saved;
    raise exception 'Immutable record update was permitted';
  exception when insufficient_privilege then null;
  end;
end $$;

reset role;
select set_config('request.jwt.claims', json_build_object('sub', b, 'role', 'authenticated')::text, true)
from nephra_test_ids;
set local role authenticated;
do $$
declare n integer;
begin
  select count(*) into n from public.assessments where id = (select record_id from nephra_test_ids);
  if n <> 0 then raise exception 'Cross-user read was permitted'; end if;
  delete from public.assessments where id = (select record_id from nephra_test_ids);
  get diagnostics n = row_count;
  if n <> 0 then raise exception 'Cross-user delete was permitted'; end if;
end $$;

reset role;
set local role anon;
do $$ begin
  begin
    perform id from public.assessments limit 1;
    raise exception 'Anonymous read was permitted';
  exception when insufficient_privilege then null;
  end;
end $$;

reset role;
select set_config('request.jwt.claims', json_build_object('sub', a, 'role', 'authenticated')::text, true)
from nephra_test_ids;
set local role authenticated;
do $$
declare n integer;
begin
  delete from public.assessments where id = (select record_id from nephra_test_ids);
  get diagnostics n = row_count;
  if n <> 1 then raise exception 'Owner delete failed'; end if;
end $$;
reset role;
rollback;
select 'PASS: own create/read/delete; cross-user read/insert/delete blocked; updates and anonymous access blocked. All test data rolled back.' as result;
