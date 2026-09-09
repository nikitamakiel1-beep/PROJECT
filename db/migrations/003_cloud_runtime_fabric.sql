-- Creixement Cloud Runtime Fabric v2
-- Durable job/event fabric, connector sync receipts and bounded child specialists.

create or replace function public.creixement_autonomy_rank(level text)
returns integer language sql immutable as $$
  select case upper(level) when 'L0' then 0 when 'L1' then 1 when 'L2' then 2 when 'L3' then 3 else 99 end;
$$;

create table if not exists public.event_outbox (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null default gen_random_uuid(),
  event_key text not null unique,
  topic text not null,
  event_type text not null,
  source_ref text,
  payload jsonb not null default '{}'::jsonb,
  payload_digest text,
  status text not null default 'pending' check (status in ('pending','leased','processed','failed','dead_lettered','cancelled')),
  priority smallint not null default 50 check (priority between 0 and 100),
  available_at timestamptz not null default now(),
  attempts integer not null default 0,
  max_attempts integer not null default 5 check (max_attempts >= 1),
  lease_owner text,
  lease_until timestamptz,
  last_error jsonb,
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists event_outbox_claim_idx on public.event_outbox(status, available_at, priority desc, created_at);
create index if not exists event_outbox_topic_idx on public.event_outbox(topic, status, created_at desc);

create table if not exists public.dead_letter_events (
  id uuid primary key default gen_random_uuid(),
  outbox_event_id uuid references public.event_outbox(id) on delete restrict,
  event_key text not null,
  topic text not null,
  payload jsonb not null,
  final_error jsonb,
  attempts integer not null,
  first_seen_at timestamptz,
  dead_lettered_at timestamptz not null default now(),
  resolution_status text not null default 'open' check (resolution_status in ('open','replayed','resolved','ignored')),
  resolution_note text,
  unique(event_key)
);

create table if not exists public.job_definitions (
  id uuid primary key default gen_random_uuid(),
  job_key text not null unique,
  name text not null,
  description text,
  trigger_type text not null check (trigger_type in ('cron','event','manual','condition')),
  schedule_expr text,
  timezone text not null default 'Europe/Madrid',
  event_topic text,
  handler_key text not null,
  owner_agent_slug text not null,
  autonomy_level text not null check (autonomy_level in ('L0','L1','L2','L3')),
  policy_key text,
  required_connectors jsonb not null default '[]'::jsonb,
  input_template jsonb not null default '{}'::jsonb,
  enabled boolean not null default false,
  max_runtime_seconds integer not null default 300 check (max_runtime_seconds between 1 and 86400),
  lease_seconds integer not null default 600 check (lease_seconds between 10 and 86400),
  max_attempts integer not null default 3 check (max_attempts between 1 and 20),
  backoff_seconds integer not null default 60 check (backoff_seconds >= 0),
  concurrency_limit integer not null default 1 check (concurrency_limit between 1 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((trigger_type <> 'cron') or schedule_expr is not null),
  check ((trigger_type <> 'event') or event_topic is not null)
);

create table if not exists public.job_executions (
  id uuid primary key default gen_random_uuid(),
  job_definition_id uuid not null references public.job_definitions(id) on delete restrict,
  correlation_id uuid not null default gen_random_uuid(),
  idempotency_key text not null unique,
  trigger_ref text,
  scheduled_for timestamptz,
  status text not null default 'queued' check (status in ('queued','leased','running','succeeded','failed','blocked','cancelled','dead_lettered')),
  attempt integer not null default 0,
  input jsonb not null default '{}'::jsonb,
  output jsonb,
  policy_decision text,
  receipt_ref text,
  lease_owner text,
  lease_until timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  last_error jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists job_executions_claim_idx on public.job_executions(status, scheduled_for, created_at);
create index if not exists job_executions_definition_idx on public.job_executions(job_definition_id, created_at desc);

create table if not exists public.connector_syncs (
  id uuid primary key default gen_random_uuid(),
  connector_slug text not null,
  correlation_id uuid not null default gen_random_uuid(),
  sync_key text not null unique,
  sync_mode text not null check (sync_mode in ('poll','webhook','manual','backfill','health')),
  cursor_before text,
  cursor_after text,
  records_seen integer not null default 0,
  records_created integer not null default 0,
  records_updated integer not null default 0,
  records_rejected integer not null default 0,
  status text not null check (status in ('started','succeeded','partial','failed','blocked')),
  input_digest text,
  output_digest text,
  receipt jsonb,
  error jsonb,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists connector_syncs_slug_idx on public.connector_syncs(connector_slug, started_at desc);

create table if not exists public.child_agent_templates (
  id uuid primary key default gen_random_uuid(),
  template_key text not null unique,
  name text not null,
  purpose_pattern text not null,
  parent_allowlist jsonb not null default '[]'::jsonb,
  max_autonomy text not null check (max_autonomy in ('L0','L1','L2')),
  allowed_capabilities jsonb not null default '[]'::jsonb,
  forbidden_actions jsonb not null default '[]'::jsonb,
  connector_allowlist jsonb not null default '[]'::jsonb,
  max_runtime_seconds integer not null default 900 check (max_runtime_seconds between 30 and 86400),
  max_parallel integer not null default 3 check (max_parallel between 1 and 50),
  max_child_depth integer not null default 0 check (max_child_depth between 0 and 3),
  persistent_promotion_min_verified_successes integer not null default 3,
  enabled boolean not null default true,
  constitution_version text not null default '2.0.0',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agent_spawn_requests (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null default gen_random_uuid(),
  parent_agent_slug text not null,
  template_key text not null references public.child_agent_templates(template_key) on delete restrict,
  objective text not null,
  rationale text not null,
  requested_autonomy text not null check (requested_autonomy in ('L0','L1','L2')),
  requested_capabilities jsonb not null default '[]'::jsonb,
  requested_connectors jsonb not null default '[]'::jsonb,
  max_runtime_seconds integer not null,
  status text not null default 'proposed' check (status in ('proposed','authorized','spawned','completed','failed','blocked','expired','promoted','retired')),
  policy_version text not null,
  policy_decision text,
  child_instance_id uuid,
  evidence_refs jsonb not null default '[]'::jsonb,
  result jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  expires_at timestamptz
);
create index if not exists agent_spawn_requests_parent_idx on public.agent_spawn_requests(parent_agent_slug, status, created_at desc);

create table if not exists public.child_agent_instances (
  id uuid primary key default gen_random_uuid(),
  spawn_request_id uuid not null unique references public.agent_spawn_requests(id) on delete restrict,
  runtime_key text not null unique,
  parent_agent_slug text not null,
  template_key text not null,
  objective text not null,
  autonomy_level text not null check (autonomy_level in ('L0','L1','L2')),
  effective_capabilities jsonb not null default '[]'::jsonb,
  effective_connectors jsonb not null default '[]'::jsonb,
  state text not null default 'starting' check (state in ('starting','running','idle','completed','failed','retired','promoted')),
  verified_successes integer not null default 0,
  total_runs integer not null default 0,
  last_run_at timestamptz,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.agent_spawn_requests
  drop constraint if exists agent_spawn_request_authority_check;
alter table public.agent_spawn_requests
  add constraint agent_spawn_request_authority_check check (public.creixement_autonomy_rank(requested_autonomy) <= 2);

create or replace function public.creixement_claim_outbox(worker text, batch_size integer default 20, lease_for_seconds integer default 120)
returns setof public.event_outbox
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  with picked as (
    select id from public.event_outbox
    where status in ('pending','failed')
      and available_at <= now()
      and (lease_until is null or lease_until < now())
      and attempts < max_attempts
    order by priority desc, available_at, created_at
    for update skip locked
    limit greatest(1, least(batch_size,100))
  )
  update public.event_outbox e
     set status='leased', lease_owner=worker, lease_until=now()+make_interval(secs=>lease_for_seconds), attempts=attempts+1, updated_at=now()
  from picked p where e.id=p.id
  returning e.*;
end;
$$;

create or replace function public.creixement_claim_jobs(worker text, batch_size integer default 10, lease_for_seconds integer default 600)
returns setof public.job_executions
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  with picked as (
    select id from public.job_executions
    where status in ('queued','failed')
      and coalesce(scheduled_for,created_at) <= now()
      and (lease_until is null or lease_until < now())
    order by coalesce(scheduled_for,created_at), created_at
    for update skip locked
    limit greatest(1, least(batch_size,50))
  )
  update public.job_executions j
     set status='leased', lease_owner=worker, lease_until=now()+make_interval(secs=>lease_for_seconds), attempt=attempt+1, updated_at=now()
  from picked p where j.id=p.id
  returning j.*;
end;
$$;

create or replace view public.v_connector_health as
select
  c.id,c.slug,c.name,c.state,c.can_read,c.can_write,c.runtime_connection,c.scopes,c.required_secrets,
  c.last_sync_at,c.last_error,c.retry_policy,c.rate_limit,c.data_classification,c.owner,
  case
    when c.state='disabled' then 'disabled'
    when c.state in ('needs_auth','needs_setup') then 'blocked'
    when coalesce(c.runtime_connection,'') in ('available_not_wired','chat_connector_available_runtime_not_wired','contracts_and_provider_access_required','provider_setup_required','project_created_build_blocked_by_credits') then 'not_runtime_ready'
    when c.state='degraded' then 'degraded'
    when c.state='connected' and coalesce(c.runtime_connection,'') not in ('','available_not_wired','chat_connector_available_runtime_not_wired') then 'runtime_ready'
    else 'unknown'
  end as effective_health,
  (select max(s.started_at) from public.connector_syncs s where s.connector_slug=c.slug) as last_sync_attempt_at,
  (select s.status from public.connector_syncs s where s.connector_slug=c.slug order by s.started_at desc limit 1) as last_sync_status
from public.connectors c;

create or replace view public.v_pending_approvals as
select a.*, act.action_type, act.connector_slug, act.required_permission, act.payload_digest
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

create or replace view public.v_chief_operator_dashboard as
select
  now() as observed_at,
  (select count(*) from public.agents) as agent_count,
  (select count(*) from public.opportunities where status in ('detected','researching','qualified','testing','authorized','executing')) as active_opportunities,
  (select count(*) from public.opportunity_signals where status in ('new','verified')) as open_signals,
  (select count(*) from public.job_executions where status in ('queued','leased','running')) as active_jobs,
  (select count(*) from public.v_pending_approvals) as pending_approvals,
  (select count(*) from public.v_connector_health where effective_health='runtime_ready') as runtime_ready_connectors,
  (select count(*) from public.connectors) as connector_count,
  (select coalesce(sum(amount),0) from public.revenue_events where lower(coalesce(status,'')) in ('paid','settled','recognized','recognised','won')) as verified_revenue,
  (select count(*) from public.commercial_genomes where status='champion') as champion_genomes,
  (select count(*) from public.dead_letter_events where resolution_status='open') as open_dead_letters;

alter table public.event_outbox enable row level security;
alter table public.dead_letter_events enable row level security;
alter table public.job_definitions enable row level security;
alter table public.job_executions enable row level security;
alter table public.connector_syncs enable row level security;
alter table public.child_agent_templates enable row level security;
alter table public.agent_spawn_requests enable row level security;
alter table public.child_agent_instances enable row level security;

-- Update timestamp triggers.
drop trigger if exists event_outbox_set_updated_at on public.event_outbox;
create trigger event_outbox_set_updated_at before update on public.event_outbox for each row execute function public.creixement_set_updated_at();
drop trigger if exists job_definitions_set_updated_at on public.job_definitions;
create trigger job_definitions_set_updated_at before update on public.job_definitions for each row execute function public.creixement_set_updated_at();
drop trigger if exists job_executions_set_updated_at on public.job_executions;
create trigger job_executions_set_updated_at before update on public.job_executions for each row execute function public.creixement_set_updated_at();
drop trigger if exists child_agent_templates_set_updated_at on public.child_agent_templates;
create trigger child_agent_templates_set_updated_at before update on public.child_agent_templates for each row execute function public.creixement_set_updated_at();
drop trigger if exists agent_spawn_requests_set_updated_at on public.agent_spawn_requests;
create trigger agent_spawn_requests_set_updated_at before update on public.agent_spawn_requests for each row execute function public.creixement_set_updated_at();
drop trigger if exists child_agent_instances_set_updated_at on public.child_agent_instances;
create trigger child_agent_instances_set_updated_at before update on public.child_agent_instances for each row execute function public.creixement_set_updated_at();

insert into public.child_agent_templates(template_key,name,purpose_pattern,parent_allowlist,max_autonomy,allowed_capabilities,forbidden_actions,connector_allowlist,max_runtime_seconds,max_parallel,max_child_depth,persistent_promotion_min_verified_successes,enabled,constitution_version)
values
('research-swarm','Research Swarm Specialist','Investigate one bounded question and return evidence/provenance only.','["chief-orchestrator","research","opportunity-hunter","market-intelligence"]'::jsonb,'L2','["public_research","approved_source_research","evidence_collection","source_comparison"]'::jsonb,'["external_send","publication","payment","contract","rights_bypass"]'::jsonb,'["google-drive","market-data","funding-feeds"]'::jsonb,900,6,0,3,true,'2.0.0'),
('account-specialist','Account Intelligence Specialist','Resolve and qualify a bounded set of business accounts.','["chief-orchestrator","commercial","counterparty","opportunity-hunter"]'::jsonb,'L2','["entity_resolution","bounded_enrichment","product_fit","qualification"]'::jsonb,'["external_send","sensitive_profile","ignore_do_not_contact","rights_bypass"]'::jsonb,'["google-sheets-crm","google-contacts","clay"]'::jsonb,900,4,0,3,true,'2.0.0'),
('report-specialist','Report Section Specialist','Draft one bounded report section from approved evidence.','["chief-orchestrator","report-factory","tectum"]'::jsonb,'L1','["draft_generation","evidence_binding","claim_check"]'::jsonb,'["client_release","invent_evidence","approval_bypass"]'::jsonb,'["google-drive"]'::jsonb,600,8,0,3,true,'2.0.0'),
('experiment-specialist','Experiment Specialist','Design or analyse one bounded commercial experiment.','["chief-orchestrator","experiment","product-architect","evolution"]'::jsonb,'L2','["experiment_design","measurement","variant_analysis"]'::jsonb,'["unbounded_spend","external_commitment","fabricate_result"]'::jsonb,'[]'::jsonb,600,4,0,3,true,'2.0.0')
on conflict (template_key) do update set name=excluded.name,purpose_pattern=excluded.purpose_pattern,parent_allowlist=excluded.parent_allowlist,max_autonomy=excluded.max_autonomy,allowed_capabilities=excluded.allowed_capabilities,forbidden_actions=excluded.forbidden_actions,connector_allowlist=excluded.connector_allowlist,max_runtime_seconds=excluded.max_runtime_seconds,max_parallel=excluded.max_parallel,max_child_depth=excluded.max_child_depth,persistent_promotion_min_verified_successes=excluded.persistent_promotion_min_verified_successes,enabled=excluded.enabled,constitution_version=excluded.constitution_version,updated_at=now();
