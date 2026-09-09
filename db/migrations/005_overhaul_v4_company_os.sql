-- Creixement Overhaul v4 — autonomous company OS persistence.
-- Apply after 002, 003 and 004.

create table if not exists public.missions (
  id uuid primary key default gen_random_uuid(),
  mission_key text not null unique,
  title text not null,
  objective text not null,
  success_definition text not null,
  status text not null default 'active' check (status in ('draft','active','paused','completed','retired')),
  owner_agent_slug text not null,
  constitution_version text not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  review_every_hours integer not null default 24 check (review_every_hours between 1 and 8760),
  last_reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.goals (
  id uuid primary key default gen_random_uuid(),
  mission_id uuid not null references public.missions(id) on delete restrict,
  parent_goal_id uuid references public.goals(id) on delete restrict,
  goal_key text not null unique,
  goal_class text not null check (goal_class in ('revenue','product','opportunity','client_delivery','tectum','reliability','strategic','compliance')),
  title text not null,
  objective text not null,
  success_condition text not null,
  owner_agent_slug text not null,
  status text not null default 'proposed' check (status in ('proposed','ready','active','blocked','succeeded','failed','cancelled','expired')),
  expected_economic_value numeric not null default 0,
  strategic_value numeric not null default 0 check (strategic_value between 0 and 1),
  urgency numeric not null default 0 check (urgency between 0 and 1),
  confidence numeric not null default 0 check (confidence between 0 and 1),
  reversibility numeric not null default 1 check (reversibility between 0 and 1),
  risk numeric not null default 0 check (risk between 0 and 1),
  blocker text,
  required_connectors jsonb not null default '[]'::jsonb,
  required_capabilities jsonb not null default '[]'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  budget_ref text,
  review_at timestamptz,
  expires_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists goals_queue_idx on public.goals(status, urgency desc, expected_economic_value desc, created_at);
create index if not exists goals_mission_idx on public.goals(mission_id, status, created_at);

create table if not exists public.goal_dependencies (
  goal_id uuid not null references public.goals(id) on delete cascade,
  depends_on_goal_id uuid not null references public.goals(id) on delete restrict,
  dependency_type text not null default 'hard' check (dependency_type in ('hard','soft')),
  created_at timestamptz not null default now(),
  primary key(goal_id, depends_on_goal_id),
  check (goal_id <> depends_on_goal_id)
);

create table if not exists public.goal_events (
  id uuid primary key default gen_random_uuid(),
  goal_id uuid not null references public.goals(id) on delete restrict,
  correlation_id uuid not null default gen_random_uuid(),
  event_type text not null,
  old_status text,
  new_status text,
  rationale jsonb not null default '{}'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  actor text not null,
  created_at timestamptz not null default now()
);
create index if not exists goal_events_goal_idx on public.goal_events(goal_id, created_at desc);

create table if not exists public.budget_envelopes (
  id uuid primary key default gen_random_uuid(),
  budget_key text not null unique,
  scope_type text not null check (scope_type in ('global','mission','goal','agent','niche','product')),
  scope_key text not null,
  period text not null check (period in ('run','day','week','month')),
  attention_units numeric not null default 0,
  agent_runs integer not null default 0,
  experiment_slots integer not null default 0,
  enrichment_records integer not null default 0,
  external_api_cost_eur numeric not null default 0,
  external_messages integer not null default 0,
  publications integer not null default 0,
  enabled boolean not null default true,
  payment_authority boolean not null default false,
  source_ref text,
  approved_by text,
  approved_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(scope_type, scope_key, period)
);

create table if not exists public.budget_usage_events (
  id uuid primary key default gen_random_uuid(),
  budget_id uuid not null references public.budget_envelopes(id) on delete restrict,
  correlation_id uuid not null,
  idempotency_key text not null unique,
  action_class text not null,
  actor_agent text not null,
  attention_units numeric not null default 0,
  agent_runs integer not null default 0,
  experiment_slots integer not null default 0,
  enrichment_records integer not null default 0,
  external_api_cost_eur numeric not null default 0,
  external_messages integer not null default 0,
  publications integer not null default 0,
  occurred_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists budget_usage_budget_idx on public.budget_usage_events(budget_id, occurred_at desc);

create table if not exists public.knowledge_items (
  id uuid primary key default gen_random_uuid(),
  namespace text not null,
  subject text not null,
  predicate text not null,
  object_value jsonb not null,
  truth_level text not null check (truth_level in ('verified_external_outcome','executed_connector_receipt','governed_source_evidence','human_approved_decision','evidence_backed_model_inference','hypothesis','generated_narrative')),
  source_refs jsonb not null default '[]'::jsonb,
  observed_at timestamptz not null,
  valid_from timestamptz,
  valid_until timestamptz,
  authority numeric not null default 0 check (authority between 0 and 1),
  freshness numeric not null default 0 check (freshness between 0 and 1),
  confidence numeric not null default 0 check (confidence between 0 and 1),
  sensitivity text not null default 'internal' check (sensitivity in ('public','internal','restricted')),
  rights_status text not null default 'unknown' check (rights_status in ('permitted','restricted','unknown','blocked')),
  digest text,
  supersedes jsonb not null default '[]'::jsonb,
  contradiction_group text,
  usage_count integer not null default 0,
  last_used_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists knowledge_lookup_idx on public.knowledge_items(namespace, subject, predicate, observed_at desc);
create index if not exists knowledge_validity_idx on public.knowledge_items(valid_until, truth_level, rights_status);

create table if not exists public.knowledge_conflicts (
  id uuid primary key default gen_random_uuid(),
  conflict_key text not null unique,
  namespace text not null,
  subject text not null,
  predicate text not null,
  item_ids jsonb not null,
  status text not null default 'open' check (status in ('open','resolved','accepted_ambiguity','expired')),
  resolution_item_id uuid references public.knowledge_items(id) on delete set null,
  rationale text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists public.provider_registry (
  id uuid primary key default gen_random_uuid(),
  provider_key text not null unique,
  name text not null,
  provider_type text not null check (provider_type in ('internal_service','connector','external_api','data_feed','renderer','underwriting','enrichment','storage','analytics')),
  runtime_state text not null default 'not_configured' check (runtime_state in ('not_configured','configured','runtime_ready','degraded','blocked','disabled')),
  rights_status text not null default 'unknown' check (rights_status in ('permitted','restricted','unknown','blocked')),
  operations jsonb not null default '[]'::jsonb,
  data_classification text not null default 'internal',
  estimated_cost_eur numeric not null default 0,
  reliability numeric not null default 0 check (reliability between 0 and 1),
  evidence_quality numeric not null default 0 check (evidence_quality between 0 and 1),
  freshness numeric not null default 0 check (freshness between 0 and 1),
  latency_ms integer,
  rate_limit jsonb not null default '{}'::jsonb,
  receipt_support boolean not null default false,
  idempotent_writes boolean not null default false,
  required_secrets jsonb not null default '[]'::jsonb,
  circuit_breaker_key text,
  owner text,
  last_verified_at timestamptz,
  last_error jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists provider_operation_idx on public.provider_registry(runtime_state, rights_status);

create table if not exists public.capability_registry (
  id uuid primary key default gen_random_uuid(),
  capability_key text not null unique,
  name text not null,
  capability_type text not null check (capability_type in ('research','commercial','report','underwriting','render','enrichment','crm','funding','market','analytics','automation','other')),
  maturity text not null default 'experimental' check (maturity in ('experimental','validated','production','deprecated','blocked')),
  execution_contract jsonb not null default '{}'::jsonb,
  evidence_requirements jsonb not null default '[]'::jsonb,
  required_truth_level text,
  verified_successes integer not null default 0,
  paid_successes integer not null default 0,
  reproducibility_score numeric,
  unit_economics_score numeric,
  source_ref text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.capability_provider_routes (
  capability_key text not null references public.capability_registry(capability_key) on delete cascade,
  provider_key text not null references public.provider_registry(provider_key) on delete restrict,
  operation text not null,
  priority integer not null default 100,
  enabled boolean not null default true,
  max_cost_eur numeric,
  min_reliability numeric,
  min_evidence_quality numeric,
  min_freshness numeric,
  created_at timestamptz not null default now(),
  primary key(capability_key, provider_key, operation)
);

create table if not exists public.experiment_definitions_v4 (
  id uuid primary key default gen_random_uuid(),
  experiment_key text not null unique,
  goal_id uuid references public.goals(id) on delete set null,
  niche text,
  hypothesis text not null,
  target_metric text not null,
  minimum_effect numeric not null default 0,
  max_observations integer not null default 100,
  min_observations_per_arm integer not null default 20,
  require_paid_evidence boolean not null default false,
  harm_stop_threshold numeric not null default 0.10,
  status text not null default 'draft' check (status in ('draft','ready','running','winner','inconclusive','stopped_harm','budget_exhausted','cancelled','expired')),
  stop_rules jsonb not null default '{}'::jsonb,
  rights_constraints jsonb not null default '{}'::jsonb,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.experiment_arm_stats_v4 (
  experiment_id uuid not null references public.experiment_definitions_v4(id) on delete cascade,
  arm_key text not null,
  successes integer not null default 0,
  trials integer not null default 0,
  paid_successes integer not null default 0,
  harmful_events integer not null default 0,
  revenue numeric not null default 0,
  direct_cost numeric not null default 0,
  evidence_refs jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  primary key(experiment_id, arm_key),
  check(successes <= trials),
  check(paid_successes <= successes),
  check(harmful_events <= trials)
);

create table if not exists public.service_identities (
  id uuid primary key default gen_random_uuid(),
  service_key text not null unique,
  name text not null,
  service_type text not null check (service_type in ('worker','api','scheduler','renderer','underwriting','cockpit','database','connector')),
  environment text not null default 'production',
  scopes jsonb not null default '[]'::jsonb,
  max_autonomy text not null default 'L1' check (max_autonomy in ('L0','L1','L2','L3')),
  state text not null default 'defined' check (state in ('defined','configured','active','degraded','disabled','retired')),
  owner text,
  last_attested_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.secret_requirements (
  id uuid primary key default gen_random_uuid(),
  secret_name text not null,
  service_key text not null references public.service_identities(service_key) on delete cascade,
  provider text not null,
  environment text not null default 'production',
  required boolean not null default true,
  configured boolean not null default false,
  rotation_days integer not null default 90,
  last_rotated_at timestamptz,
  next_rotation_due timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(secret_name, service_key, environment)
);

create table if not exists public.slo_definitions (
  id uuid primary key default gen_random_uuid(),
  slo_key text not null unique,
  scope_type text not null check (scope_type in ('global','service','connector','handler','product')),
  scope_key text not null,
  metric_key text not null,
  comparator text not null check (comparator in ('gte','lte')),
  target numeric not null,
  window_minutes integer not null default 60,
  severity text not null default 'warning' check (severity in ('info','warning','critical')),
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.incidents (
  id uuid primary key default gen_random_uuid(),
  incident_key text not null unique,
  severity text not null check (severity in ('info','warning','critical')),
  status text not null default 'open' check (status in ('open','acknowledged','mitigating','resolved','closed')),
  scope_type text not null,
  scope_key text not null,
  title text not null,
  summary text,
  detected_by text not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  opened_at timestamptz not null default now(),
  acknowledged_at timestamptz,
  resolved_at timestamptz,
  root_cause text,
  corrective_actions jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists incidents_open_idx on public.incidents(status, severity, opened_at desc);

create table if not exists public.trace_spans (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null,
  span_id text not null,
  parent_span_id text,
  service_key text,
  actor_agent text,
  operation text not null,
  status text not null check (status in ('started','succeeded','failed','blocked','cancelled')),
  started_at timestamptz not null,
  completed_at timestamptz,
  duration_ms integer,
  input_digest text,
  output_digest text,
  receipt_ref text,
  metadata jsonb not null default '{}'::jsonb,
  unique(correlation_id, span_id)
);
create index if not exists trace_correlation_idx on public.trace_spans(correlation_id, started_at);

create table if not exists public.release_assessments (
  id uuid primary key default gen_random_uuid(),
  release_key text not null unique,
  branch text,
  commit_sha text,
  target_environment text not null default 'production',
  promotable boolean not null default false,
  readiness numeric not null default 0 check (readiness between 0 and 1),
  assessment_version text not null default '4.0.0',
  assessed_at timestamptz not null default now(),
  assessed_by text not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.release_gate_results (
  release_id uuid not null references public.release_assessments(id) on delete cascade,
  gate_key text not null,
  state text not null check (state in ('pass','fail','blocked','not_applicable','unknown')),
  required boolean not null default true,
  reason text not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  primary key(release_id, gate_key)
);

-- RLS: browser/anon receives no direct table policy by default.
alter table public.missions enable row level security;
alter table public.goals enable row level security;
alter table public.goal_dependencies enable row level security;
alter table public.goal_events enable row level security;
alter table public.budget_envelopes enable row level security;
alter table public.budget_usage_events enable row level security;
alter table public.knowledge_items enable row level security;
alter table public.knowledge_conflicts enable row level security;
alter table public.provider_registry enable row level security;
alter table public.capability_registry enable row level security;
alter table public.capability_provider_routes enable row level security;
alter table public.experiment_definitions_v4 enable row level security;
alter table public.experiment_arm_stats_v4 enable row level security;
alter table public.service_identities enable row level security;
alter table public.secret_requirements enable row level security;
alter table public.slo_definitions enable row level security;
alter table public.incidents enable row level security;
alter table public.trace_spans enable row level security;
alter table public.release_assessments enable row level security;
alter table public.release_gate_results enable row level security;

-- updated_at triggers.
drop trigger if exists missions_set_updated_at on public.missions;
create trigger missions_set_updated_at before update on public.missions for each row execute function public.creixement_set_updated_at();
drop trigger if exists goals_set_updated_at on public.goals;
create trigger goals_set_updated_at before update on public.goals for each row execute function public.creixement_set_updated_at();
drop trigger if exists budget_envelopes_set_updated_at on public.budget_envelopes;
create trigger budget_envelopes_set_updated_at before update on public.budget_envelopes for each row execute function public.creixement_set_updated_at();
drop trigger if exists knowledge_items_set_updated_at on public.knowledge_items;
create trigger knowledge_items_set_updated_at before update on public.knowledge_items for each row execute function public.creixement_set_updated_at();
drop trigger if exists provider_registry_set_updated_at on public.provider_registry;
create trigger provider_registry_set_updated_at before update on public.provider_registry for each row execute function public.creixement_set_updated_at();
drop trigger if exists capability_registry_set_updated_at on public.capability_registry;
create trigger capability_registry_set_updated_at before update on public.capability_registry for each row execute function public.creixement_set_updated_at();
drop trigger if exists experiment_definitions_v4_set_updated_at on public.experiment_definitions_v4;
create trigger experiment_definitions_v4_set_updated_at before update on public.experiment_definitions_v4 for each row execute function public.creixement_set_updated_at();
drop trigger if exists service_identities_set_updated_at on public.service_identities;
create trigger service_identities_set_updated_at before update on public.service_identities for each row execute function public.creixement_set_updated_at();
drop trigger if exists secret_requirements_set_updated_at on public.secret_requirements;
create trigger secret_requirements_set_updated_at before update on public.secret_requirements for each row execute function public.creixement_set_updated_at();
drop trigger if exists slo_definitions_set_updated_at on public.slo_definitions;
create trigger slo_definitions_set_updated_at before update on public.slo_definitions for each row execute function public.creixement_set_updated_at();
drop trigger if exists incidents_set_updated_at on public.incidents;
create trigger incidents_set_updated_at before update on public.incidents for each row execute function public.creixement_set_updated_at();

create or replace function public.creixement_assert_goal_acyclic(p_goal_id uuid, p_dependency_id uuid)
returns boolean language sql stable as $$
  with recursive descendants(id) as (
    select p_dependency_id
    union
    select gd.depends_on_goal_id from public.goal_dependencies gd join descendants d on gd.goal_id=d.id
  )
  select not exists(select 1 from descendants where id=p_goal_id);
$$;

create or replace function public.creixement_consume_budget(
  p_budget_key text,
  p_correlation_id uuid,
  p_idempotency_key text,
  p_action_class text,
  p_actor_agent text,
  p_attention_units numeric default 0,
  p_agent_runs integer default 0,
  p_experiment_slots integer default 0,
  p_enrichment_records integer default 0,
  p_external_api_cost_eur numeric default 0,
  p_external_messages integer default 0,
  p_publications integer default 0
) returns public.budget_usage_events
language plpgsql security definer set search_path=public as $$
declare
  b public.budget_envelopes%rowtype;
  u public.budget_usage_events%rowtype;
  period_start timestamptz;
  used_attention numeric; used_runs bigint; used_experiments bigint; used_enrichment bigint;
  used_cost numeric; used_messages bigint; used_publications bigint;
begin
  select * into b from public.budget_envelopes where budget_key=p_budget_key and enabled=true for update;
  if not found then raise exception 'budget envelope unavailable: %', p_budget_key; end if;
  if b.expires_at is not null and b.expires_at <= now() then raise exception 'budget envelope expired'; end if;
  if p_external_api_cost_eur > 0 and b.payment_authority=false then
    -- This authorizes API cost only; it still cannot authorize arbitrary money movement.
    null;
  end if;
  period_start := case b.period when 'run' then now() - interval '1 minute' when 'day' then date_trunc('day',now()) when 'week' then date_trunc('week',now()) when 'month' then date_trunc('month',now()) end;
  select coalesce(sum(attention_units),0),coalesce(sum(agent_runs),0),coalesce(sum(experiment_slots),0),coalesce(sum(enrichment_records),0),coalesce(sum(external_api_cost_eur),0),coalesce(sum(external_messages),0),coalesce(sum(publications),0)
    into used_attention,used_runs,used_experiments,used_enrichment,used_cost,used_messages,used_publications
  from public.budget_usage_events where budget_id=b.id and occurred_at>=period_start;
  if used_attention+p_attention_units>b.attention_units or used_runs+p_agent_runs>b.agent_runs or used_experiments+p_experiment_slots>b.experiment_slots or used_enrichment+p_enrichment_records>b.enrichment_records or used_cost+p_external_api_cost_eur>b.external_api_cost_eur or used_messages+p_external_messages>b.external_messages or used_publications+p_publications>b.publications then
    raise exception 'budget exceeded: %', p_budget_key;
  end if;
  insert into public.budget_usage_events(budget_id,correlation_id,idempotency_key,action_class,actor_agent,attention_units,agent_runs,experiment_slots,enrichment_records,external_api_cost_eur,external_messages,publications)
  values(b.id,p_correlation_id,p_idempotency_key,p_action_class,p_actor_agent,p_attention_units,p_agent_runs,p_experiment_slots,p_enrichment_records,p_external_api_cost_eur,p_external_messages,p_publications)
  returning * into u;
  return u;
exception when unique_violation then
  select * into u from public.budget_usage_events where idempotency_key=p_idempotency_key;
  return u;
end;
$$;

create or replace view public.v_goal_queue_v4 as
select g.*,
  coalesce((select count(*) from public.goal_dependencies gd join public.goals d on d.id=gd.depends_on_goal_id where gd.goal_id=g.id and gd.dependency_type='hard' and d.status<>'succeeded'),0) as blocking_dependencies,
  case when g.expires_at is not null and g.expires_at<=now() then false
       when g.status not in ('proposed','ready','blocked') then false
       when exists(select 1 from public.goal_dependencies gd join public.goals d on d.id=gd.depends_on_goal_id where gd.goal_id=g.id and gd.dependency_type='hard' and d.status<>'succeeded') then false
       else true end as runnable,
  (tanh(greatest(g.expected_economic_value,0)/1000.0) + g.strategic_value*0.6 + g.urgency*0.5 + g.confidence*0.7 + g.reversibility*0.3 - g.risk*0.8
   - coalesce((select count(*) from public.goal_dependencies gd join public.goals d on d.id=gd.depends_on_goal_id where gd.goal_id=g.id and gd.dependency_type='hard' and d.status<>'succeeded'),0)*2.0) as priority_score
from public.goals g;

create or replace view public.v_provider_health_v4 as
select p.*,
  case when p.runtime_state='runtime_ready' and p.rights_status='permitted' and p.receipt_support=true and coalesce(cb.state,'closed')<>'open' then true else false end as usable,
  coalesce(cb.state,'closed') as circuit_state
from public.provider_registry p
left join public.circuit_breakers cb on cb.breaker_key=p.circuit_breaker_key;

create or replace view public.v_incident_dashboard_v4 as
select i.*,
  extract(epoch from (coalesce(i.resolved_at,now())-i.opened_at))/60.0 as age_minutes
from public.incidents i
where i.status<>'closed'
order by case i.severity when 'critical' then 1 when 'warning' then 2 else 3 end, i.opened_at;

create or replace view public.v_release_readiness_v4 as
select r.*,
  coalesce(count(g.*) filter(where g.required),0) as required_gates,
  coalesce(count(g.*) filter(where g.required and g.state='pass' and jsonb_array_length(g.evidence_refs)>0),0) as passed_required_gates,
  coalesce(count(g.*) filter(where g.required and g.state in ('fail','blocked')),0) as failed_required_gates,
  coalesce(count(g.*) filter(where g.required and g.state='unknown'),0) as unknown_required_gates
from public.release_assessments r left join public.release_gate_results g on g.release_id=r.id
group by r.id;

-- Seed persistent mission and zero-risk global budget.
insert into public.missions(mission_key,title,objective,success_definition,status,owner_agent_slug,constitution_version,evidence_refs)
values('creixement-primary','Creixement Autonomous Growth','Continuously discover, validate, build, sell, deliver and improve the highest-value lawful Creixement opportunities.','Verified paid outcomes, repeatable delivery, positive contribution margin and increasing reusable capability without violating governance.','active','chief-orchestrator','4.0.0','["config/creixement-runtime-v4.json"]'::jsonb)
on conflict(mission_key) do update set objective=excluded.objective,success_definition=excluded.success_definition,status=excluded.status,owner_agent_slug=excluded.owner_agent_slug,constitution_version=excluded.constitution_version,evidence_refs=excluded.evidence_refs,updated_at=now();

insert into public.budget_envelopes(budget_key,scope_type,scope_key,period,attention_units,agent_runs,experiment_slots,enrichment_records,external_api_cost_eur,external_messages,publications,enabled,payment_authority,source_ref)
values('global-v4-day','global','creixement','day',100,250,20,100,0,0,0,true,false,'config/creixement-runtime-v4.json')
on conflict(budget_key) do update set attention_units=excluded.attention_units,agent_runs=excluded.agent_runs,experiment_slots=excluded.experiment_slots,enrichment_records=excluded.enrichment_records,external_api_cost_eur=excluded.external_api_cost_eur,external_messages=excluded.external_messages,publications=excluded.publications,enabled=excluded.enabled,payment_authority=excluded.payment_authority,source_ref=excluded.source_ref,updated_at=now();

insert into public.slo_definitions(slo_key,scope_type,scope_key,metric_key,comparator,target,window_minutes,severity,enabled)
values
('global-job-success','global','creixement','job_success_rate','gte',0.98,60,'critical',true),
('global-receipt-verification','global','creixement','receipt_verification_rate','gte',1.0,60,'critical',true),
('global-connector-sync','global','creixement','connector_sync_success_rate','gte',0.98,60,'warning',true),
('global-p95-latency','global','creixement','p95_job_latency_seconds','lte',900,60,'warning',true),
('global-queue-age','global','creixement','oldest_queue_age_seconds','lte',1800,30,'critical',true),
('global-dead-letter-rate','global','creixement','dead_letter_rate','lte',0.01,60,'critical',true)
on conflict(slo_key) do update set target=excluded.target,window_minutes=excluded.window_minutes,severity=excluded.severity,enabled=excluded.enabled,updated_at=now();

insert into public.service_identities(service_key,name,service_type,environment,scopes,max_autonomy,state,owner)
values
('control-plane-api','Creixement Control Plane API','api','production','["control.read","control.write_internal"]'::jsonb,'L2','defined','Creixement'),
('scheduler','Creixement Scheduler','scheduler','production','["jobs.enqueue","events.enqueue"]'::jsonb,'L2','defined','Creixement'),
('opportunity-worker','Opportunity Worker','worker','production','["signals.read","opportunities.write","research.route"]'::jsonb,'L2','defined','Creixement'),
('evolution-worker','Evolution Worker','worker','production','["genomes.readwrite","experiments.read"]'::jsonb,'L2','defined','Creixement'),
('connector-worker','Connector Worker','worker','production','["connectors.execute","receipts.write"]'::jsonb,'L2','defined','Creixement'),
('tectum-underwriting','Tectum Cloud Underwriting','underwriting','production','["underwriting.calculate","receipts.write"]'::jsonb,'L2','defined','Tectum'),
('tectum-renderer','Tectum Cloud Renderer','renderer','production','["reports.render","reports.hash","previews.render"]'::jsonb,'L2','defined','Tectum'),
('lovable-cockpit','Creixement Lovable Cockpit','cockpit','production','["control.read","goals.submit_internal"]'::jsonb,'L1','defined','Creixement')
on conflict(service_key) do update set name=excluded.name,service_type=excluded.service_type,scopes=excluded.scopes,max_autonomy=excluded.max_autonomy,owner=excluded.owner,updated_at=now();
