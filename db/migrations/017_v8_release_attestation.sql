-- Creixement v8 — release attestation and promotion gate.
-- Apply after 016_v8_kairon_runtime_contract.sql.
-- A release is promotable only when the exact production branch/commit has verified CI, migration,
-- deployment, runtime heartbeat, scheduler and safety evidence.

alter table public.release_attestations_v6 add column if not exists deployment_evidence_verified boolean not null default false;
alter table public.release_attestations_v6 add column if not exists migration_evidence_verified boolean not null default false;
alter table public.release_attestations_v6 add column if not exists production_branch_match boolean not null default false;

create or replace function public.creixement_assess_release_v6(
  p_release_key text,p_branch text,p_commit_sha text,p_ci_status text,p_evidence_refs jsonb default '[]'::jsonb
) returns public.release_attestations_v6
language plpgsql security definer set search_path=public
as $$
declare
  r public.v_runtime_readiness_v5%rowtype;
  s record;
  h record;
  blocker_count integer := 0;
  ci_verified boolean := false;
  deploy_verified boolean := false;
  migration_verified boolean := false;
  matching_runtime integer := 0;
  branch_ok boolean := false;
  v_row public.release_attestations_v6%rowtype;
begin
  if p_ci_status not in ('success','failure','pending','unknown') then raise exception 'invalid ci status'; end if;
  if coalesce(trim(p_commit_sha),'')='' then raise exception 'commit sha is required'; end if;
  branch_ok := p_branch='production/creixement-kairon';

  select * into r from public.v_runtime_readiness_v5 limit 1;
  select * into s from public.v_scheduler_readiness_v6 limit 1;
  select * into h from public.v_operating_health_v6 limit 1;
  select count(*) into blocker_count from public.v_enabled_job_connector_blockers_v6;

  select exists(
    select 1 from public.release_evidence_v6 e
    where e.release_key=p_release_key and e.evidence_type='ci_run' and e.verification_status='verified'
      and e.commit_sha=p_commit_sha and lower(coalesce(e.metadata->>'conclusion',''))='success'
  ) into ci_verified;

  select exists(
    select 1 from public.release_evidence_v6 e
    where e.release_key=p_release_key and e.evidence_type='deployment' and e.verification_status='verified'
      and e.commit_sha=p_commit_sha
  ) into deploy_verified;

  select exists(
    select 1 from public.release_evidence_v6 e
    where e.release_key=p_release_key and e.evidence_type='migration' and e.verification_status='verified'
      and (e.commit_sha is null or e.commit_sha=p_commit_sha)
      and coalesce(e.metadata->>'migrationHead','')='017_v8_release_attestation.sql'
  ) into migration_verified;

  select count(*) into matching_runtime
  from public.runtime_heartbeats_v5
  where status='healthy' and last_seen_at>=now()-interval '15 minutes' and commit_sha=p_commit_sha;

  insert into public.release_attestations_v6(
    release_key,branch,commit_sha,ci_status,migration_head,runtime_version,internal_runtime_ready,
    high_frequency_scheduler_ready,enabled_job_connector_blockers,critical_drift,critical_incidents,
    healthy_runtime_instances,open_job_dead_letters,open_outbox_dead_letters,open_handler_circuits,
    ci_evidence_verified,matching_runtime_instances,deployment_evidence_verified,migration_evidence_verified,
    production_branch_match,promotable,evidence_refs,assessed_at
  ) values(
    p_release_key,p_branch,p_commit_sha,p_ci_status,'017_v8_release_attestation.sql','0.8.0',
    coalesce(r.internal_runtime_ready,false),coalesce(s.high_frequency_ready,false),blocker_count,
    coalesce(r.critical_drift,0),coalesce(r.critical_incidents,0),coalesce(h.healthy_runtime_instances,0),
    coalesce(h.open_job_dead_letters,0),coalesce(h.open_outbox_dead_letters,0),coalesce(h.open_handler_circuits,0),
    ci_verified,matching_runtime,deploy_verified,migration_verified,branch_ok,
    branch_ok and p_ci_status='success' and ci_verified and deploy_verified and migration_verified and matching_runtime>0
      and coalesce(s.high_frequency_ready,false) and blocker_count=0
      and coalesce(r.critical_drift,0)=0 and coalesce(r.critical_incidents,0)=0
      and coalesce(h.open_job_dead_letters,0)=0 and coalesce(h.open_outbox_dead_letters,0)=0
      and coalesce(h.open_handler_circuits,0)=0,
    coalesce(p_evidence_refs,'[]'::jsonb),now()
  )
  on conflict(release_key) do update set
    branch=excluded.branch,commit_sha=excluded.commit_sha,ci_status=excluded.ci_status,
    migration_head=excluded.migration_head,runtime_version=excluded.runtime_version,
    internal_runtime_ready=excluded.internal_runtime_ready,
    high_frequency_scheduler_ready=excluded.high_frequency_scheduler_ready,
    enabled_job_connector_blockers=excluded.enabled_job_connector_blockers,
    critical_drift=excluded.critical_drift,critical_incidents=excluded.critical_incidents,
    healthy_runtime_instances=excluded.healthy_runtime_instances,
    open_job_dead_letters=excluded.open_job_dead_letters,open_outbox_dead_letters=excluded.open_outbox_dead_letters,
    open_handler_circuits=excluded.open_handler_circuits,ci_evidence_verified=excluded.ci_evidence_verified,
    matching_runtime_instances=excluded.matching_runtime_instances,
    deployment_evidence_verified=excluded.deployment_evidence_verified,
    migration_evidence_verified=excluded.migration_evidence_verified,
    production_branch_match=excluded.production_branch_match,promotable=excluded.promotable,
    evidence_refs=excluded.evidence_refs,assessed_at=now()
  returning * into v_row;
  return v_row;
end;
$$;

create or replace view public.v_release_evidence_matrix_v8 as
select
  a.release_key,a.branch,a.commit_sha,a.ci_status,a.runtime_version,a.migration_head,
  a.production_branch_match,a.ci_evidence_verified,a.deployment_evidence_verified,
  a.migration_evidence_verified,a.matching_runtime_instances,a.high_frequency_scheduler_ready,
  a.enabled_job_connector_blockers,a.critical_drift,a.critical_incidents,a.open_job_dead_letters,
  a.open_outbox_dead_letters,a.open_handler_circuits,a.promotable,a.assessed_at,
  (select count(*) from public.release_evidence_v6 e where e.release_key=a.release_key and e.verification_status='verified') as verified_evidence_items,
  (select jsonb_agg(jsonb_build_object('type',e.evidence_type,'reference',e.reference,'verifiedAt',e.verified_at,'commitSha',e.commit_sha) order by e.created_at)
   from public.release_evidence_v6 e where e.release_key=a.release_key and e.verification_status='verified') as verified_evidence
from public.release_attestations_v6 a;

-- Preserve the stable V6 view ABI; strengthen its truth semantics with V8 attestation fields.
create or replace view public.v_production_gate_v6 as
select
  now() as observed_at,
  coalesce((select ci_status='success' and ci_evidence_verified and production_branch_match from public.release_attestations_v6 order by assessed_at desc limit 1),false) as ci_green,
  coalesce((select matching_runtime_instances>0 and deployment_evidence_verified from public.release_attestations_v6 order by assessed_at desc limit 1),false) as runtime_alive,
  coalesce((select high_frequency_ready from public.v_scheduler_readiness_v6 limit 1),false) as scheduler_ready,
  (select count(*)=0 from public.v_enabled_job_connector_blockers_v6) as connector_dependencies_ready,
  coalesce((select critical_drift=0 and critical_incidents=0 and open_job_dead_letters=0 and open_outbox_dead_letters=0 and open_handler_circuits=0 from public.v_operating_health_v6 limit 1),false) as safety_clean,
  coalesce((select promotable from public.release_attestations_v6 order by assessed_at desc limit 1),false) as promotable,
  (select count(*) from public.v_owner_action_queue_v4) as owner_actions,
  (select count(*) from public.v_provider_readiness_v6 where operational=true) as operational_providers;

-- Rebind preflight to the strengthened release gate without changing its public signature.
create or replace function public.creixement_kairon_preflight_v8()
returns table(
  effective_mode text,
  maintenance_allowed boolean,
  economic_l2_allowed boolean,
  reason text,
  global_runtime_state text,
  runtime_alive boolean,
  scheduler_ready boolean,
  safety_clean boolean,
  release_promotable boolean
)
language plpgsql security definer set search_path=public
as $$
declare
  v_global text := 'missing';
  v_runtime_alive boolean := false;
  v_scheduler boolean := false;
  v_safety boolean := false;
  v_promotable boolean := false;
begin
  select state into v_global
  from public.runtime_controls
  where scope_type='global' and scope_key='creixement'
    and (expires_at is null or expires_at>now())
  order by updated_at desc limit 1;
  v_global := coalesce(v_global,'missing');

  select coalesce(runtime_alive,false),coalesce(scheduler_ready,false),coalesce(safety_clean,false),coalesce(promotable,false)
  into v_runtime_alive,v_scheduler,v_safety,v_promotable
  from public.v_production_gate_v6 limit 1;

  return query
  select
    case
      when v_global in ('paused','blocked','emergency_stop') then 'emergency_stop'
      when not v_runtime_alive or not v_safety or not v_scheduler then 'degraded'
      else 'autonomous'
    end,
    (v_global='active'),
    (v_global='active' and v_runtime_alive and v_safety and v_scheduler and v_promotable),
    case
      when v_global<>'active' then 'global runtime control is not active'
      when not v_runtime_alive then 'exact deployed commit is not verified alive'
      when not v_safety then 'runtime safety gate is not clean'
      when not v_scheduler then 'high-frequency scheduler is not verified'
      when not v_promotable then 'release lacks complete verified promotion evidence'
      else 'Kairon maintenance and bounded economic L2 are permitted'
    end,
    v_global,v_runtime_alive,v_scheduler,v_safety,v_promotable;
end;
$$;
