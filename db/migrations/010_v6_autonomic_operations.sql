-- Creixement v6 converged autonomic operations.
-- Apply after 009_v5_runtime_convergence.sql.
-- Adds handler circuits, owner-decision ingress, scheduler/provider readiness and release attestation.

create or replace function public.creixement_handler_circuit_decision_v6(p_handler text)
returns table(allowed boolean,state text,reason text)
language plpgsql security definer set search_path=public
as $$
declare v_breaker public.circuit_breakers%rowtype;
begin
  select * into v_breaker
  from public.circuit_breakers
  where scope_type='handler' and scope_key=p_handler
  for update;

  if not found then
    return query select true,'closed'::text,'no handler circuit exists; execution permitted'::text;
    return;
  end if;

  if v_breaker.state='open' and v_breaker.retry_at is not null and v_breaker.retry_at>now() then
    return query select false,'open'::text,'handler circuit is open until '||v_breaker.retry_at::text;
    return;
  end if;

  if v_breaker.state='open' then
    update public.circuit_breakers set state='half_open',updated_at=now() where id=v_breaker.id;
    return query select true,'half_open'::text,'cooldown elapsed; one probe is permitted'::text;
    return;
  end if;

  return query select true,v_breaker.state,'handler circuit permits execution'::text;
end;
$$;

create or replace function public.creixement_record_handler_result_v6(
  p_handler text,
  p_success boolean,
  p_error jsonb default null
) returns public.circuit_breakers
language plpgsql security definer set search_path=public
as $$
declare v_breaker public.circuit_breakers%rowtype;
begin
  insert into public.circuit_breakers(
    breaker_key,scope_type,scope_key,state,consecutive_failures,failure_threshold,cooldown_seconds
  ) values(
    'handler:'||p_handler,'handler',p_handler,'closed',0,5,900
  ) on conflict(breaker_key) do nothing;

  select * into v_breaker from public.circuit_breakers where breaker_key='handler:'||p_handler for update;

  if p_success then
    update public.circuit_breakers
    set state='closed',consecutive_failures=0,retry_at=null,opened_at=null,
        last_success_at=now(),last_error=null,updated_at=now()
    where id=v_breaker.id returning * into v_breaker;
    return v_breaker;
  end if;

  update public.circuit_breakers
  set consecutive_failures=consecutive_failures+1,last_failure_at=now(),last_error=p_error,updated_at=now()
  where id=v_breaker.id returning * into v_breaker;

  if v_breaker.consecutive_failures>=v_breaker.failure_threshold then
    update public.circuit_breakers
    set state='open',opened_at=coalesce(opened_at,now()),
        retry_at=now()+make_interval(secs=>cooldown_seconds),updated_at=now()
    where id=v_breaker.id returning * into v_breaker;
  end if;
  return v_breaker;
end;
$$;

create or replace function public.creixement_claim_jobs(
  worker text,
  batch_size integer default 10,
  lease_for_seconds integer default 600
) returns setof public.job_executions
language plpgsql security definer set search_path=public
as $$
begin
  return query
  with picked as (
    select j.id
    from public.job_executions j
    join public.job_definitions d on d.id=j.job_definition_id
    where d.enabled=true
      and j.status in ('queued','failed')
      and j.attempt<d.max_attempts
      and coalesce(j.scheduled_for,j.created_at)<=now()
      and (j.lease_until is null or j.lease_until<now())
    order by coalesce(j.scheduled_for,j.created_at),j.created_at
    for update of j skip locked
    limit greatest(1,least(batch_size,50))
  )
  update public.job_executions j
  set status='leased',lease_owner=worker,
      lease_until=now()+make_interval(secs=>greatest(10,lease_for_seconds)),
      attempt=j.attempt+1,started_at=coalesce(j.started_at,now()),updated_at=now()
  from picked p where j.id=p.id
  returning j.*;
end;
$$;

create table if not exists public.owner_decisions_v6 (
  id uuid primary key default gen_random_uuid(),
  idempotency_key text not null unique,
  decision_key text not null unique,
  subject_type text not null check (subject_type in ('goal','approval','action','release','connector','policy','other')),
  subject_key text not null,
  decision text not null check (decision in ('approve','reject','defer','modify')),
  payload_digest text not null check (payload_digest ~ '^[0-9A-Fa-f]{64}$'),
  rationale text,
  modifications jsonb not null default '{}'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  status text not null default 'recorded' check (status in ('recorded','consumed','superseded','cancelled')),
  actor text not null default 'owner',
  consumed_receipt_ref text,
  created_at timestamptz not null default now(),
  consumed_at timestamptz
);
create index if not exists owner_decisions_v6_subject_idx on public.owner_decisions_v6(subject_type,subject_key,created_at desc);
alter table public.owner_decisions_v6 enable row level security;

create or replace function public.creixement_submit_owner_decision_v6(
  p_idempotency_key text,
  p_subject_type text,
  p_subject_key text,
  p_decision text,
  p_payload_digest text,
  p_rationale text default null,
  p_modifications jsonb default '{}'::jsonb,
  p_evidence_refs jsonb default '[]'::jsonb
) returns public.owner_decisions_v6
language plpgsql security definer set search_path=public
as $$
declare v_row public.owner_decisions_v6%rowtype;
begin
  if p_subject_type not in ('goal','approval','action','release','connector','policy','other') then
    raise exception 'invalid subject type';
  end if;
  if p_decision not in ('approve','reject','defer','modify') then
    raise exception 'invalid owner decision';
  end if;
  if p_payload_digest !~ '^[0-9A-Fa-f]{64}$' then
    raise exception 'payload digest must be sha256 hex';
  end if;

  insert into public.owner_decisions_v6(
    idempotency_key,decision_key,subject_type,subject_key,decision,payload_digest,rationale,modifications,evidence_refs
  ) values(
    p_idempotency_key,'owner:'||p_subject_type||':'||p_subject_key||':'||p_idempotency_key,
    p_subject_type,p_subject_key,p_decision,lower(p_payload_digest),p_rationale,
    coalesce(p_modifications,'{}'::jsonb),coalesce(p_evidence_refs,'[]'::jsonb)
  )
  on conflict(idempotency_key) do update set idempotency_key=excluded.idempotency_key
  returning * into v_row;

  insert into public.event_outbox(event_key,topic,event_type,source_ref,payload,payload_digest,priority)
  values(
    'owner.decision:'||p_idempotency_key,
    'owner.decision.recorded',
    'owner_decision',
    'owner_decisions_v6:'||v_row.id::text,
    jsonb_build_object(
      'decisionId',v_row.id,
      'subjectType',v_row.subject_type,
      'subjectKey',v_row.subject_key,
      'decision',v_row.decision,
      'payloadDigest',v_row.payload_digest
    ),
    v_row.payload_digest,
    90
  ) on conflict(event_key) do nothing;

  return v_row;
end;
$$;

create table if not exists public.scheduler_bindings_v6 (
  id uuid primary key default gen_random_uuid(),
  binding_key text not null unique,
  provider text not null,
  purpose text not null,
  cadence_minutes integer not null check (cadence_minutes>=1),
  endpoint_path text not null,
  secret_ref text not null,
  state text not null check (state in ('defined','needs_setup','active','degraded','disabled')),
  environment text not null default 'production',
  evidence_refs jsonb not null default '[]'::jsonb,
  last_verified_at timestamptz,
  last_error jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.scheduler_bindings_v6 enable row level security;
drop trigger if exists scheduler_bindings_v6_set_updated_at on public.scheduler_bindings_v6;
create trigger scheduler_bindings_v6_set_updated_at before update on public.scheduler_bindings_v6 for each row execute function public.creixement_set_updated_at();

insert into public.scheduler_bindings_v6(binding_key,provider,purpose,cadence_minutes,endpoint_path,secret_ref,state,evidence_refs)
values
('vercel-native-daily-fallback','vercel','Daily safety wake-up compatible with Hobby limits.',1440,'/api/tick','CRON_SECRET','defined','["config/creixement-runtime-v5.json"]'::jsonb),
('high-frequency-primary','managed-cloud-scheduler','Primary five-minute autonomic wake-up.',5,'/api/tick','CRON_SECRET','needs_setup','["config/creixement-runtime-v5.json"]'::jsonb)
on conflict(binding_key) do update set provider=excluded.provider,purpose=excluded.purpose,cadence_minutes=excluded.cadence_minutes,
endpoint_path=excluded.endpoint_path,secret_ref=excluded.secret_ref,state=excluded.state,evidence_refs=excluded.evidence_refs,updated_at=now();

create table if not exists public.release_attestations_v6 (
  id uuid primary key default gen_random_uuid(),
  release_key text not null unique,
  branch text not null,
  commit_sha text not null,
  ci_status text not null check (ci_status in ('success','failure','pending','unknown')),
  migration_head text not null,
  runtime_version text not null,
  internal_runtime_ready boolean not null default false,
  high_frequency_scheduler_ready boolean not null default false,
  enabled_job_connector_blockers integer not null default 0,
  critical_drift integer not null default 0,
  critical_incidents integer not null default 0,
  promotable boolean not null default false,
  evidence_refs jsonb not null default '[]'::jsonb,
  assessed_at timestamptz not null default now()
);
create index if not exists release_attestations_v6_sha_idx on public.release_attestations_v6(commit_sha,assessed_at desc);
alter table public.release_attestations_v6 enable row level security;

create or replace view public.v_scheduler_readiness_v6 as
select
  now() as observed_at,
  count(*) filter (where state='active') as active_bindings,
  count(*) filter (where state='active' and cadence_minutes<=5) as high_frequency_bindings,
  coalesce(min(cadence_minutes) filter (where state='active'),0) as best_active_cadence_minutes,
  (count(*) filter (where state='active' and cadence_minutes<=5)>0) as high_frequency_ready
from public.scheduler_bindings_v6;

create or replace view public.v_provider_readiness_v6 as
select
  p.provider_key,p.name,p.provider_type,p.runtime_state,p.rights_status,p.receipt_support,p.idempotent_writes,
  p.required_secrets,p.last_verified_at,
  (p.runtime_state in ('configured','runtime_ready','degraded')) as configured,
  (p.runtime_state='runtime_ready') as runtime_ready,
  (p.rights_status='permitted') as authorized,
  (p.runtime_state='runtime_ready' and p.rights_status='permitted' and p.receipt_support) as operational
from public.provider_registry p;

create or replace view public.v_enabled_job_connector_blockers_v6 as
select d.job_key,r.slug as connector_slug,coalesce(h.effective_health,'missing') as effective_health
from public.job_definitions d
cross join lateral jsonb_array_elements_text(d.required_connectors) as r(slug)
left join public.v_connector_health h on h.slug=r.slug
where d.enabled=true and coalesce(h.effective_health,'missing')<>'runtime_ready';

create or replace view public.v_owner_decision_queue_v6 as
select * from public.owner_decisions_v6 where status='recorded' order by created_at;

create or replace view public.v_operating_health_v6 as
select
  now() as observed_at,
  (select count(*) from public.runtime_heartbeats_v5 where status='healthy' and last_seen_at>=now()-interval '15 minutes') as healthy_runtime_instances,
  (select count(*) from public.job_executions where status='queued') as queued_jobs,
  (select count(*) from public.job_executions where status='failed') as retrying_jobs,
  (select count(*) from public.job_dead_letters_v5 where resolution_status='open') as open_job_dead_letters,
  (select count(*) from public.dead_letter_events where resolution_status='open') as open_outbox_dead_letters,
  (select count(*) from public.circuit_breakers where state='open') as open_handler_circuits,
  (select count(*) from public.runtime_drift_findings_v4 where status='open' and severity='critical') as critical_drift,
  (select count(*) from public.incidents where severity='critical' and status not in ('resolved','closed')) as critical_incidents,
  (select count(*) from public.v_enabled_job_connector_blockers_v6) as enabled_job_connector_blockers,
  (select high_frequency_ready from public.v_scheduler_readiness_v6) as high_frequency_scheduler_ready,
  (select count(*) from public.v_owner_action_queue_v4) as owner_actions,
  (select count(*) from public.v_owner_decision_queue_v6) as recorded_owner_decisions,
  (select count(*) from public.v_goal_queue_v4 where runnable=true and execution_mode='autonomous') as autonomous_goals;

create or replace function public.creixement_assess_release_v6(
  p_release_key text,
  p_branch text,
  p_commit_sha text,
  p_ci_status text,
  p_evidence_refs jsonb default '[]'::jsonb
) returns public.release_attestations_v6
language plpgsql security definer set search_path=public
as $$
declare
  r public.v_runtime_readiness_v5%rowtype;
  s record;
  blocker_count integer;
  v_row public.release_attestations_v6%rowtype;
begin
  if p_ci_status not in ('success','failure','pending','unknown') then raise exception 'invalid ci status'; end if;
  select * into r from public.v_runtime_readiness_v5 limit 1;
  select * into s from public.v_scheduler_readiness_v6 limit 1;
  select count(*) into blocker_count from public.v_enabled_job_connector_blockers_v6;

  insert into public.release_attestations_v6(
    release_key,branch,commit_sha,ci_status,migration_head,runtime_version,
    internal_runtime_ready,high_frequency_scheduler_ready,enabled_job_connector_blockers,
    critical_drift,critical_incidents,promotable,evidence_refs,assessed_at
  ) values(
    p_release_key,p_branch,p_commit_sha,p_ci_status,'010_v6_autonomic_operations.sql','0.6.0',
    coalesce(r.internal_runtime_ready,false),coalesce(s.high_frequency_ready,false),blocker_count,
    coalesce(r.critical_drift,0),coalesce(r.critical_incidents,0),
    p_ci_status='success' and coalesce(r.internal_runtime_ready,false) and coalesce(s.high_frequency_ready,false)
      and blocker_count=0 and coalesce(r.critical_drift,0)=0 and coalesce(r.critical_incidents,0)=0,
    coalesce(p_evidence_refs,'[]'::jsonb),now()
  )
  on conflict(release_key) do update set
    branch=excluded.branch,commit_sha=excluded.commit_sha,ci_status=excluded.ci_status,
    migration_head=excluded.migration_head,runtime_version=excluded.runtime_version,
    internal_runtime_ready=excluded.internal_runtime_ready,
    high_frequency_scheduler_ready=excluded.high_frequency_scheduler_ready,
    enabled_job_connector_blockers=excluded.enabled_job_connector_blockers,
    critical_drift=excluded.critical_drift,critical_incidents=excluded.critical_incidents,
    promotable=excluded.promotable,evidence_refs=excluded.evidence_refs,assessed_at=now()
  returning * into v_row;
  return v_row;
end;
$$;
