-- Creixement Overhaul v3 — runtime governance, scheduler seeds and operator views.
-- Apply after 002_autonomous_economic_brain.sql and 003_cloud_runtime_fabric.sql.

create table if not exists public.authorization_envelopes (
  id uuid primary key default gen_random_uuid(),
  envelope_key text not null unique,
  version text not null,
  action_class text not null,
  max_autonomy text not null check (max_autonomy in ('L0','L1','L2','L3')),
  enabled boolean not null default false,
  allowed_agents jsonb not null default '[]'::jsonb,
  allowed_connectors jsonb not null default '[]'::jsonb,
  prerequisites jsonb not null default '[]'::jsonb,
  limits jsonb not null default '{}'::jsonb,
  source_ref text,
  digest text,
  approved_by text,
  approved_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists authorization_envelopes_action_idx on public.authorization_envelopes(action_class, enabled, expires_at);

create table if not exists public.runtime_controls (
  id uuid primary key default gen_random_uuid(),
  scope_type text not null check (scope_type in ('global','connector','action_class','agent')),
  scope_key text not null,
  state text not null check (state in ('active','paused','blocked')),
  reason text not null,
  set_by text not null,
  source_ref text,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(scope_type, scope_key)
);

create table if not exists public.runtime_metrics (
  id uuid primary key default gen_random_uuid(),
  metric_key text not null,
  dimension_key text,
  metric_value numeric not null,
  unit text,
  observed_at timestamptz not null default now(),
  source_ref text,
  truth_level text not null default 'executed_connector_receipt',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists runtime_metrics_key_idx on public.runtime_metrics(metric_key, observed_at desc);

create table if not exists public.circuit_breakers (
  id uuid primary key default gen_random_uuid(),
  breaker_key text not null unique,
  scope_type text not null check (scope_type in ('connector','handler','action_class')),
  scope_key text not null,
  state text not null default 'closed' check (state in ('closed','open','half_open')),
  consecutive_failures integer not null default 0,
  failure_threshold integer not null default 5,
  cooldown_seconds integer not null default 900,
  opened_at timestamptz,
  retry_at timestamptz,
  last_success_at timestamptz,
  last_failure_at timestamptz,
  last_error jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists circuit_breakers_state_idx on public.circuit_breakers(state, retry_at);

alter table public.authorization_envelopes enable row level security;
alter table public.runtime_controls enable row level security;
alter table public.runtime_metrics enable row level security;
alter table public.circuit_breakers enable row level security;

drop trigger if exists authorization_envelopes_set_updated_at on public.authorization_envelopes;
create trigger authorization_envelopes_set_updated_at before update on public.authorization_envelopes for each row execute function public.creixement_set_updated_at();
drop trigger if exists runtime_controls_set_updated_at on public.runtime_controls;
create trigger runtime_controls_set_updated_at before update on public.runtime_controls for each row execute function public.creixement_set_updated_at();
drop trigger if exists circuit_breakers_set_updated_at on public.circuit_breakers;
create trigger circuit_breakers_set_updated_at before update on public.circuit_breakers for each row execute function public.creixement_set_updated_at();

create or replace function public.creixement_runtime_control_decision(
  p_action_class text,
  p_connector text default null,
  p_agent text default null
) returns table(allowed boolean, reason text)
language plpgsql
stable
security definer
set search_path = public
as $$
declare
  v_row public.runtime_controls%rowtype;
begin
  select * into v_row from public.runtime_controls
   where scope_type='global' and scope_key='creixement'
     and state in ('paused','blocked') and (expires_at is null or expires_at > now())
   limit 1;
  if found then return query select false, 'global runtime control: ' || v_row.state || ' — ' || v_row.reason; return; end if;

  if p_connector is not null then
    select * into v_row from public.runtime_controls
     where scope_type='connector' and scope_key=p_connector
       and state in ('paused','blocked') and (expires_at is null or expires_at > now())
     limit 1;
    if found then return query select false, 'connector runtime control: ' || v_row.state || ' — ' || v_row.reason; return; end if;
  end if;

  select * into v_row from public.runtime_controls
   where scope_type='action_class' and scope_key=p_action_class
     and state in ('paused','blocked') and (expires_at is null or expires_at > now())
   limit 1;
  if found then return query select false, 'action-class runtime control: ' || v_row.state || ' — ' || v_row.reason; return; end if;

  if p_agent is not null then
    select * into v_row from public.runtime_controls
     where scope_type='agent' and scope_key=p_agent
       and state in ('paused','blocked') and (expires_at is null or expires_at > now())
     limit 1;
    if found then return query select false, 'agent runtime control: ' || v_row.state || ' — ' || v_row.reason; return; end if;
  end if;

  return query select true, 'runtime control permits execution';
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
  v_max_attempts integer;
begin
  if p_status not in ('succeeded','failed','blocked','cancelled') then
    raise exception 'invalid job terminal status: %', p_status;
  end if;

  select j.*, d.max_attempts into v_job, v_max_attempts
  from public.job_executions j
  join public.job_definitions d on d.id=j.job_definition_id
  where j.id=p_job_id
  for update;

  if not found then raise exception 'job not found'; end if;
  if v_job.status in ('succeeded','cancelled','dead_lettered') then raise exception 'terminal job is immutable'; end if;
  if v_job.lease_owner is distinct from p_worker then raise exception 'job lease owner mismatch'; end if;

  update public.job_executions
     set status = case when p_status='failed' and v_job.attempt >= v_max_attempts then 'dead_lettered' else p_status end,
         output=p_output,
         last_error=p_error,
         receipt_ref=coalesce(p_receipt_ref,receipt_ref),
         completed_at=case when p_status in ('succeeded','blocked','cancelled') or (p_status='failed' and v_job.attempt >= v_max_attempts) then now() else completed_at end,
         lease_owner=null,
         lease_until=null,
         updated_at=now()
   where id=p_job_id
   returning * into v_job;
  return v_job;
end;
$$;

create or replace function public.creixement_finish_outbox(
  p_event_id uuid,
  p_worker text,
  p_success boolean,
  p_error jsonb default null
) returns public.event_outbox
language plpgsql
security definer
set search_path=public
as $$
declare
  v_event public.event_outbox%rowtype;
begin
  select * into v_event from public.event_outbox where id=p_event_id for update;
  if not found then raise exception 'outbox event not found'; end if;
  if v_event.status in ('processed','dead_lettered','cancelled') then raise exception 'terminal outbox event is immutable'; end if;
  if v_event.lease_owner is distinct from p_worker then raise exception 'outbox lease owner mismatch'; end if;

  if p_success then
    update public.event_outbox
       set status='processed', processed_at=now(), last_error=null, lease_owner=null, lease_until=null, updated_at=now()
     where id=p_event_id returning * into v_event;
  elsif v_event.attempts >= v_event.max_attempts then
    update public.event_outbox
       set status='dead_lettered', last_error=p_error, lease_owner=null, lease_until=null, updated_at=now()
     where id=p_event_id returning * into v_event;
    insert into public.dead_letter_events(outbox_event_id,event_key,topic,payload,final_error,attempts,first_seen_at)
    values(v_event.id,v_event.event_key,v_event.topic,v_event.payload,p_error,v_event.attempts,v_event.created_at)
    on conflict(event_key) do update set final_error=excluded.final_error,attempts=excluded.attempts,dead_lettered_at=now(),resolution_status='open';
  else
    update public.event_outbox
       set status='failed', last_error=p_error,
           available_at=now()+make_interval(secs=>least(900,30*power(2,greatest(v_event.attempts-1,0))::int)),
           lease_owner=null,lease_until=null,updated_at=now()
     where id=p_event_id returning * into v_event;
  end if;
  return v_event;
end;
$$;

create or replace view public.v_connector_health as
select
  c.id,c.slug,c.name,c.state,c.can_read,c.can_write,c.runtime_connection,c.scopes,c.required_secrets,
  c.last_sync_at,c.last_error,c.retry_policy,c.rate_limit,c.data_classification,c.owner,
  case
    when c.state='disabled' then 'disabled'
    when c.state in ('needs_auth','needs_setup') then 'blocked'
    when coalesce(c.runtime_connection,'') in (
      'available_not_wired','chat_connector_available_runtime_not_wired','contracts_and_provider_access_required',
      'provider_setup_required','project_created_build_blocked_by_credits','cloud_service_not_deployed',
      'optional_migration_not_configured'
    ) then 'not_runtime_ready'
    when c.state='degraded' then 'degraded'
    when c.state='connected' and coalesce(c.runtime_connection,'') not in ('','available_not_wired','chat_connector_available_runtime_not_wired') then 'runtime_ready'
    else 'unknown'
  end as effective_health,
  (select max(s.started_at) from public.connector_syncs s where s.connector_slug=c.slug) as last_sync_attempt_at,
  (select s.status from public.connector_syncs s where s.connector_slug=c.slug order by s.started_at desc limit 1) as last_sync_status
from public.connectors c;

create or replace view public.v_pending_approvals as
select a.*,act.action_type,act.connector_slug,act.required_permission,act.payload_digest
from public.approvals a
left join public.actions act on act.id=a.action_id
where a.status='pending'
order by a.created_at;

create or replace view public.v_evolution_dashboard as
select
  g.id,g.niche,g.lineage_id,g.generation,g.variant_name,g.parent_ids,g.genes,g.status,g.fitness,g.confidence,
  g.verified_observations,g.verified_successes,g.paid_successes,g.telomere,g.exploration_budget,
  aa.exploit,aa.adjacency,aa.exploration,aa.rationale as allocation_rationale,
  (select max(e.created_at) from public.evolution_events e where e.niche=g.niche) as last_evolution_at
from public.commercial_genomes g
left join lateral (
  select a.* from public.attention_allocations a where a.niche=g.niche order by a.created_at desc limit 1
) aa on true;

create or replace view public.v_runtime_backlog as
select
  d.job_key,d.name,d.owner_agent_slug,d.autonomy_level,d.enabled,
  count(*) filter (where x.status='queued') as queued,
  count(*) filter (where x.status in ('leased','running')) as active,
  count(*) filter (where x.status='failed') as retrying,
  count(*) filter (where x.status='dead_lettered') as dead_lettered,
  min(coalesce(x.scheduled_for,x.created_at)) filter (where x.status='queued') as oldest_queued_at
from public.job_definitions d
left join public.job_executions x on x.job_definition_id=d.id
group by d.id;

create or replace view public.v_chief_operator_dashboard as
select
  now() as observed_at,
  (select count(*) from public.agents) as agent_count,
  (select count(*) from public.opportunities where status in ('detected','researching','qualified','testing','authorized','executing')) as active_opportunities,
  (select count(*) from public.opportunity_signals where status in ('new','verified')) as open_signals,
  (select count(*) from public.job_executions where status in ('queued','leased','running','failed')) as active_jobs,
  (select count(*) from public.v_pending_approvals) as pending_approvals,
  (select count(*) from public.v_connector_health where effective_health='runtime_ready') as runtime_ready_connectors,
  (select count(*) from public.connectors) as connector_count,
  (select coalesce(sum(amount),0) from public.revenue_events where verified=true) as verified_revenue,
  (select count(*) from public.commercial_genomes where status='champion') as champion_genomes,
  (select count(*) from public.dead_letter_events where resolution_status='open') as open_dead_letters,
  (select count(*) from public.runtime_controls where state in ('paused','blocked') and (expires_at is null or expires_at>now())) as active_runtime_controls;

-- Replace the legacy Tectum runtime descriptor with cloud services.
update public.connectors
set slug='tectum-cloud-underwriting',name='Tectum Cloud Underwriting',state='needs_setup',can_read=true,can_write=true,
    runtime_connection='cloud_service_not_deployed',
    required_secrets='["TECTUM_UNDERWRITING_SERVICE_URL","TECTUM_UNDERWRITING_SERVICE_TOKEN"]'::jsonb,
    scopes='["underwriting.calculate","underwriting.health"]'::jsonb,
    retry_policy='{"max_attempts":3,"backoff_seconds":[5,30,120],"idempotency_required":true}'::jsonb,
    data_classification='restricted',owner='Tectum / Creixement',
    last_error='Cloud underwriting service not deployed; golden-case equivalence required before production use.',updated_at=now()
where slug='tectum-local-bridge';

insert into public.connectors(slug,name,state,can_read,can_write,runtime_connection,scopes,required_secrets,retry_policy,data_classification,owner,last_error)
values
('tectum-cloud-renderer','Tectum Cloud Renderer','needs_setup',true,true,'cloud_service_not_deployed','["report.render","report.preview","report.hash","report.health"]'::jsonb,'["TECTUM_RENDER_SERVICE_URL","TECTUM_RENDER_SERVICE_TOKEN"]'::jsonb,'{"max_attempts":3,"backoff_seconds":[10,60,300],"idempotency_required":true}'::jsonb,'restricted','Tectum / Creixement','Cloud renderer not deployed; golden-report fidelity required before production release.'),
('microsoft-365-cloud-workbook','Microsoft 365 Cloud Workbook (migration compatibility)','disabled',true,true,'optional_migration_not_configured','["files.readwrite","workbook.readwrite"]'::jsonb,'["M365_TENANT_ID","M365_CLIENT_ID","M365_CLIENT_SECRET","M365_WORKBOOK_ID"]'::jsonb,'{"max_attempts":3,"backoff_seconds":[10,60,300],"idempotency_required":true}'::jsonb,'restricted','Tectum / Creixement','Optional compatibility only; never a required production dependency.')
on conflict(slug) do update set name=excluded.name,state=excluded.state,can_read=excluded.can_read,can_write=excluded.can_write,runtime_connection=excluded.runtime_connection,scopes=excluded.scopes,required_secrets=excluded.required_secrets,retry_policy=excluded.retry_policy,data_classification=excluded.data_classification,owner=excluded.owner,last_error=excluded.last_error,updated_at=now();

-- Safe default envelopes: zero external spend and no external effect.
insert into public.authorization_envelopes(envelope_key,version,action_class,max_autonomy,enabled,limits,source_ref)
select 'safe-v3:'||x.action_class,'3.0.0',x.action_class,'L2',true,
       jsonb_build_object('maxActionsPerRun',25,'maxEstimatedExternalCostEur',0,'allowExternalEffect',false,'maxBatchSize',x.max_batch),
       'config/creixement-autonomy-constitution-v3.json'
from (values
  ('public_research',50),('approved_source_research',50),('internal_normalise_dedupe',1000),
  ('internal_crm_reversible_write',50),('report_draft',20),('internal_qa',50),
  ('create_product_hypothesis',10),('create_experiment',10),('bounded_enrichment',25),
  ('genome_evolution',10),('child_agent_spawn',6)
) as x(action_class,max_batch)
on conflict(envelope_key) do update set version=excluded.version,action_class=excluded.action_class,max_autonomy=excluded.max_autonomy,enabled=excluded.enabled,limits=excluded.limits,source_ref=excluded.source_ref,updated_at=now();

-- Scheduler definitions. Connector-dependent jobs remain disabled until runtime wiring is verified.
insert into public.job_definitions(job_key,name,description,trigger_type,schedule_expr,timezone,event_topic,handler_key,owner_agent_slug,autonomy_level,policy_key,required_connectors,enabled,max_runtime_seconds,lease_seconds,max_attempts,backoff_seconds,concurrency_limit)
values
('chief_operator_priority_compile','Chief Operator Priority Compile','Rank current internal priorities without external side effects.','cron','0 7 * * *','Europe/Madrid',null,'chief.compile_priorities','chief-orchestrator','L1',null,'[]'::jsonb,true,300,600,3,30,1),
('runtime_connector_health','Connector Runtime Health','Check declared runtime connectors and write truthful health receipts.','cron','*/30 * * * *','Europe/Madrid',null,'automation.connector_health','automation-engineer','L1',null,'[]'::jsonb,true,180,300,2,30,1),
('opportunity_signal_consumer','Opportunity Signal Consumer','Verify, score and route one bounded opportunity signal.','event',null,'Europe/Madrid','opportunity.signal','opportunity.consume_signal','opportunity-hunter','L2','safe-v3:public_research','[]'::jsonb,true,600,900,5,30,4),
('opportunity_radar_refresh','Opportunity Radar Refresh','Re-rank live opportunity records from current evidence.','cron','15 */4 * * *','Europe/Madrid',null,'opportunity.refresh_radar','opportunity-hunter','L1',null,'[]'::jsonb,true,600,900,3,60,1),
('commercial_genome_evolution','Commercial Genome Evolution','Evaluate bounded mutations only when verified evidence thresholds are met.','cron','30 6 * * 1','Europe/Madrid',null,'evolution.evaluate_niches','evolution','L2','safe-v3:genome_evolution','[]'::jsonb,true,900,1200,2,120,1),
('counterparty_freshness_sweep','Counterparty Freshness Sweep','Mark stale counterparty context without fabricating new facts.','cron','0 5 * * *','Europe/Madrid',null,'counterparty.refresh_staleness','counterparty','L1',null,'[]'::jsonb,true,300,600,2,60,1),
('crm_pipeline_sync','CRM Pipeline Sync','Synchronise governed CRM state after runtime authentication.','cron','*/15 * * * *','Europe/Madrid',null,'commercial.sync_crm','commercial','L2','safe-v3:internal_crm_reversible_write','["google-sheets-crm"]'::jsonb,false,300,600,5,30,1),
('funding_radar_refresh','Funding Radar Refresh','Refresh funding calls from an approved provider.','cron','30 7 * * *','Europe/Madrid',null,'funding.refresh_calls','funding','L1',null,'["funding-feeds"]'::jsonb,false,900,1200,3,120,1),
('market_intelligence_refresh','Market Intelligence Refresh','Execute bounded market research from approved runtime providers.','event',null,'Europe/Madrid','market.research.requested','market.research','market-intelligence','L2','safe-v3:approved_source_research','["market-data"]'::jsonb,false,1200,1500,3,120,3),
('tectum_underwriting','Tectum Cloud Underwriting','Run deterministic cloud underwriting after evidence/right gates and golden equivalence.','event',null,'Europe/Madrid','tectum.case.ready_for_underwriting','tectum.underwrite','tectum','L2',null,'["tectum-cloud-underwriting"]'::jsonb,false,600,900,3,60,3),
('tectum_report_render','Tectum Cloud Report Render','Render the governed report candidate after underwriting readiness.','event',null,'Europe/Madrid','tectum.case.ready_for_report','tectum.render_report','tectum','L2',null,'["tectum-cloud-renderer"]'::jsonb,false,900,1200,3,120,2),
('dead_letter_triage','Dead Letter Triage','Surface unresolved dead letters for repair or explicit replay.','cron','10 * * * *','Europe/Madrid',null,'automation.dead_letter_triage','automation-engineer','L1',null,'[]'::jsonb,true,180,300,1,0,1)
on conflict(job_key) do update set name=excluded.name,description=excluded.description,trigger_type=excluded.trigger_type,schedule_expr=excluded.schedule_expr,timezone=excluded.timezone,event_topic=excluded.event_topic,handler_key=excluded.handler_key,owner_agent_slug=excluded.owner_agent_slug,autonomy_level=excluded.autonomy_level,policy_key=excluded.policy_key,required_connectors=excluded.required_connectors,enabled=excluded.enabled,max_runtime_seconds=excluded.max_runtime_seconds,lease_seconds=excluded.lease_seconds,max_attempts=excluded.max_attempts,backoff_seconds=excluded.backoff_seconds,concurrency_limit=excluded.concurrency_limit,updated_at=now();

insert into public.runtime_controls(scope_type,scope_key,state,reason,set_by,source_ref)
values('global','creixement','active','Default active state; fail closed only when an explicit pause or block is written.','migration:004','config/creixement-autonomy-constitution-v3.json')
on conflict(scope_type,scope_key) do nothing;
