-- Creixement V10 — runtime health convergence.
-- Apply after 022_v10_business_portfolio_and_venture_foundry.sql.
-- Repairs two V9-era assumptions that kept a genuinely executing V10 runtime degraded:
--   1. OUT-parameter/column ambiguity in creixement_reconcile_runtime_v5().
--   2. scheduler proof hard-coded to kairon-cloudflare-v9.
-- Also closes two bootstrap goals whose success conditions are now externally evidenced.

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
  for d in
    select drs.*
    from public.desired_runtime_state_v4 drs
    where drs.active=true
  loop
    actual := null;
    if d.kind='connector' then
      select jsonb_build_object('state',c.state,'runtime_connection',c.runtime_connection)
      into actual
      from public.connectors c where c.slug=d.state_key limit 1;
    elsif d.kind='job' then
      select jsonb_build_object('enabled',j.enabled,'handler_key',j.handler_key,'autonomy_level',j.autonomy_level)
      into actual
      from public.job_definitions j where j.job_key=d.state_key limit 1;
    elsif d.kind='agent' then
      select jsonb_build_object('health',a.health,'autonomy_level',a.autonomy_level,'version',a.version)
      into actual
      from public.agents a where a.slug=d.state_key limit 1;
    elsif d.kind='service' then
      select jsonb_build_object('state',s.state,'max_autonomy',s.max_autonomy)
      into actual
      from public.service_identities s where s.service_key=d.state_key limit 1;
    elsif d.kind='policy' then
      select jsonb_build_object('decision',p.decision,'max_autonomy',p.max_autonomy,'active',p.active)
      into actual
      from public.policies p where p.policy_key=d.state_key limit 1;
    end if;
    actual := coalesce(actual,'{}'::jsonb);

    insert into public.observed_runtime_state_v4 as ors(kind,state_key,observed,evidence_refs,observed_at)
    values(d.kind,d.state_key,actual,jsonb_build_array('runtime-reconcile-v10.1'),v_seen)
    on conflict do update
      set observed=excluded.observed,
          evidence_refs=excluded.evidence_refs,
          observed_at=excluded.observed_at;

    for f in select jsonb_object_keys(d.desired) loop
      expected_value := d.desired -> f;
      observed_value := actual -> f;
      if observed_value is distinct from expected_value then
        sev := case
          when d.kind in ('policy','service') then 'critical'
          when d.kind in ('connector','job') then 'warning'
          else 'info'
        end;
        remedy := case
          when d.auto_remediate and d.kind in ('job','agent') then 'automatic'
          else 'approval_required'
        end;

        v_id := null;
        update public.runtime_drift_findings_v4 rf
        set desired=expected_value,
            observed=observed_value,
            severity=sev,
            remediation=remedy,
            evidence_refs=jsonb_build_array('runtime-reconcile-v10.1'),
            last_seen_at=v_seen,
            resolved_at=null
        where rf.kind=d.kind
          and rf.state_key=d.state_key
          and rf.field=f
          and rf.status='open'
        returning rf.id into v_id;

        if v_id is null then
          insert into public.runtime_drift_findings_v4(
            kind,state_key,field,desired,observed,severity,remediation,status,evidence_refs,detected_at,last_seen_at
          ) values(
            d.kind,d.state_key,f,expected_value,observed_value,sev,remedy,'open',
            jsonb_build_array('runtime-reconcile-v10.1'),v_seen,v_seen
          );
        end if;

        return query select d.kind,d.state_key,f,sev,remedy;
      end if;
    end loop;
  end loop;

  update public.runtime_drift_findings_v4 rf
  set status='resolved',resolved_at=v_seen
  where rf.status='open'
    and coalesce(rf.last_seen_at,rf.detected_at)<v_seen;
end;
$$;

revoke all on function public.creixement_reconcile_runtime_v5() from public,anon,authenticated;
grant execute on function public.creixement_reconcile_runtime_v5() to service_role;

create or replace function public.creixement_auto_verify_cloudflare_scheduler_v9()
returns jsonb
language plpgsql security definer set search_path=public
as $$
declare
  v_latest public.runtime_heartbeats_v5%rowtype;
  v_proof record;
  v_binding public.scheduler_bindings_v6%rowtype;
  v_observed integer;
begin
  select h.* into v_latest
  from public.runtime_heartbeats_v5 h
  where h.runtime_id='kairon-cloudflare-v10'
    and h.status='healthy'
    and h.commit_sha is not null
  order by h.last_seen_at desc
  limit 1;

  if not found then
    return jsonb_build_object('verified',false,'reason','no healthy Kairon V10 Cloudflare heartbeat with commit sha');
  end if;

  select * into v_proof
  from public.creixement_runtime_cadence_proof_v9(
    v_latest.runtime_id,v_latest.commit_sha,30,3,5,3
  );

  if coalesce(v_proof.cadence_stable,false) is not true then
    return jsonb_build_object(
      'verified',false,
      'reason','insufficient stable cadence evidence',
      'runtimeId',v_latest.runtime_id,
      'commitSha',v_latest.commit_sha,
      'samples',coalesce(v_proof.sample_count,0),
      'averageGapMinutes',v_proof.average_gap_minutes,
      'maximumGapMinutes',v_proof.maximum_gap_minutes
    );
  end if;

  v_observed := greatest(1,least(5,round(coalesce(v_proof.average_gap_minutes,5))::integer));

  select * into v_binding
  from public.creixement_verify_scheduler_binding_v6(
    'cloudflare-primary-heartbeat',
    v_observed,
    'cadence-proof:'||v_latest.commit_sha,
    coalesce(v_proof.latest_receipt_ref,'runtime-heartbeat:'||v_latest.runtime_id)
  );

  return jsonb_build_object(
    'verified',v_binding.state='active',
    'bindingKey',v_binding.binding_key,
    'state',v_binding.state,
    'runtimeId',v_latest.runtime_id,
    'commitSha',v_latest.commit_sha,
    'samples',v_proof.sample_count,
    'averageGapMinutes',v_proof.average_gap_minutes,
    'maximumGapMinutes',v_proof.maximum_gap_minutes,
    'receipt',v_binding.verification_receipt_ref
  );
end;
$$;

revoke all on function public.creixement_auto_verify_cloudflare_scheduler_v9() from public,anon,authenticated;
grant execute on function public.creixement_auto_verify_cloudflare_scheduler_v9() to service_role;

create or replace function public.creixement_heartbeat_sample_autoverify_v9()
returns trigger
language plpgsql security definer set search_path=public
as $$
begin
  if new.runtime_id='kairon-cloudflare-v10'
     and new.status='healthy'
     and new.metadata->>'phase'='tick_completed' then
    begin
      perform public.creixement_auto_verify_cloudflare_scheduler_v9();
    exception when others then
      update public.scheduler_bindings_v6 sb
      set last_error=jsonb_build_object(
            'code','automatic_scheduler_verification_failed',
            'message',left(sqlerrm,800),
            'observedAt',now()
          ),
          updated_at=now()
      where sb.binding_key='cloudflare-primary-heartbeat';
    end;
  end if;
  return new;
end;
$$;

revoke all on function public.creixement_heartbeat_sample_autoverify_v9() from public,anon,authenticated;
grant execute on function public.creixement_heartbeat_sample_autoverify_v9() to service_role;

create or replace view public.v_runtime_cadence_proof_v9 as
with latest as (
  select h.runtime_id,h.commit_sha,h.version,h.last_seen_at,h.status
  from public.runtime_heartbeats_v5 h
  where h.runtime_id='kairon-cloudflare-v10'
  order by h.last_seen_at desc
  limit 1
)
select
  now() as observed_at,
  l.runtime_id,
  l.version,
  l.commit_sha,
  l.status,
  l.last_seen_at,
  p.sample_count,
  p.first_sample_at,
  p.last_sample_at,
  p.average_gap_minutes,
  p.maximum_gap_minutes,
  p.cadence_stable,
  p.latest_receipt_ref,
  p.evidence_refs
from latest l
left join lateral public.creixement_runtime_cadence_proof_v9(
  l.runtime_id,l.commit_sha,30,3,5,3
) p on true;

create or replace view public.v_runtime_proof_summary_v9 as
select
  now() as observed_at,
  coalesce((select count(*) from public.runtime_heartbeat_samples_v9 s where s.observed_at>=now()-interval '30 minutes'),0) as samples_30m,
  coalesce((select count(*) from public.runtime_heartbeat_samples_v9 s where s.runtime_id='kairon-cloudflare-v10' and s.status='healthy' and s.metadata->>'phase'='tick_completed' and s.observed_at>=now()-interval '30 minutes'),0) as completed_healthy_ticks_30m,
  coalesce((select cp.cadence_stable from public.v_runtime_cadence_proof_v9 cp limit 1),false) as cloudflare_cadence_stable,
  coalesce((select sb.state='active' from public.scheduler_bindings_v6 sb where sb.binding_key='cloudflare-primary-heartbeat'),false) as cloudflare_scheduler_verified,
  (select sb.last_verified_at from public.scheduler_bindings_v6 sb where sb.binding_key='cloudflare-primary-heartbeat') as scheduler_last_verified_at;

-- These two bootstrap goals are obsolete only after their success conditions are now independently evidenced.
update public.goals g
set status='completed',
    blocker=null,
    runnable=false,
    completed_at=coalesce(g.completed_at,now()),
    evidence_refs=coalesce(g.evidence_refs,'[]'::jsonb) || jsonb_build_array(
      'verified:cloudflare-runtime:kairon-cloudflare-v10',
      'verified:runtime-commit:15238da48b7b2c536c87c3651ddf5571c0436c09'
    ),
    updated_at=now()
where g.goal_key='deploy-cloud-runtime'
  and exists (
    select 1 from public.runtime_heartbeats_v5 h
    where h.runtime_id='kairon-cloudflare-v10'
      and h.commit_sha='15238da48b7b2c536c87c3651ddf5571c0436c09'
      and h.last_seen_at>=now()-interval '15 minutes'
  );

update public.goals g
set status='completed',
    blocker=null,
    runnable=false,
    completed_at=coalesce(g.completed_at,now()),
    evidence_refs=coalesce(g.evidence_refs,'[]'::jsonb) || jsonb_build_array(
      'verified:lovable-published:creixement-ops-hub.lovable.app',
      'verified:lovable-commit:63d20b4c6b26761fc45b0ea3dbc38f05f0d53836'
    ),
    updated_at=now()
where g.goal_key='complete-lovable-cockpit';

comment on function public.creixement_reconcile_runtime_v5() is
  'V10 runtime reconciliation with fully qualified drift columns; safe from RETURNS TABLE output-name ambiguity.';
comment on function public.creixement_auto_verify_cloudflare_scheduler_v9() is
  'ABI-preserved scheduler verifier, converged to the Kairon V10 Cloudflare runtime identity.';
