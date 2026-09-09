-- Creixement v5 runtime convergence.
-- Apply after 008_v4_production_trust_fabric.sql.
-- Adds durable worker heartbeat, job dead letters, retry backoff, desired-state reconciliation and runtime readiness.

create table if not exists public.runtime_heartbeats_v5 (
  runtime_id text primary key,
  service_key text not null default 'creixement-cloud-runtime',
  version text not null,
  commit_sha text,
  environment text not null default 'production',
  status text not null check (status in ('starting','healthy','degraded','stopping','stopped')),
  metadata jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.job_dead_letters_v5 (
  id uuid primary key default gen_random_uuid(),
  job_execution_id uuid not null unique references public.job_executions(id) on delete restrict,
  job_definition_id uuid not null references public.job_definitions(id) on delete restrict,
  job_key text not null,
  correlation_id uuid not null,
  idempotency_key text not null,
  attempts integer not null,
  final_error jsonb,
  input jsonb not null default '{}'::jsonb,
  resolution_status text not null default 'open' check (resolution_status in ('open','replayed','resolved','ignored')),
  resolution_note text,
  dead_lettered_at timestamptz not null default now(),
  resolved_at timestamptz
);
create index if not exists job_dead_letters_v5_open_idx on public.job_dead_letters_v5(resolution_status,dead_lettered_at desc);

alter table public.runtime_heartbeats_v5 enable row level security;
alter table public.job_dead_letters_v5 enable row level security;

drop trigger if exists runtime_heartbeats_v5_set_updated_at on public.runtime_heartbeats_v5;
create trigger runtime_heartbeats_v5_set_updated_at before update on public.runtime_heartbeats_v5 for each row execute function public.creixement_set_updated_at();

create or replace function public.creixement_record_heartbeat_v5(
  p_runtime_id text,
  p_version text,
  p_commit_sha text default null,
  p_status text default 'healthy',
  p_metadata jsonb default '{}'::jsonb
) returns public.runtime_heartbeats_v5
language plpgsql security definer set search_path=public
as $$
declare v_row public.runtime_heartbeats_v5%rowtype;
begin
  if p_status not in ('starting','healthy','degraded','stopping','stopped') then
    raise exception 'invalid heartbeat status: %', p_status;
  end if;
  insert into public.runtime_heartbeats_v5(runtime_id,version,commit_sha,status,metadata,first_seen_at,last_seen_at)
  values(p_runtime_id,p_version,p_commit_sha,p_status,coalesce(p_metadata,'{}'::jsonb),now(),now())
  on conflict(runtime_id) do update set
    version=excluded.version,
    commit_sha=excluded.commit_sha,
    status=excluded.status,
    metadata=excluded.metadata,
    last_seen_at=now(),
    updated_at=now()
  returning * into v_row;
  return v_row;
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
language plpgsql security definer set search_path=public
as $$
declare
  v_job public.job_executions%rowtype;
  v_definition public.job_definitions%rowtype;
  v_terminal boolean;
  v_backoff integer;
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

  v_terminal := p_status in ('succeeded','blocked','cancelled') or (p_status='failed' and v_job.attempt>=v_definition.max_attempts);
  v_backoff := least(3600, greatest(v_definition.backoff_seconds,1) * power(2,greatest(v_job.attempt-1,0))::integer);

  update public.job_executions set
    status=case when p_status='failed' and v_job.attempt>=v_definition.max_attempts then 'dead_lettered' else p_status end,
    output=p_output,
    last_error=p_error,
    receipt_ref=coalesce(p_receipt_ref,receipt_ref),
    scheduled_for=case when p_status='failed' and v_job.attempt<v_definition.max_attempts then now()+make_interval(secs=>v_backoff) else scheduled_for end,
    completed_at=case when v_terminal then now() else null end,
    lease_owner=null,
    lease_until=null,
    updated_at=now()
  where id=p_job_id returning * into v_job;

  if v_job.status='dead_lettered' then
    insert into public.job_dead_letters_v5(job_execution_id,job_definition_id,job_key,correlation_id,idempotency_key,attempts,final_error,input)
    values(v_job.id,v_job.job_definition_id,v_definition.job_key,v_job.correlation_id,v_job.idempotency_key,v_job.attempt,p_error,v_job.input)
    on conflict(job_execution_id) do update set
      attempts=excluded.attempts,
      final_error=excluded.final_error,
      dead_lettered_at=now(),
      resolution_status='open';
  end if;

  return v_job;
end;
$$;

create or replace function public.creixement_reconcile_runtime_v5()
returns table(kind text,state_key text,field text,severity text,remediation text)
language plpgsql security definer set search_path=public
as $$
declare
  d record;
  actual jsonb;
  expected_value jsonb;
  observed_value jsonb;
  f text;
  sev text;
  remedy text;
begin
  delete from public.runtime_drift_findings_v4 where status='open';

  for d in select * from public.desired_runtime_state_v4 where active=true loop
    actual := null;

    if d.kind='connector' then
      select jsonb_build_object('state',state,'runtime_connection',runtime_connection) into actual
      from public.connectors where slug=d.state_key limit 1;
    elsif d.kind='job' then
      select jsonb_build_object('enabled',enabled,'handler_key',handler_key,'autonomy_level',autonomy_level) into actual
      from public.job_definitions where job_key=d.state_key limit 1;
    elsif d.kind='agent' then
      select jsonb_build_object('health',health,'autonomy_level',autonomy_level,'version',version) into actual
      from public.agents where slug=d.state_key limit 1;
    elsif d.kind='service' then
      select jsonb_build_object('state',state,'max_autonomy',max_autonomy) into actual
      from public.service_identities where service_key=d.state_key limit 1;
    elsif d.kind='policy' then
      select jsonb_build_object('decision',decision,'max_autonomy',max_autonomy,'active',active) into actual
      from public.policies where policy_key=d.state_key limit 1;
    end if;

    if actual is null then actual := '{}'::jsonb; end if;

    insert into public.observed_runtime_state_v4(kind,state_key,observed,evidence_refs,observed_at)
    values(d.kind,d.state_key,actual,jsonb_build_array('runtime-reconcile-v5'),now())
    on conflict(kind,state_key) do update set observed=excluded.observed,evidence_refs=excluded.evidence_refs,observed_at=excluded.observed_at;

    for f in select jsonb_object_keys(d.desired) loop
      expected_value := d.desired -> f;
      observed_value := actual -> f;
      if observed_value is distinct from expected_value then
        sev := case when d.kind in ('policy','service') then 'critical' when d.kind in ('connector','job') then 'warning' else 'info' end;
        remedy := case when d.auto_remediate and d.kind in ('job','agent') then 'automatic' else 'approval_required' end;
        insert into public.runtime_drift_findings_v4(kind,state_key,field,desired,observed,severity,remediation,status,evidence_refs)
        values(d.kind,d.state_key,f,expected_value,observed_value,sev,remedy,'open',jsonb_build_array('runtime-reconcile-v5'));
        return query select d.kind,d.state_key,f,sev,remedy;
      end if;
    end loop;
  end loop;
end;
$$;

create or replace view public.v_runtime_readiness_v5 as
select
  now() as observed_at,
  (select count(*) from public.runtime_heartbeats_v5 where status='healthy' and last_seen_at >= now()-interval '15 minutes') as healthy_runtime_instances,
  (select count(*) from public.v_connector_health where effective_health='runtime_ready') as runtime_ready_connectors,
  (select count(*) from public.connectors) as connector_count,
  (select count(*) from public.job_definitions where enabled=true) as enabled_jobs,
  (select count(*) from public.job_executions where status in ('queued','leased','running','failed')) as active_jobs,
  (select count(*) from public.job_dead_letters_v5 where resolution_status='open') as open_job_dead_letters,
  (select count(*) from public.runtime_drift_findings_v4 where status='open' and severity='critical') as critical_drift,
  (select count(*) from public.incidents where severity='critical' and status not in ('resolved','closed')) as critical_incidents,
  (select count(*) from public.v_owner_action_queue_v4) as owner_actions,
  (select count(*) from public.v_goal_queue_v4 where runnable=true and execution_mode='autonomous') as autonomous_goals,
  case
    when (select count(*) from public.runtime_heartbeats_v5 where status='healthy' and last_seen_at >= now()-interval '15 minutes')=0 then false
    when (select count(*) from public.runtime_drift_findings_v4 where status='open' and severity='critical')>0 then false
    when (select count(*) from public.incidents where severity='critical' and status not in ('resolved','closed'))>0 then false
    else true
  end as internal_runtime_ready;

insert into public.desired_runtime_state_v4(kind,state_key,desired,auto_remediate,source_ref,active)
values
('service','creixement-cloud-runtime','{"state":"active","max_autonomy":"L2"}'::jsonb,false,'v5-runtime-convergence',true),
('job','chief-priority-compile','{"enabled":true,"handler_key":"chief.compile_priorities","autonomy_level":"L1"}'::jsonb,true,'v5-runtime-convergence',true),
('job','connector-health','{"enabled":true,"handler_key":"automation.connector_health","autonomy_level":"L1"}'::jsonb,true,'v5-runtime-convergence',true),
('job','opportunity-radar','{"enabled":true,"handler_key":"opportunity.refresh_radar","autonomy_level":"L1"}'::jsonb,true,'v5-runtime-convergence',true)
on conflict(kind,state_key) do update set desired=excluded.desired,auto_remediate=excluded.auto_remediate,source_ref=excluded.source_ref,active=excluded.active,updated_at=now();

insert into public.job_definitions(job_key,name,description,trigger_type,schedule_expr,timezone,handler_key,owner_agent_slug,autonomy_level,policy_key,required_connectors,input_template,enabled,max_runtime_seconds,lease_seconds,max_attempts,backoff_seconds,concurrency_limit)
values
('runtime-reconcile-v5','Runtime desired-state reconciliation','Compare governed desired runtime state with live observed state and record drift.','cron','*/30 * * * *','Europe/Madrid','automation.runtime_reconcile','automation-engineer','L1','internal_read_research','[]'::jsonb,'{}'::jsonb,true,120,240,3,60,1)
on conflict(job_key) do update set name=excluded.name,description=excluded.description,trigger_type=excluded.trigger_type,schedule_expr=excluded.schedule_expr,timezone=excluded.timezone,handler_key=excluded.handler_key,owner_agent_slug=excluded.owner_agent_slug,autonomy_level=excluded.autonomy_level,policy_key=excluded.policy_key,required_connectors=excluded.required_connectors,input_template=excluded.input_template,enabled=excluded.enabled,max_runtime_seconds=excluded.max_runtime_seconds,lease_seconds=excluded.lease_seconds,max_attempts=excluded.max_attempts,backoff_seconds=excluded.backoff_seconds,concurrency_limit=excluded.concurrency_limit,updated_at=now();
