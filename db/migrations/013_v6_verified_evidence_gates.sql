-- Creixement v6.2 verified-evidence gates.
-- Apply after 012_v6_resilience_and_release_integrity.sql.

create table if not exists public.release_evidence_v6 (
  id uuid primary key default gen_random_uuid(),
  evidence_key text not null unique,
  release_key text not null,
  evidence_type text not null check (evidence_type in ('ci_run','deployment','migration','scheduler','manual_review')),
  commit_sha text,
  reference text not null,
  verification_status text not null default 'unverified' check (verification_status in ('unverified','verified','rejected')),
  verifier text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  verified_at timestamptz
);
create index if not exists release_evidence_v6_release_idx on public.release_evidence_v6(release_key,evidence_type,verification_status,created_at desc);
alter table public.release_evidence_v6 enable row level security;

create or replace function public.creixement_record_release_evidence_v6(
  p_evidence_key text,p_release_key text,p_evidence_type text,p_commit_sha text,p_reference text,
  p_verification_status text default 'unverified',p_verifier text default null,p_metadata jsonb default '{}'::jsonb
) returns public.release_evidence_v6
language plpgsql security definer set search_path=public
as $$
declare v_row public.release_evidence_v6%rowtype;
begin
  if p_evidence_type not in ('ci_run','deployment','migration','scheduler','manual_review') then raise exception 'invalid release evidence type'; end if;
  if p_verification_status not in ('unverified','verified','rejected') then raise exception 'invalid release evidence status'; end if;
  if p_verification_status='verified' and coalesce(trim(p_verifier),'')='' then raise exception 'verified evidence requires verifier'; end if;
  insert into public.release_evidence_v6(evidence_key,release_key,evidence_type,commit_sha,reference,verification_status,verifier,metadata,verified_at)
  values(p_evidence_key,p_release_key,p_evidence_type,p_commit_sha,p_reference,p_verification_status,p_verifier,coalesce(p_metadata,'{}'::jsonb),case when p_verification_status='verified' then now() else null end)
  on conflict(evidence_key) do update set
    release_key=excluded.release_key,evidence_type=excluded.evidence_type,commit_sha=excluded.commit_sha,
    reference=excluded.reference,verification_status=excluded.verification_status,verifier=excluded.verifier,
    metadata=excluded.metadata,verified_at=excluded.verified_at
  returning * into v_row;
  return v_row;
end;
$$;

alter table public.scheduler_bindings_v6 add column if not exists verification_receipt_ref text;

create or replace function public.creixement_verify_scheduler_binding_v6(
  p_binding_key text,p_observed_cadence_minutes integer,p_evidence_ref text,p_receipt_ref text
) returns public.scheduler_bindings_v6
language plpgsql security definer set search_path=public
as $$
declare v_row public.scheduler_bindings_v6%rowtype;
begin
  if p_observed_cadence_minutes<1 then raise exception 'observed cadence must be positive'; end if;
  if coalesce(trim(p_evidence_ref),'')='' or coalesce(trim(p_receipt_ref),'')='' then raise exception 'scheduler verification requires evidence and receipt'; end if;
  select * into v_row from public.scheduler_bindings_v6 where binding_key=p_binding_key for update;
  if not found then raise exception 'scheduler binding not found'; end if;
  update public.scheduler_bindings_v6
  set state=case when p_observed_cadence_minutes<=cadence_minutes then 'active' else 'degraded' end,
      last_verified_at=now(),last_error=case when p_observed_cadence_minutes<=cadence_minutes then null else jsonb_build_object('code','cadence_slower_than_contract','observedMinutes',p_observed_cadence_minutes) end,
      evidence_refs=coalesce(evidence_refs,'[]'::jsonb) || jsonb_build_array(p_evidence_ref),
      verification_receipt_ref=p_receipt_ref,updated_at=now()
  where id=v_row.id returning * into v_row;
  return v_row;
end;
$$;

create or replace view public.v_scheduler_readiness_v6 as
select
  now() as observed_at,
  count(*) filter (where state='active' and last_verified_at is not null and verification_receipt_ref is not null) as verified_active_bindings,
  count(*) filter (where state='active' and cadence_minutes<=5 and last_verified_at is not null
    and last_verified_at>=now()-interval '7 days' and verification_receipt_ref is not null and jsonb_array_length(evidence_refs)>0) as high_frequency_bindings,
  coalesce(min(cadence_minutes) filter (where state='active' and last_verified_at is not null and verification_receipt_ref is not null),0) as best_active_cadence_minutes,
  (count(*) filter (where state='active' and cadence_minutes<=5 and last_verified_at is not null
    and last_verified_at>=now()-interval '7 days' and verification_receipt_ref is not null and jsonb_array_length(evidence_refs)>0)>0) as high_frequency_ready
from public.scheduler_bindings_v6;

create or replace view public.v_provider_readiness_v6 as
select
  p.provider_key,p.name,p.provider_type,p.runtime_state,p.rights_status,p.receipt_support,p.idempotent_writes,
  p.required_secrets,p.last_verified_at,
  (p.runtime_state in ('configured','runtime_ready','degraded')) as configured,
  (p.runtime_state='runtime_ready' and p.last_verified_at is not null) as runtime_ready,
  (p.rights_status='permitted') as authorized,
  (p.runtime_state='runtime_ready' and p.rights_status='permitted' and p.receipt_support
    and p.last_verified_at is not null and p.last_verified_at>=now()-interval '30 days') as operational
from public.provider_registry p;

alter table public.release_attestations_v6 add column if not exists ci_evidence_verified boolean not null default false;
alter table public.release_attestations_v6 add column if not exists matching_runtime_instances integer not null default 0;

create or replace function public.creixement_assess_release_v6(
  p_release_key text,p_branch text,p_commit_sha text,p_ci_status text,p_evidence_refs jsonb default '[]'::jsonb
) returns public.release_attestations_v6
language plpgsql security definer set search_path=public
as $$
declare
  r public.v_runtime_readiness_v5%rowtype; s record; h record; blocker_count integer;
  ci_verified boolean := false; matching_runtime integer := 0; v_row public.release_attestations_v6%rowtype;
begin
  if p_ci_status not in ('success','failure','pending','unknown') then raise exception 'invalid ci status'; end if;
  select * into r from public.v_runtime_readiness_v5 limit 1;
  select * into s from public.v_scheduler_readiness_v6 limit 1;
  select * into h from public.v_operating_health_v6 limit 1;
  select count(*) into blocker_count from public.v_enabled_job_connector_blockers_v6;
  select exists(
    select 1 from public.release_evidence_v6 e
    where e.release_key=p_release_key and e.evidence_type='ci_run' and e.verification_status='verified'
      and e.commit_sha=p_commit_sha and lower(coalesce(e.metadata->>'conclusion',''))='success'
  ) into ci_verified;
  select count(*) into matching_runtime from public.runtime_heartbeats_v5
    where status='healthy' and last_seen_at>=now()-interval '15 minutes' and commit_sha=p_commit_sha;

  insert into public.release_attestations_v6(
    release_key,branch,commit_sha,ci_status,migration_head,runtime_version,internal_runtime_ready,
    high_frequency_scheduler_ready,enabled_job_connector_blockers,critical_drift,critical_incidents,
    healthy_runtime_instances,open_job_dead_letters,open_outbox_dead_letters,open_handler_circuits,
    ci_evidence_verified,matching_runtime_instances,promotable,evidence_refs,assessed_at
  ) values(
    p_release_key,p_branch,p_commit_sha,p_ci_status,'013_v6_verified_evidence_gates.sql','0.6.2',
    coalesce(r.internal_runtime_ready,false),coalesce(s.high_frequency_ready,false),blocker_count,
    coalesce(r.critical_drift,0),coalesce(r.critical_incidents,0),coalesce(h.healthy_runtime_instances,0),
    coalesce(h.open_job_dead_letters,0),coalesce(h.open_outbox_dead_letters,0),coalesce(h.open_handler_circuits,0),
    ci_verified,matching_runtime,
    p_ci_status='success' and ci_verified and matching_runtime>0 and coalesce(s.high_frequency_ready,false)
      and blocker_count=0 and coalesce(r.critical_drift,0)=0 and coalesce(r.critical_incidents,0)=0
      and coalesce(h.open_job_dead_letters,0)=0 and coalesce(h.open_outbox_dead_letters,0)=0 and coalesce(h.open_handler_circuits,0)=0,
    coalesce(p_evidence_refs,'[]'::jsonb),now()
  )
  on conflict(release_key) do update set branch=excluded.branch,commit_sha=excluded.commit_sha,ci_status=excluded.ci_status,
    migration_head=excluded.migration_head,runtime_version=excluded.runtime_version,internal_runtime_ready=excluded.internal_runtime_ready,
    high_frequency_scheduler_ready=excluded.high_frequency_scheduler_ready,enabled_job_connector_blockers=excluded.enabled_job_connector_blockers,
    critical_drift=excluded.critical_drift,critical_incidents=excluded.critical_incidents,
    healthy_runtime_instances=excluded.healthy_runtime_instances,open_job_dead_letters=excluded.open_job_dead_letters,
    open_outbox_dead_letters=excluded.open_outbox_dead_letters,open_handler_circuits=excluded.open_handler_circuits,
    ci_evidence_verified=excluded.ci_evidence_verified,matching_runtime_instances=excluded.matching_runtime_instances,
    promotable=excluded.promotable,evidence_refs=excluded.evidence_refs,assessed_at=now()
  returning * into v_row;
  return v_row;
end;
$$;

create or replace view public.v_production_gate_v6 as
select
  now() as observed_at,
  coalesce((select ci_status='success' and ci_evidence_verified from public.release_attestations_v6 order by assessed_at desc limit 1),false) as ci_verified_green,
  coalesce((select matching_runtime_instances>0 from public.release_attestations_v6 order by assessed_at desc limit 1),false) as deployed_commit_alive,
  coalesce((select high_frequency_ready from public.v_scheduler_readiness_v6 limit 1),false) as scheduler_verified_ready,
  (select count(*)=0 from public.v_enabled_job_connector_blockers_v6) as connector_dependencies_ready,
  coalesce((select critical_drift=0 and critical_incidents=0 and open_job_dead_letters=0 and open_outbox_dead_letters=0 and open_handler_circuits=0 from public.v_operating_health_v6 limit 1),false) as safety_clean,
  coalesce((select promotable from public.release_attestations_v6 order by assessed_at desc limit 1),false) as promotable,
  (select count(*) from public.v_owner_action_queue_v4) as owner_actions,
  (select count(*) from public.v_provider_readiness_v6 where operational=true) as operational_providers;

create or replace view public.v_truth_grade_v6 as
select 'runtime'::text as kind,runtime_id as state_key,
       case when status='healthy' and last_seen_at>=now()-interval '15 minutes' then 'externally_observed_runtime' else 'stale_or_unhealthy' end as truth_state,
       last_seen_at as observed_at,jsonb_build_object('version',version,'commitSha',commit_sha,'status',status) as evidence
from public.runtime_heartbeats_v5
union all
select 'scheduler',binding_key,
       case when state='active' and last_verified_at is not null and verification_receipt_ref is not null then 'verified' else state end,
       last_verified_at,jsonb_build_object('provider',provider,'cadenceMinutes',cadence_minutes,'receipt',verification_receipt_ref)
from public.scheduler_bindings_v6
union all
select 'provider',provider_key,
       case when runtime_state='runtime_ready' and rights_status='permitted' and receipt_support and last_verified_at is not null then 'verified_operational_candidate' else runtime_state end,
       last_verified_at,jsonb_build_object('rights',rights_status,'receiptSupport',receipt_support)
from public.provider_registry;
