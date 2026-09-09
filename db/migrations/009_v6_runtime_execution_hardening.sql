-- Creixement v6 runtime execution hardening.
-- Apply after 008_v4_production_trust_fabric.sql.

create table if not exists public.job_dead_letters_v6 (
  id uuid primary key default gen_random_uuid(),
  job_execution_id uuid not null unique references public.job_executions(id) on delete restrict,
  job_definition_id uuid not null references public.job_definitions(id) on delete restrict,
  job_key text not null,
  correlation_id uuid not null,
  idempotency_key text not null,
  attempts integer not null,
  max_attempts integer not null,
  final_error jsonb,
  input jsonb not null default '{}'::jsonb,
  resolution_status text not null default 'open' check (resolution_status in ('open','replayed','resolved','ignored')),
  resolution_note text,
  opened_at timestamptz not null default now(),
  resolved_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists job_dead_letters_v6_status_idx on public.job_dead_letters_v6(resolution_status,opened_at desc);
alter table public.job_dead_letters_v6 enable row level security;

create or replace function public.creixement_claim_jobs(
  worker text,
  batch_size integer default 10,
  lease_for_seconds integer default 600
) returns setof public.job_executions
language plpgsql
security definer
set search_path=public
as $$
begin
  return query
  with picked as (
    select j.id
    from public.job_executions j
    join public.job_definitions d on d.id=j.job_definition_id
    where d.enabled=true
      and j.status in ('queued','failed')
      and j.attempt < d.max_attempts
      and coalesce(j.scheduled_for,j.created_at)<=now()
      and (j.lease_until is null or j.lease_until<now())
    order by coalesce(j.scheduled_for,j.created_at),j.created_at
    for update of j skip locked
    limit greatest(1,least(batch_size,50))
  )
  update public.job_executions j
     set status='leased',
         lease_owner=worker,
         lease_until=now()+make_interval(secs=>greatest(10,lease_for_seconds)),
         attempt=j.attempt+1,
         started_at=coalesce(j.started_at,now()),
         updated_at=now()
  from picked p
  where j.id=p.id
  returning j.*;
end;
$$;

create or replace function public.creixement_finish_job(
  p_job_id uuid,
  p_worker text,
  p_status text,
  p_output jsonb default null,
  p_error jsonb default null,
  p_receipt_ref text default null
) returns public.job_executions
language plpgsql
security definer
set search_path=public
as $$
declare
  v_job public.job_executions%rowtype;
  v_definition public.job_definitions%rowtype;
  v_retry_seconds integer;
begin
  if p_status not in ('succeeded','failed','blocked','cancelled') then
    raise exception 'invalid job terminal status: %',p_status;
  end if;

  select * into v_job from public.job_executions where id=p_job_id for update;
  if not found then raise exception 'job not found'; end if;
  select * into v_definition from public.job_definitions where id=v_job.job_definition_id;
  if not found then raise exception 'job definition not found'; end if;

  if v_job.status in ('succeeded','cancelled','dead_lettered') then raise exception 'terminal job is immutable'; end if;
  if v_job.lease_owner is distinct from p_worker then raise exception 'job lease owner mismatch'; end if;

  if p_status='failed' and v_job.attempt < v_definition.max_attempts then
    v_retry_seconds := least(3600,greatest(v_definition.backoff_seconds,1) * (2 ^ greatest(v_job.attempt-1,0)));
    update public.job_executions
       set status='failed',output=p_output,last_error=p_error,receipt_ref=coalesce(p_receipt_ref,receipt_ref),
           scheduled_for=now()+make_interval(secs=>v_retry_seconds),
           completed_at=null,lease_owner=null,lease_until=null,updated_at=now()
     where id=p_job_id returning * into v_job;
    return v_job;
  end if;

  if p_status='failed' and v_job.attempt >= v_definition.max_attempts then
    update public.job_executions
       set status='dead_lettered',output=p_output,last_error=p_error,receipt_ref=coalesce(p_receipt_ref,receipt_ref),
           completed_at=now(),lease_owner=null,lease_until=null,updated_at=now()
     where id=p_job_id returning * into v_job;

    insert into public.job_dead_letters_v6(
      job_execution_id,job_definition_id,job_key,correlation_id,idempotency_key,attempts,max_attempts,final_error,input
    ) values(
      v_job.id,v_job.job_definition_id,v_definition.job_key,v_job.correlation_id,v_job.idempotency_key,
      v_job.attempt,v_definition.max_attempts,p_error,v_job.input
    ) on conflict(job_execution_id) do update
      set attempts=excluded.attempts,max_attempts=excluded.max_attempts,final_error=excluded.final_error,
          resolution_status='open',resolution_note=null,resolved_at=null,opened_at=now();
    return v_job;
  end if;

  update public.job_executions
     set status=p_status,output=p_output,last_error=p_error,receipt_ref=coalesce(p_receipt_ref,receipt_ref),
         completed_at=now(),lease_owner=null,lease_until=null,updated_at=now()
   where id=p_job_id returning * into v_job;
  return v_job;
end;
$$;

create or replace function public.creixement_handler_circuit_decision(p_handler text)
returns table(allowed boolean,state text,reason text)
language plpgsql
security definer
set search_path=public
as $$
declare v_breaker public.circuit_breakers%rowtype;
begin
  select * into v_breaker from public.circuit_breakers where scope_type='handler' and scope_key=p_handler for update;
  if not found then
    return query select true,'closed'::text,'no circuit breaker state exists; execution permitted'::text;
    return;
  end if;

  if v_breaker.state='open' and v_breaker.retry_at is not null and v_breaker.retry_at>now() then
    return query select false,'open'::text,'handler circuit breaker is open until '||v_breaker.retry_at::text;
    return;
  end if;

  if v_breaker.state='open' then
    update public.circuit_breakers set state='half_open',updated_at=now() where id=v_breaker.id;
    return query select true,'half_open'::text,'cooldown elapsed; one probe execution is permitted'::text;
    return;
  end if;

  return query select true,v_breaker.state,'handler circuit permits execution'::text;
end;
$$;

create or replace function public.creixement_record_handler_result(
  p_handler text,
  p_success boolean,
  p_error jsonb default null
) returns public.circuit_breakers
language plpgsql
security definer
set search_path=public
as $$
declare v_breaker public.circuit_breakers%rowtype;
begin
  insert into public.circuit_breakers(breaker_key,scope_type,scope_key,state,consecutive_failures,failure_threshold,cooldown_seconds)
  values('handler:'||p_handler,'handler',p_handler,'closed',0,5,900)
  on conflict(breaker_key) do nothing;

  select * into v_breaker from public.circuit_breakers where breaker_key='handler:'||p_handler for update;

  if p_success then
    update public.circuit_breakers
       set state='closed',consecutive_failures=0,retry_at=null,opened_at=null,last_success_at=now(),last_error=null,updated_at=now()
     where id=v_breaker.id returning * into v_breaker;
    return v_breaker;
  end if;

  update public.circuit_breakers
     set consecutive_failures=consecutive_failures+1,last_failure_at=now(),last_error=p_error,updated_at=now()
   where id=v_breaker.id returning * into v_breaker;

  if v_breaker.consecutive_failures>=v_breaker.failure_threshold then
    update public.circuit_breakers
       set state='open',opened_at=coalesce(opened_at,now()),retry_at=now()+make_interval(secs=>cooldown_seconds),updated_at=now()
     where id=v_breaker.id returning * into v_breaker;
  end if;
  return v_breaker;
end;
$$;

insert into public.desired_runtime_state_v4(kind,state_key,desired,auto_remediate,source_ref,active)
values
('service','creixement-runtime',jsonb_build_object('state','active','cloudOnly',true,'authRequired',true,'receiptRequired',true),false,'migration:009',true),
('job','safe-internal-handlers',jsonb_build_object('unknownHandlers','blocked','l3Execution','blocked','budgetRequired',true,'connectorReadinessRequired',true),false,'migration:009',true)
on conflict(kind,state_key) do update set desired=excluded.desired,auto_remediate=excluded.auto_remediate,source_ref=excluded.source_ref,active=excluded.active,updated_at=now();

create or replace view public.v_runtime_operating_health_v6 as
select
  now() as observed_at,
  (select state from public.runtime_controls where scope_type='global' and scope_key='creixement' limit 1) as global_runtime_state,
  (select count(*) from public.job_executions where status='queued') as queued_jobs,
  (select count(*) from public.job_executions where status='failed') as retrying_jobs,
  (select count(*) from public.job_executions where status in ('leased','running')) as active_jobs,
  (select count(*) from public.job_dead_letters_v6 where resolution_status='open') as open_job_dead_letters,
  (select count(*) from public.dead_letter_events where resolution_status='open') as open_outbox_dead_letters,
  (select count(*) from public.circuit_breakers where state='open') as open_circuits,
  (select count(*) from public.incidents where status not in ('resolved','closed') and severity='critical') as open_critical_incidents,
  (select count(*) from public.v_connector_health where effective_health='runtime_ready') as runtime_ready_connectors,
  (select count(*) from public.v_connector_health) as connector_count,
  (select count(*) from public.v_goal_queue_v4 where runnable=true) as runnable_goals,
  (select count(*) from public.v_owner_action_queue_v4) as owner_actions,
  (select coalesce(sum(amount),0) from public.revenue_events where verified=true) as verified_revenue;
