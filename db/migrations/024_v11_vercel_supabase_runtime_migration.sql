-- Creixement V11 — migrate the authoritative Kairon runtime away from Cloudflare.
-- Primary compute: Vercel Functions.
-- Primary scheduler: Supabase pg_cron -> pg_net -> Vercel /api/tick.
-- State authority remains Supabase PostgreSQL; runtime data access remains the authenticated Lovable relay.
-- Apply after 023_v10_runtime_health_convergence.sql.

create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

create table if not exists public.runtime_platform_v11 (
  singleton boolean primary key default true check (singleton),
  runtime_id text not null,
  runtime_version text not null,
  platform text not null check (platform in ('vercel-functions','other-managed-cloud')),
  endpoint_base_url text,
  scheduler_binding_key text not null,
  scheduler_provider text not null,
  cron_secret_name text,
  state text not null default 'configured' check (state in ('configured','proving','active','degraded','retired')),
  previous_runtime_id text,
  cutover_at timestamptz,
  evidence_refs jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.runtime_scheduler_invocations_v11 (
  id uuid primary key default gen_random_uuid(),
  runtime_id text not null,
  scheduler_binding_key text not null,
  request_id bigint,
  endpoint_host text,
  invoked_at timestamptz not null default now(),
  evidence_refs jsonb not null default '[]'::jsonb
);

alter table public.runtime_platform_v11 enable row level security;
alter table public.runtime_scheduler_invocations_v11 enable row level security;
revoke all on public.runtime_platform_v11, public.runtime_scheduler_invocations_v11 from public,anon,authenticated;
grant all on public.runtime_platform_v11, public.runtime_scheduler_invocations_v11 to service_role;

insert into public.runtime_platform_v11(
  singleton,runtime_id,runtime_version,platform,scheduler_binding_key,scheduler_provider,state,
  previous_runtime_id,evidence_refs,metadata
) values(
  true,'kairon-vercel-v11','1.1.0','vercel-functions','supabase-pg-cron-kairon-v11','supabase-pg-cron',
  'configured','kairon-cloudflare-v10',
  '["migration:024_v11_vercel_supabase_runtime_migration.sql","repo:production/creixement-kairon"]'::jsonb,
  '{"cloudflareAuthoritative":false,"stateAuthority":"supabase-postgresql","dataPlane":"authenticated-managed-relay"}'::jsonb
)
on conflict(singleton) do update set
  runtime_id=excluded.runtime_id,
  runtime_version=excluded.runtime_version,
  platform=excluded.platform,
  scheduler_binding_key=excluded.scheduler_binding_key,
  scheduler_provider=excluded.scheduler_provider,
  state=case when public.runtime_platform_v11.state='active' then 'active' else 'configured' end,
  previous_runtime_id=excluded.previous_runtime_id,
  evidence_refs=excluded.evidence_refs,
  metadata=public.runtime_platform_v11.metadata||excluded.metadata,
  updated_at=now();

insert into public.scheduler_bindings_v6(
  binding_key,provider,purpose,cadence_minutes,endpoint_path,secret_ref,state,environment,evidence_refs
) values(
  'supabase-pg-cron-kairon-v11',
  'supabase-pg-cron',
  'Authoritative five-minute Kairon V11 scheduler. Supabase pg_cron invokes Vercel /api/tick through pg_net.',
  5,
  '/api/tick',
  'vault:kairon-v11-cron-secret',
  'needs_setup',
  'production',
  '["db/migrations/024_v11_vercel_supabase_runtime_migration.sql","scheduler:supabase-pg-cron","compute:vercel-functions"]'::jsonb
)
on conflict(binding_key) do update set
  provider=excluded.provider,
  purpose=excluded.purpose,
  cadence_minutes=excluded.cadence_minutes,
  endpoint_path=excluded.endpoint_path,
  secret_ref=excluded.secret_ref,
  state=case when public.scheduler_bindings_v6.state='active' then 'active' else 'needs_setup' end,
  environment='production',
  evidence_refs=excluded.evidence_refs,
  updated_at=now();

create or replace function public.creixement_runtime_cadence_proof_v11(
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
  select *
  from public.creixement_runtime_cadence_proof_v9(
    p_runtime_id,p_commit_sha,p_window_minutes,p_required_samples,p_contract_minutes,p_tolerance_minutes
  );
$$;

revoke all on function public.creixement_runtime_cadence_proof_v11(text,text,integer,integer,numeric,numeric) from public,anon,authenticated;
grant execute on function public.creixement_runtime_cadence_proof_v11(text,text,integer,integer,numeric,numeric) to service_role;

create or replace view public.v_runtime_cadence_proof_v11 as
with platform as (
  select runtime_id,runtime_version,platform,scheduler_binding_key,state,endpoint_base_url
  from public.runtime_platform_v11
  where singleton=true
),
latest as (
  select h.runtime_id,h.commit_sha,h.version,h.last_seen_at,h.status
  from public.runtime_heartbeats_v5 h
  join platform p on p.runtime_id=h.runtime_id
  order by h.last_seen_at desc
  limit 1
)
select
  now() as observed_at,
  p.platform,
  p.scheduler_binding_key,
  p.state as platform_state,
  p.endpoint_base_url,
  l.runtime_id,
  l.version,
  l.commit_sha,
  l.status,
  l.last_seen_at,
  proof.sample_count,
  proof.first_sample_at,
  proof.last_sample_at,
  proof.average_gap_minutes,
  proof.maximum_gap_minutes,
  proof.cadence_stable,
  proof.latest_receipt_ref,
  proof.evidence_refs
from platform p
left join latest l on true
left join lateral public.creixement_runtime_cadence_proof_v11(
  p.runtime_id,l.commit_sha,30,3,5,3
) proof on l.runtime_id is not null;

create or replace view public.v_runtime_proof_summary_v11 as
select
  now() as observed_at,
  p.runtime_id,
  p.runtime_version,
  p.platform,
  p.state as platform_state,
  p.scheduler_binding_key,
  p.scheduler_provider,
  p.endpoint_base_url,
  coalesce((
    select count(*) from public.runtime_heartbeat_samples_v9 s
    where s.runtime_id=p.runtime_id and s.observed_at>=now()-interval '30 minutes'
  ),0) as samples_30m,
  coalesce((
    select count(*) from public.runtime_heartbeat_samples_v9 s
    where s.runtime_id=p.runtime_id
      and s.status='healthy'
      and s.metadata->>'phase'='tick_completed'
      and s.observed_at>=now()-interval '30 minutes'
  ),0) as completed_healthy_ticks_30m,
  coalesce((select cp.cadence_stable from public.v_runtime_cadence_proof_v11 cp limit 1),false) as primary_cadence_stable,
  coalesce((
    select sb.state='active' from public.scheduler_bindings_v6 sb
    where sb.binding_key=p.scheduler_binding_key
  ),false) as primary_scheduler_verified,
  (select sb.last_verified_at from public.scheduler_bindings_v6 sb where sb.binding_key=p.scheduler_binding_key) as scheduler_last_verified_at,
  (select h.commit_sha from public.runtime_heartbeats_v5 h where h.runtime_id=p.runtime_id order by h.last_seen_at desc limit 1) as current_commit_sha,
  (select h.status from public.runtime_heartbeats_v5 h where h.runtime_id=p.runtime_id order by h.last_seen_at desc limit 1) as current_status,
  (select h.last_seen_at from public.runtime_heartbeats_v5 h where h.runtime_id=p.runtime_id order by h.last_seen_at desc limit 1) as current_last_seen_at
from public.runtime_platform_v11 p
where p.singleton=true;

revoke all on public.v_runtime_cadence_proof_v11,public.v_runtime_proof_summary_v11 from public,anon,authenticated;
grant select on public.v_runtime_cadence_proof_v11,public.v_runtime_proof_summary_v11 to service_role;

create or replace function public.creixement_auto_verify_primary_scheduler_v11()
returns jsonb
language plpgsql security definer set search_path=public
as $$
declare
  v_platform public.runtime_platform_v11%rowtype;
  v_latest public.runtime_heartbeats_v5%rowtype;
  v_proof record;
  v_binding public.scheduler_bindings_v6%rowtype;
  v_observed integer;
begin
  select * into v_platform from public.runtime_platform_v11 where singleton=true for update;
  if not found or v_platform.state='retired' then
    return jsonb_build_object('verified',false,'reason','primary runtime platform is not configured');
  end if;

  select h.* into v_latest
  from public.runtime_heartbeats_v5 h
  where h.runtime_id=v_platform.runtime_id
    and h.status='healthy'
    and h.commit_sha is not null
  order by h.last_seen_at desc
  limit 1;

  if not found then
    return jsonb_build_object('verified',false,'reason','no healthy primary runtime heartbeat with commit sha','runtimeId',v_platform.runtime_id);
  end if;

  select * into v_proof
  from public.creixement_runtime_cadence_proof_v11(v_latest.runtime_id,v_latest.commit_sha,30,3,5,3);

  if coalesce(v_proof.cadence_stable,false) is not true then
    update public.runtime_platform_v11 set state='proving',updated_at=now() where singleton=true and state<>'active';
    return jsonb_build_object(
      'verified',false,'reason','insufficient stable cadence evidence',
      'runtimeId',v_latest.runtime_id,'commitSha',v_latest.commit_sha,
      'samples',coalesce(v_proof.sample_count,0),
      'averageGapMinutes',v_proof.average_gap_minutes,
      'maximumGapMinutes',v_proof.maximum_gap_minutes
    );
  end if;

  v_observed := greatest(1,least(5,round(coalesce(v_proof.average_gap_minutes,5))::integer));

  select * into v_binding
  from public.creixement_verify_scheduler_binding_v6(
    v_platform.scheduler_binding_key,
    v_observed,
    'cadence-proof:'||v_latest.commit_sha,
    coalesce(v_proof.latest_receipt_ref,'runtime-heartbeat:'||v_latest.runtime_id)
  );

  if v_binding.state='active' then
    update public.runtime_platform_v11
    set state='active',cutover_at=coalesce(cutover_at,now()),
        evidence_refs=evidence_refs||jsonb_build_array(
          coalesce(v_proof.latest_receipt_ref,'runtime-heartbeat:'||v_latest.runtime_id),
          'scheduler-binding:'||v_binding.binding_key
        ),
        updated_at=now()
    where singleton=true;

    update public.scheduler_bindings_v6
    set state='disabled',
        last_error=jsonb_build_object('code','retired_after_v11_cutover','replacement',v_binding.binding_key,'observedAt',now()),
        updated_at=now()
    where binding_key='cloudflare-primary-heartbeat';

    update public.runtime_db_relay_credentials_v10
    set active=false,
        metadata=metadata||jsonb_build_object('retiredBy','kairon-v11-cutover','retiredAt',now()),
        updated_at=now()
    where runtime_id='kairon-cloudflare-v10' and active=true;
  end if;

  return jsonb_build_object(
    'verified',v_binding.state='active',
    'bindingKey',v_binding.binding_key,
    'state',v_binding.state,
    'runtimeId',v_latest.runtime_id,
    'commitSha',v_latest.commit_sha,
    'samples',v_proof.sample_count,
    'averageGapMinutes',v_proof.average_gap_minutes,
    'maximumGapMinutes',v_proof.maximum_gap_minutes,
    'receipt',v_binding.verification_receipt_ref,
    'cloudflareRetired',v_binding.state='active'
  );
end;
$$;

revoke all on function public.creixement_auto_verify_primary_scheduler_v11() from public,anon,authenticated;
grant execute on function public.creixement_auto_verify_primary_scheduler_v11() to service_role;

create or replace function public.creixement_heartbeat_sample_autoverify_v11()
returns trigger
language plpgsql security definer set search_path=public
as $$
declare
  v_runtime_id text;
begin
  select runtime_id into v_runtime_id from public.runtime_platform_v11 where singleton=true;
  if new.runtime_id=v_runtime_id
     and new.status='healthy'
     and new.metadata->>'phase'='tick_completed' then
    begin
      perform public.creixement_auto_verify_primary_scheduler_v11();
    exception when others then
      update public.scheduler_bindings_v6 sb
      set last_error=jsonb_build_object(
            'code','automatic_scheduler_verification_failed',
            'message',left(sqlerrm,800),
            'observedAt',now()
          ),
          updated_at=now()
      where sb.binding_key=(select scheduler_binding_key from public.runtime_platform_v11 where singleton=true);
    end;
  end if;
  return new;
end;
$$;

revoke all on function public.creixement_heartbeat_sample_autoverify_v11() from public,anon,authenticated;
grant execute on function public.creixement_heartbeat_sample_autoverify_v11() to service_role;

drop trigger if exists runtime_heartbeat_samples_v9_autoverify on public.runtime_heartbeat_samples_v9;
drop trigger if exists runtime_heartbeat_samples_v11_autoverify on public.runtime_heartbeat_samples_v9;
create trigger runtime_heartbeat_samples_v11_autoverify
after insert on public.runtime_heartbeat_samples_v9
for each row execute function public.creixement_heartbeat_sample_autoverify_v11();

create or replace function public.creixement_configure_primary_runtime_v11(
  p_endpoint_base_url text,
  p_cron_secret_name text default 'kairon-v11-cron-secret'
) returns public.runtime_platform_v11
language plpgsql security definer set search_path=public,vault
as $$
declare
  v_row public.runtime_platform_v11%rowtype;
begin
  if p_endpoint_base_url is null
     or p_endpoint_base_url !~ '^https://[A-Za-z0-9.-]+(:[0-9]+)?$' then
    raise exception 'endpoint must be an HTTPS origin without path/query/fragment';
  end if;
  if coalesce(trim(p_cron_secret_name),'')='' then
    raise exception 'cron secret name is required';
  end if;
  if not exists(select 1 from vault.decrypted_secrets where name=p_cron_secret_name and decrypted_secret is not null) then
    raise exception 'cron secret is not present in Supabase Vault';
  end if;

  update public.runtime_platform_v11
  set endpoint_base_url=rtrim(p_endpoint_base_url,'/'),
      cron_secret_name=p_cron_secret_name,
      state=case when state='active' then 'active' else 'proving' end,
      metadata=metadata||jsonb_build_object('configuredAt',now(),'scheduler','supabase-pg-cron','compute','vercel-functions'),
      updated_at=now()
  where singleton=true
  returning * into v_row;

  update public.scheduler_bindings_v6
  set endpoint_path=rtrim(p_endpoint_base_url,'/')||'/api/tick',
      secret_ref='vault:'||p_cron_secret_name,
      state=case when state='active' then 'active' else 'needs_setup' end,
      updated_at=now()
  where binding_key=v_row.scheduler_binding_key;

  return v_row;
end;
$$;

revoke all on function public.creixement_configure_primary_runtime_v11(text,text) from public,anon,authenticated;
grant execute on function public.creixement_configure_primary_runtime_v11(text,text) to service_role;

create or replace function public.creixement_invoke_primary_runtime_v11()
returns bigint
language plpgsql security definer set search_path=public,vault,net
as $$
declare
  v_platform public.runtime_platform_v11%rowtype;
  v_secret text;
  v_request_id bigint;
begin
  select * into v_platform from public.runtime_platform_v11 where singleton=true;
  if not found or v_platform.state not in ('proving','active') or v_platform.endpoint_base_url is null then
    raise exception 'primary runtime is not ready for scheduler invocation';
  end if;

  select decrypted_secret into v_secret
  from vault.decrypted_secrets
  where name=v_platform.cron_secret_name
  limit 1;
  if coalesce(v_secret,'')='' then raise exception 'primary runtime cron secret is unavailable'; end if;

  select net.http_post(
    url := rtrim(v_platform.endpoint_base_url,'/')||'/api/tick',
    headers := jsonb_build_object(
      'Authorization','Bearer '||v_secret,
      'Content-Type','application/json',
      'User-Agent','Creixement-Supabase-Scheduler/11'
    ),
    body := jsonb_build_object('source','supabase-pg-cron','scheduledAt',now()),
    timeout_milliseconds := 120000
  ) into v_request_id;

  insert into public.runtime_scheduler_invocations_v11(
    runtime_id,scheduler_binding_key,request_id,endpoint_host,evidence_refs
  ) values(
    v_platform.runtime_id,v_platform.scheduler_binding_key,v_request_id,
    split_part(replace(v_platform.endpoint_base_url,'https://',''),'/',1),
    jsonb_build_array('pg_net:'||v_request_id::text,'scheduler:'||v_platform.scheduler_binding_key)
  );

  return v_request_id;
end;
$$;

revoke all on function public.creixement_invoke_primary_runtime_v11() from public,anon,authenticated;
grant execute on function public.creixement_invoke_primary_runtime_v11() to service_role;

create or replace function public.creixement_schedule_primary_runtime_v11()
returns bigint
language plpgsql security definer set search_path=public,cron
as $$
declare
  v_jobid bigint;
begin
  if not exists(select 1 from public.runtime_platform_v11 where singleton=true and state in ('proving','active') and endpoint_base_url is not null) then
    raise exception 'primary runtime must be configured before scheduling';
  end if;

  perform cron.unschedule(jobid)
  from cron.job
  where jobname='creixement-kairon-v11-5m';

  select cron.schedule(
    'creixement-kairon-v11-5m',
    '*/5 * * * *',
    'select public.creixement_invoke_primary_runtime_v11();'
  ) into v_jobid;

  update public.scheduler_bindings_v6
  set state='needs_setup',
      evidence_refs=evidence_refs||jsonb_build_array('pg_cron-job:'||v_jobid::text),
      last_error=null,
      updated_at=now()
  where binding_key='supabase-pg-cron-kairon-v11';

  return v_jobid;
end;
$$;

revoke all on function public.creixement_schedule_primary_runtime_v11() from public,anon,authenticated;
grant execute on function public.creixement_schedule_primary_runtime_v11() to service_role;

comment on table public.runtime_platform_v11 is
  'Canonical primary-runtime declaration after migration away from Cloudflare. No raw secrets are stored here.';
comment on function public.creixement_invoke_primary_runtime_v11() is
  'Supabase-scheduled invocation of the Vercel Kairon tick using a Vault-held bearer secret.';
comment on function public.creixement_auto_verify_primary_scheduler_v11() is
  'Fail-closed cutover gate. Retires Cloudflare DB authority only after three healthy V11 cadence samples.';
