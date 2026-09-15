-- Creixement V9.2 — immutable runtime heartbeat evidence and automatic scheduler verification.
-- Apply after 020_v9_population_and_courts_runtime.sql.
-- This migration preserves the V5 heartbeat ABI while adding append-only proof of cadence.

create table if not exists public.runtime_heartbeat_samples_v9 (
  id uuid primary key default gen_random_uuid(),
  runtime_id text not null,
  service_key text not null default 'creixement-cloud-runtime',
  version text not null,
  commit_sha text,
  environment text not null default 'production',
  status text not null check (status in ('starting','healthy','degraded','stopping','stopped')),
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now()
);

create index if not exists runtime_heartbeat_samples_v9_runtime_idx
  on public.runtime_heartbeat_samples_v9(runtime_id, observed_at desc);
create index if not exists runtime_heartbeat_samples_v9_commit_idx
  on public.runtime_heartbeat_samples_v9(commit_sha, observed_at desc)
  where commit_sha is not null;
create index if not exists runtime_heartbeat_samples_v9_completed_idx
  on public.runtime_heartbeat_samples_v9(runtime_id, commit_sha, observed_at desc)
  where status='healthy' and metadata->>'phase'='tick_completed';

alter table public.runtime_heartbeat_samples_v9 enable row level security;

-- Preserve the existing V5 upsert as the low-cardinality current-state register,
-- and additionally append every heartbeat as immutable evidence.
create or replace function public.creixement_record_heartbeat_v5(
  p_runtime_id text,
  p_version text,
  p_commit_sha text default null,
  p_status text default 'healthy',
  p_metadata jsonb default '{}'::jsonb
) returns public.runtime_heartbeats_v5
language plpgsql security definer set search_path=public
as $$
declare
  v_row public.runtime_heartbeats_v5%rowtype;
  v_metadata jsonb := coalesce(p_metadata,'{}'::jsonb);
begin
  if p_status not in ('starting','healthy','degraded','stopping','stopped') then
    raise exception 'invalid heartbeat status: %', p_status;
  end if;
  if coalesce(trim(p_runtime_id),'')='' then
    raise exception 'runtime id is required';
  end if;
  if coalesce(trim(p_version),'')='' then
    raise exception 'runtime version is required';
  end if;

  insert into public.runtime_heartbeats_v5(
    runtime_id,version,commit_sha,status,metadata,first_seen_at,last_seen_at
  ) values(
    p_runtime_id,p_version,p_commit_sha,p_status,v_metadata,now(),now()
  )
  on conflict(runtime_id) do update set
    version=excluded.version,
    commit_sha=excluded.commit_sha,
    status=excluded.status,
    metadata=excluded.metadata,
    last_seen_at=now(),
    updated_at=now()
  returning * into v_row;

  insert into public.runtime_heartbeat_samples_v9(
    runtime_id,service_key,version,commit_sha,environment,status,metadata,observed_at
  ) values(
    p_runtime_id,
    coalesce(v_row.service_key,'creixement-cloud-runtime'),
    p_version,
    p_commit_sha,
    coalesce(nullif(v_metadata->>'environment',''),v_row.environment,'production'),
    p_status,
    v_metadata,
    now()
  );

  return v_row;
end;
$$;

revoke all on function public.creixement_record_heartbeat_v5(text,text,text,text,jsonb) from public;
revoke all on function public.creixement_record_heartbeat_v5(text,text,text,text,jsonb) from anon;
revoke all on function public.creixement_record_heartbeat_v5(text,text,text,text,jsonb) from authenticated;
grant execute on function public.creixement_record_heartbeat_v5(text,text,text,text,jsonb) to service_role;

create or replace function public.creixement_runtime_cadence_proof_v9(
  p_runtime_id text,
  p_commit_sha text default null,
  p_window_minutes integer default 30,
  p_required_samples integer default 3,
  p_contract_minutes numeric default 5,
  p_tolerance_minutes numeric default 3
) returns table(
  runtime_id text,
  commit_sha text,
  sample_count integer,
  first_sample_at timestamptz,
  last_sample_at timestamptz,
  average_gap_minutes numeric,
  maximum_gap_minutes numeric,
  cadence_stable boolean,
  latest_receipt_ref text,
  evidence_refs jsonb
)
language sql stable security definer set search_path=public
as $$
  with samples as (
    select
      s.id,
      s.runtime_id,
      s.commit_sha,
      s.observed_at,
      lag(s.observed_at) over(order by s.observed_at) as previous_at
    from public.runtime_heartbeat_samples_v9 s
    where s.runtime_id=p_runtime_id
      and s.status='healthy'
      and s.metadata->>'phase'='tick_completed'
      and s.observed_at>=now()-make_interval(mins=>greatest(5,p_window_minutes))
      and (p_commit_sha is null or s.commit_sha=p_commit_sha)
  ),
  gaps as (
    select extract(epoch from (observed_at-previous_at))/60.0 as gap_minutes
    from samples
    where previous_at is not null
  ),
  agg as (
    select
      count(*)::integer as sample_count,
      min(observed_at) as first_sample_at,
      max(observed_at) as last_sample_at,
      (select avg(gap_minutes) from gaps) as average_gap_minutes,
      (select max(gap_minutes) from gaps) as maximum_gap_minutes,
      (select id::text from samples order by observed_at desc limit 1) as latest_id,
      coalesce((select jsonb_agg('runtime_heartbeat_samples_v9:'||id::text order by observed_at) from samples),'[]'::jsonb) as evidence_refs,
      (select commit_sha from samples order by observed_at desc limit 1) as observed_commit_sha
    from samples
  )
  select
    p_runtime_id,
    coalesce(p_commit_sha,agg.observed_commit_sha),
    agg.sample_count,
    agg.first_sample_at,
    agg.last_sample_at,
    round(coalesce(agg.average_gap_minutes,0)::numeric,3),
    round(coalesce(agg.maximum_gap_minutes,0)::numeric,3),
    (
      agg.sample_count>=greatest(3,p_required_samples)
      and agg.maximum_gap_minutes is not null
      and agg.maximum_gap_minutes<=p_contract_minutes+p_tolerance_minutes
      and agg.last_sample_at>=now()-make_interval(mins=>greatest(2,ceil(p_contract_minutes+p_tolerance_minutes)::integer))
    ),
    case when agg.latest_id is null then null else 'runtime_heartbeat_samples_v9:'||agg.latest_id end,
    agg.evidence_refs
  from agg;
$$;

revoke all on function public.creixement_runtime_cadence_proof_v9(text,text,integer,integer,numeric,numeric) from public;
revoke all on function public.creixement_runtime_cadence_proof_v9(text,text,integer,integer,numeric,numeric) from anon;
revoke all on function public.creixement_runtime_cadence_proof_v9(text,text,integer,integer,numeric,numeric) from authenticated;
grant execute on function public.creixement_runtime_cadence_proof_v9(text,text,integer,integer,numeric,numeric) to service_role;

insert into public.scheduler_bindings_v6(
  binding_key,provider,purpose,cadence_minutes,endpoint_path,secret_ref,state,evidence_refs
) values (
  'cloudflare-primary-heartbeat',
  'cloudflare-workers-cron',
  'Primary five-minute Kairon production heartbeat; becomes active only after immutable cadence evidence.',
  5,
  'scheduled:event',
  'none:same-worker',
  'needs_setup',
  '["cloud/creixement-cloudflare-runtime/wrangler.toml","db/migrations/021_v9_runtime_proof_and_scheduler_autoverify.sql"]'::jsonb
)
on conflict(binding_key) do update set
  provider=excluded.provider,
  purpose=excluded.purpose,
  cadence_minutes=excluded.cadence_minutes,
  endpoint_path=excluded.endpoint_path,
  secret_ref=excluded.secret_ref,
  evidence_refs=case
    when public.scheduler_bindings_v6.state='active' then public.scheduler_bindings_v6.evidence_refs
    else excluded.evidence_refs
  end,
  state=case
    when public.scheduler_bindings_v6.state='active' then 'active'
    else 'needs_setup'
  end,
  updated_at=now();

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
  select * into v_latest
  from public.runtime_heartbeats_v5
  where runtime_id='kairon-cloudflare-v9'
    and status='healthy'
    and commit_sha is not null
  order by last_seen_at desc
  limit 1;

  if not found then
    return jsonb_build_object('verified',false,'reason','no healthy cloudflare heartbeat with commit sha');
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

revoke all on function public.creixement_auto_verify_cloudflare_scheduler_v9() from public;
revoke all on function public.creixement_auto_verify_cloudflare_scheduler_v9() from anon;
revoke all on function public.creixement_auto_verify_cloudflare_scheduler_v9() from authenticated;
grant execute on function public.creixement_auto_verify_cloudflare_scheduler_v9() to service_role;

create or replace function public.creixement_heartbeat_sample_autoverify_v9()
returns trigger
language plpgsql security definer set search_path=public
as $$
begin
  if new.runtime_id='kairon-cloudflare-v9'
     and new.status='healthy'
     and new.metadata->>'phase'='tick_completed' then
    begin
      perform public.creixement_auto_verify_cloudflare_scheduler_v9();
    exception when others then
      update public.scheduler_bindings_v6
      set last_error=jsonb_build_object(
            'code','automatic_scheduler_verification_failed',
            'message',left(sqlerrm,800),
            'observedAt',now()
          ),
          updated_at=now()
      where binding_key='cloudflare-primary-heartbeat';
    end;
  end if;
  return new;
end;
$$;

drop trigger if exists runtime_heartbeat_samples_v9_autoverify on public.runtime_heartbeat_samples_v9;
create trigger runtime_heartbeat_samples_v9_autoverify
after insert on public.runtime_heartbeat_samples_v9
for each row execute function public.creixement_heartbeat_sample_autoverify_v9();

create or replace view public.v_runtime_cadence_proof_v9 as
with latest as (
  select runtime_id,commit_sha,version,last_seen_at,status
  from public.runtime_heartbeats_v5
  where runtime_id='kairon-cloudflare-v9'
  order by last_seen_at desc
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
  coalesce((select count(*) from public.runtime_heartbeat_samples_v9 where observed_at>=now()-interval '30 minutes'),0) as samples_30m,
  coalesce((select count(*) from public.runtime_heartbeat_samples_v9 where status='healthy' and metadata->>'phase'='tick_completed' and observed_at>=now()-interval '30 minutes'),0) as completed_healthy_ticks_30m,
  coalesce((select cadence_stable from public.v_runtime_cadence_proof_v9 limit 1),false) as cloudflare_cadence_stable,
  coalesce((select state='active' from public.scheduler_bindings_v6 where binding_key='cloudflare-primary-heartbeat'),false) as cloudflare_scheduler_verified,
  coalesce((select last_verified_at from public.scheduler_bindings_v6 where binding_key='cloudflare-primary-heartbeat'),null) as scheduler_last_verified_at;

comment on table public.runtime_heartbeat_samples_v9 is
  'Append-only runtime evidence. Current-state heartbeat remains runtime_heartbeats_v5; cadence proof is derived only from healthy tick_completed samples.';
