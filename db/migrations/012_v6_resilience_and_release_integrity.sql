-- Creixement v6.1 resilience and release-integrity hardening.
-- Apply after 011_v6_invariant_guards.sql.

-- Preserve drift history while allowing one current/open finding per field.
alter table public.runtime_drift_findings_v4 add column if not exists last_seen_at timestamptz;
alter table public.runtime_drift_findings_v4 drop constraint if exists runtime_drift_findings_v4_kind_state_key_field_status_key;
create unique index if not exists runtime_drift_findings_v4_single_open_idx
  on public.runtime_drift_findings_v4(kind,state_key,field) where status='open';

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
  v_seen timestamptz := clock_timestamp();
  v_id uuid;
begin
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
    actual := coalesce(actual,'{}'::jsonb);

    insert into public.observed_runtime_state_v4(kind,state_key,observed,evidence_refs,observed_at)
    values(d.kind,d.state_key,actual,jsonb_build_array('runtime-reconcile-v6.1'),v_seen)
    on conflict(kind,state_key) do update set observed=excluded.observed,evidence_refs=excluded.evidence_refs,observed_at=excluded.observed_at;

    for f in select jsonb_object_keys(d.desired) loop
      expected_value := d.desired -> f;
      observed_value := actual -> f;
      if observed_value is distinct from expected_value then
        sev := case when d.kind in ('policy','service') then 'critical' when d.kind in ('connector','job') then 'warning' else 'info' end;
        remedy := case when d.auto_remediate and d.kind in ('job','agent') then 'automatic' else 'approval_required' end;
        update public.runtime_drift_findings_v4
        set desired=expected_value,observed=observed_value,severity=sev,remediation=remedy,
            evidence_refs=jsonb_build_array('runtime-reconcile-v6.1'),last_seen_at=v_seen,resolved_at=null
        where kind=d.kind and state_key=d.state_key and field=f and status='open'
        returning id into v_id;
        if v_id is null then
          insert into public.runtime_drift_findings_v4(kind,state_key,field,desired,observed,severity,remediation,status,evidence_refs,detected_at,last_seen_at)
          values(d.kind,d.state_key,f,expected_value,observed_value,sev,remedy,'open',jsonb_build_array('runtime-reconcile-v6.1'),v_seen,v_seen);
        end if;
        v_id := null;
        return query select d.kind,d.state_key,f,sev,remedy;
      end if;
    end loop;
  end loop;

  update public.runtime_drift_findings_v4
  set status='resolved',resolved_at=v_seen
  where status='open' and coalesce(last_seen_at,detected_at)<v_seen;
end;
$$;

-- Recover work after worker death. Crashed leases must never strand forever.
create or replace function public.creixement_reap_expired_leases_v6()
returns table(job_requeued integer,job_dead_lettered integer,outbox_requeued integer,outbox_dead_lettered integer)
language plpgsql security definer set search_path=public
as $$
declare
  j_retry integer := 0; j_dead integer := 0; o_retry integer := 0; o_dead integer := 0;
begin
  update public.job_executions j
  set status='failed',lease_owner=null,lease_until=null,scheduled_for=now(),
      last_error=jsonb_build_object('code','lease_expired','recoveredAt',now()),updated_at=now()
  from public.job_definitions d
  where j.job_definition_id=d.id and j.status in ('leased','running') and j.lease_until<now() and j.attempt<d.max_attempts;
  get diagnostics j_retry = row_count;

  with expired as (
    update public.job_executions j
    set status='dead_lettered',lease_owner=null,lease_until=null,completed_at=now(),
        last_error=jsonb_build_object('code','lease_expired_after_max_attempts','recoveredAt',now()),updated_at=now()
    from public.job_definitions d
    where j.job_definition_id=d.id and j.status in ('leased','running') and j.lease_until<now() and j.attempt>=d.max_attempts
    returning j.*,d.job_key,d.max_attempts
  )
  insert into public.job_dead_letters_v5(job_execution_id,job_definition_id,job_key,correlation_id,idempotency_key,attempts,final_error,input,dead_lettered_at)
  select id,job_definition_id,job_key,correlation_id,idempotency_key,attempt,last_error,input,now() from expired
  on conflict(job_execution_id) do update set attempts=excluded.attempts,final_error=excluded.final_error,resolution_status='open',dead_lettered_at=now();
  get diagnostics j_dead = row_count;

  update public.event_outbox
  set status='failed',lease_owner=null,lease_until=null,available_at=now(),
      last_error=jsonb_build_object('code','lease_expired','recoveredAt',now()),updated_at=now()
  where status='leased' and lease_until<now() and attempts<max_attempts;
  get diagnostics o_retry = row_count;

  with expired as (
    update public.event_outbox
    set status='dead_lettered',lease_owner=null,lease_until=null,
        last_error=jsonb_build_object('code','lease_expired_after_max_attempts','recoveredAt',now()),updated_at=now()
    where status='leased' and lease_until<now() and attempts>=max_attempts
    returning *
  )
  insert into public.dead_letter_events(outbox_event_id,event_key,topic,payload,final_error,attempts,first_seen_at,dead_lettered_at,resolution_status)
  select id,event_key,topic,payload,last_error,attempts,created_at,now(),'open' from expired
  on conflict(event_key) do update set final_error=excluded.final_error,attempts=excluded.attempts,dead_lettered_at=now(),resolution_status='open';
  get diagnostics o_dead = row_count;

  return query select j_retry,j_dead,o_retry,o_dead;
end;
$$;

-- Claims enforce definition concurrency and can recover stale leases defensively.
create or replace function public.creixement_claim_jobs(worker text,batch_size integer default 10,lease_for_seconds integer default 600)
returns setof public.job_executions
language plpgsql security definer set search_path=public
as $$
begin
  return query
  with picked as (
    select j.id,d.lease_seconds
    from public.job_executions j
    join public.job_definitions d on d.id=j.job_definition_id
    where d.enabled=true
      and (j.status in ('queued','failed') or (j.status in ('leased','running') and j.lease_until<now()))
      and j.attempt<d.max_attempts
      and coalesce(j.scheduled_for,j.created_at)<=now()
      and (j.lease_until is null or j.lease_until<now())
      and (
        select count(*) from public.job_executions active
        where active.job_definition_id=j.job_definition_id
          and active.id<>j.id
          and active.status in ('leased','running')
          and (active.lease_until is null or active.lease_until>now())
      ) < d.concurrency_limit
    order by coalesce(j.scheduled_for,j.created_at),j.created_at
    for update of j skip locked
    limit greatest(1,least(batch_size,50))
  )
  update public.job_executions j
  set status='leased',lease_owner=worker,
      lease_until=now()+make_interval(secs=>greatest(10,least(p.lease_seconds,greatest(10,lease_for_seconds)))),
      attempt=j.attempt+1,started_at=coalesce(j.started_at,now()),updated_at=now()
  from picked p where j.id=p.id
  returning j.*;
end;
$$;

create or replace function public.creixement_claim_outbox(worker text,batch_size integer default 20,lease_for_seconds integer default 120)
returns setof public.event_outbox
language plpgsql security definer set search_path=public
as $$
begin
  return query
  with picked as (
    select id from public.event_outbox
    where (status in ('pending','failed') or (status='leased' and lease_until<now()))
      and available_at<=now() and (lease_until is null or lease_until<now()) and attempts<max_attempts
    order by priority desc,available_at,created_at
    for update skip locked
    limit greatest(1,least(batch_size,100))
  )
  update public.event_outbox e
  set status='leased',lease_owner=worker,lease_until=now()+make_interval(secs=>greatest(10,lease_for_seconds)),
      attempts=attempts+1,updated_at=now()
  from picked p where e.id=p.id
  returning e.*;
end;
$$;

-- Half-open means exactly one in-flight probe, not unlimited probes.
create or replace function public.creixement_handler_circuit_decision_v6(p_handler text)
returns table(allowed boolean,state text,reason text)
language plpgsql security definer set search_path=public
as $$
declare v_breaker public.circuit_breakers%rowtype;
begin
  select * into v_breaker from public.circuit_breakers where scope_type='handler' and scope_key=p_handler for update;
  if not found then return query select true,'closed'::text,'no handler circuit exists; execution permitted'::text; return; end if;
  if v_breaker.state='open' and v_breaker.retry_at is not null and v_breaker.retry_at>now() then
    return query select false,'open'::text,'handler circuit is open until '||v_breaker.retry_at::text; return;
  end if;
  if v_breaker.state='open' then
    update public.circuit_breakers set state='half_open',retry_at=now()+make_interval(secs=>cooldown_seconds),updated_at=now() where id=v_breaker.id;
    return query select true,'half_open'::text,'cooldown elapsed; single probe execution permitted'::text; return;
  end if;
  if v_breaker.state='half_open' then
    if v_breaker.retry_at is null or v_breaker.retry_at<=now() then
      update public.circuit_breakers set retry_at=now()+make_interval(secs=>cooldown_seconds),updated_at=now() where id=v_breaker.id;
      return query select true,'half_open'::text,'previous probe timed out; replacement probe permitted'::text; return;
    end if;
    return query select false,'half_open'::text,'probe already in flight; concurrent probe denied'::text; return;
  end if;
  return query select true,v_breaker.state,'handler circuit permits execution'::text;
end;
$$;

-- Idempotency keys are content-addressed promises: conflicting reuse is an error.
create or replace function public.creixement_submit_owner_decision_v6(
  p_idempotency_key text,p_subject_type text,p_subject_key text,p_decision text,p_payload_digest text,
  p_rationale text default null,p_modifications jsonb default '{}'::jsonb,p_evidence_refs jsonb default '[]'::jsonb
) returns public.owner_decisions_v6
language plpgsql security definer set search_path=public
as $$
declare v_row public.owner_decisions_v6%rowtype;
begin
  if p_subject_type not in ('goal','approval','action','release','connector','policy','other') then raise exception 'invalid subject type'; end if;
  if p_decision not in ('approve','reject','defer','modify') then raise exception 'invalid owner decision'; end if;
  if p_payload_digest !~ '^[0-9A-Fa-f]{64}$' then raise exception 'payload digest must be sha256 hex'; end if;

  select * into v_row from public.owner_decisions_v6 where idempotency_key=p_idempotency_key;
  if found then
    if v_row.subject_type<>p_subject_type or v_row.subject_key<>p_subject_key or v_row.decision<>p_decision
       or lower(v_row.payload_digest)<>lower(p_payload_digest)
       or coalesce(v_row.rationale,'')<>coalesce(p_rationale,'')
       or v_row.modifications<>coalesce(p_modifications,'{}'::jsonb)
       or v_row.evidence_refs<>coalesce(p_evidence_refs,'[]'::jsonb) then
      raise exception 'idempotency key reused with conflicting owner-decision content';
    end if;
  else
    insert into public.owner_decisions_v6(idempotency_key,decision_key,subject_type,subject_key,decision,payload_digest,rationale,modifications,evidence_refs)
    values(p_idempotency_key,'owner:'||p_subject_type||':'||p_subject_key||':'||p_idempotency_key,p_subject_type,p_subject_key,p_decision,lower(p_payload_digest),p_rationale,coalesce(p_modifications,'{}'::jsonb),coalesce(p_evidence_refs,'[]'::jsonb))
    returning * into v_row;
  end if;

  insert into public.event_outbox(event_key,topic,event_type,source_ref,payload,payload_digest,priority)
  values('owner.decision:'||p_idempotency_key,'owner.decision.recorded','owner_decision','owner_decisions_v6:'||v_row.id::text,
    jsonb_build_object('decisionId',v_row.id,'subjectType',v_row.subject_type,'subjectKey',v_row.subject_key,'decision',v_row.decision,'payloadDigest',v_row.payload_digest),v_row.payload_digest,90)
  on conflict(event_key) do nothing;
  return v_row;
end;
$$;

create or replace function public.creixement_guard_owner_decision_v6()
returns trigger language plpgsql set search_path=public
as $$
begin
  if new.idempotency_key is distinct from old.idempotency_key or new.decision_key is distinct from old.decision_key
     or new.subject_type is distinct from old.subject_type or new.subject_key is distinct from old.subject_key
     or new.decision is distinct from old.decision or new.payload_digest is distinct from old.payload_digest
     or new.rationale is distinct from old.rationale or new.modifications is distinct from old.modifications
     or new.evidence_refs is distinct from old.evidence_refs or new.actor is distinct from old.actor
     or new.created_at is distinct from old.created_at then
    raise exception 'recorded owner-decision content is immutable';
  end if;
  return new;
end;
$$;

alter table public.release_attestations_v6 add column if not exists healthy_runtime_instances integer not null default 0;
alter table public.release_attestations_v6 add column if not exists open_job_dead_letters integer not null default 0;
alter table public.release_attestations_v6 add column if not exists open_outbox_dead_letters integer not null default 0;
alter table public.release_attestations_v6 add column if not exists open_handler_circuits integer not null default 0;

create or replace function public.creixement_assess_release_v6(
  p_release_key text,p_branch text,p_commit_sha text,p_ci_status text,p_evidence_refs jsonb default '[]'::jsonb
) returns public.release_attestations_v6
language plpgsql security definer set search_path=public
as $$
declare
  r public.v_runtime_readiness_v5%rowtype; s record; h record; blocker_count integer; v_row public.release_attestations_v6%rowtype;
begin
  if p_ci_status not in ('success','failure','pending','unknown') then raise exception 'invalid ci status'; end if;
  select * into r from public.v_runtime_readiness_v5 limit 1;
  select * into s from public.v_scheduler_readiness_v6 limit 1;
  select * into h from public.v_operating_health_v6 limit 1;
  select count(*) into blocker_count from public.v_enabled_job_connector_blockers_v6;

  insert into public.release_attestations_v6(
    release_key,branch,commit_sha,ci_status,migration_head,runtime_version,internal_runtime_ready,
    high_frequency_scheduler_ready,enabled_job_connector_blockers,critical_drift,critical_incidents,
    healthy_runtime_instances,open_job_dead_letters,open_outbox_dead_letters,open_handler_circuits,promotable,evidence_refs,assessed_at
  ) values(
    p_release_key,p_branch,p_commit_sha,p_ci_status,'012_v6_resilience_and_release_integrity.sql','0.6.1',
    coalesce(r.internal_runtime_ready,false),coalesce(s.high_frequency_ready,false),blocker_count,
    coalesce(r.critical_drift,0),coalesce(r.critical_incidents,0),coalesce(h.healthy_runtime_instances,0),
    coalesce(h.open_job_dead_letters,0),coalesce(h.open_outbox_dead_letters,0),coalesce(h.open_handler_circuits,0),
    p_ci_status='success' and coalesce(r.internal_runtime_ready,false) and coalesce(s.high_frequency_ready,false)
      and blocker_count=0 and coalesce(r.critical_drift,0)=0 and coalesce(r.critical_incidents,0)=0
      and coalesce(h.healthy_runtime_instances,0)>0 and coalesce(h.open_job_dead_letters,0)=0
      and coalesce(h.open_outbox_dead_letters,0)=0 and coalesce(h.open_handler_circuits,0)=0,
    coalesce(p_evidence_refs,'[]'::jsonb),now()
  )
  on conflict(release_key) do update set branch=excluded.branch,commit_sha=excluded.commit_sha,ci_status=excluded.ci_status,
    migration_head=excluded.migration_head,runtime_version=excluded.runtime_version,internal_runtime_ready=excluded.internal_runtime_ready,
    high_frequency_scheduler_ready=excluded.high_frequency_scheduler_ready,enabled_job_connector_blockers=excluded.enabled_job_connector_blockers,
    critical_drift=excluded.critical_drift,critical_incidents=excluded.critical_incidents,
    healthy_runtime_instances=excluded.healthy_runtime_instances,open_job_dead_letters=excluded.open_job_dead_letters,
    open_outbox_dead_letters=excluded.open_outbox_dead_letters,open_handler_circuits=excluded.open_handler_circuits,
    promotable=excluded.promotable,evidence_refs=excluded.evidence_refs,assessed_at=now()
  returning * into v_row;
  return v_row;
end;
$$;

create or replace view public.v_production_gate_v6 as
select
  now() as observed_at,
  coalesce((select ci_status='success' from public.release_attestations_v6 order by assessed_at desc limit 1),false) as ci_green,
  coalesce((select healthy_runtime_instances>0 from public.v_operating_health_v6 limit 1),false) as runtime_alive,
  coalesce((select high_frequency_ready from public.v_scheduler_readiness_v6 limit 1),false) as scheduler_ready,
  (select count(*)=0 from public.v_enabled_job_connector_blockers_v6) as connector_dependencies_ready,
  coalesce((select critical_drift=0 and critical_incidents=0 and open_job_dead_letters=0 and open_outbox_dead_letters=0 and open_handler_circuits=0 from public.v_operating_health_v6 limit 1),false) as safety_clean,
  coalesce((select promotable from public.release_attestations_v6 order by assessed_at desc limit 1),false) as promotable,
  (select count(*) from public.v_owner_action_queue_v4) as owner_actions,
  (select count(*) from public.v_provider_readiness_v6 where operational=true) as operational_providers;
