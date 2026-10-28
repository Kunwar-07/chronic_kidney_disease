-- Run once in the Supabase SQL Editor, or apply with your Supabase migration workflow.
begin;

create table public.assessments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  task text not null check (task in ('screening', 'biomarker')),
  input jsonb not null check (jsonb_typeof(input) = 'object'),
  result jsonb not null check (jsonb_typeof(result) = 'object'),
  created_at timestamptz not null default now(),
  constraint assessment_result_status check (
    (result->>'status' = 'ok') is true
  ),
  constraint assessment_result_task check (
    (result->>'task' = task) is true
  ),
  constraint assessment_result_probability check (
    result ? 'probability' and jsonb_typeof(result->'probability') = 'number'
    and (result->>'probability')::numeric between 0 and 1
  )
);

create index assessments_user_created_idx on public.assessments (user_id, created_at desc, id desc);

alter table public.assessments enable row level security;
alter table public.assessments force row level security;

revoke all on public.assessments from public, anon, authenticated;
grant select, delete on public.assessments to authenticated;
-- Clients cannot choose IDs/timestamps, transfer ownership, or update historical records.
grant insert (user_id, task, input, result) on public.assessments to authenticated;

create policy assessments_select_own on public.assessments
  for select to authenticated using ((select auth.uid()) = user_id);
create policy assessments_insert_own on public.assessments
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy assessments_delete_own on public.assessments
  for delete to authenticated using ((select auth.uid()) = user_id);

comment on table public.assessments is
  'User-owned research assessments. Not a clinically verified patient record. Inputs are explicitly saved by authenticated callers.';

commit;
