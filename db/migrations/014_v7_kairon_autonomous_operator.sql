-- Creixement v7 — Kairon autonomous operator.
-- Apply after 013_v6_verified_evidence_gates.sql.
-- Kairon is autonomous through L2. Constitutionally non-delegable L3 actions remain owner-only.

create table if not exists public.kairon_state_v7 (
  singleton boolean primary key default true check (singleton=true),
  operator_name text not null default 'Kairon',
  mode text not null default 'autonomous' check (mode in ('autonomous','degraded','paused','emergency_stop')),
  autonomy_ceiling text not null default 'L2' check (autonomy_ceiling in ('L0','L1','L2')),
  mission text not null,
  cycle_target_minutes integer not null default 5 check (cycle_target_minutes between 1 and 1440),
  last_cycle_at timestamptz,
  last_cycle_status text check (last_cycle_status in ('healthy','degraded','blocked','failed')),
  last_cycle_id uuid,
  current_focus jsonb not null default '[]'::jsonb,
  current_blockers jsonb not null default '[]'::jsonb,
  control_snapshot jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

insert into public.kairon_state_v7(singleton,mission)
values(true,'Continuously improve verified economic output by sensing opportunities, allocating attention, coordinating specialist agents, executing bounded reversible actions, repairing operational drift, learning from outcomes and escalating only constitutionally non-delegable decisions.')
on conflict(singleton) do update set mission=excluded.mission,updated_at=now();

create table if not exists public.kairon_control_cycles_v7 (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null default gen_random_uuid(),
  idempotency_key text not null unique,
  runtime_id text not null,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null default 'running' check (status in ('running','healthy','degraded','blocked','failed')),
  sensed jsonb not null default '{}'::jsonb,
  priorities jsonb not null default '[]'::jsonb,
  automatic_actions jsonb not null default '[]'::jsonb,
  escalations jsonb not null default '[]'::jsonb,
  self_heal jsonb not null default '[]'::jsonb,
  outcome jsonb not null default '{}'::jsonb,
  receipt_ref text,
  error jsonb
);
create index if not exists kairon_cycles_started_idx on public.kairon_control_cycles_v7(started_at desc);

create table if not exists public.kairon_directives_v7 (
  id uuid primary key default gen_random_uuid(),
  directive_key text not null unique,
  objective text not null,
  scope text not null default 'global',
  status text not null default 'active' check (status in ('active','paused','completed','retired')),
  priority numeric not null default 50 check (priority between 0 and 100),
  execution_mode text not null default 'autonomous' check (execution_mode in ('autonomous','hybrid','owner')),
  max_autonomy text not null default 'L2' check (max_autonomy in ('L0','L1','L2','L3')),
  success_criteria jsonb not null default '[]'::jsonb,
  constraints jsonb not null default '[]'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.kairon_directives_v7(directive_key,objective,scope,priority,execution_mode,max_autonomy,success_criteria,constraints,evidence_refs)
values
('verified-economic-output','Increase verified economic output without fabricating traction or exceeding authority.','global',100,'autonomous','L2','["verified outcomes increase","truth hierarchy preserved"]','["no fake revenue","no unreceipted consequential actions"]','["config/creixement-kairon-v7.json"]'),
('continuous-opportunity-sensing','Continuously detect, rank and test monetisable opportunities across Creixement product families.','commercial',90,'autonomous','L2','["actionable opportunities ranked","experiments created when justified"]','["rights and provider readiness required"]','["config/creixement-kairon-v7.json"]'),
('runtime-self-healing','Keep the cloud runtime healthy through bounded reversible remediation.','runtime',95,'autonomous','L2','["stale leases recovered","critical drift surfaced","dead letters triaged"]','["never relax policy automatically"]','["config/creixement-kairon-v7.json"]'),
('continuous-learning','Update fitness, attention and capability confidence from verified outcomes.','evolution',80,'autonomous','L2','["allocation changes are evidence-backed","weak variants senesce rather than vanish"]','["verified outcomes outrank inference"]','["config/creixement-kairon-v7.json"]')
on conflict(directive_key) do update set objective=excluded.objective,scope=excluded.scope,priority=excluded.priority,execution_mode=excluded.execution_mode,max_autonomy=excluded.max_autonomy,success_criteria=excluded.success_criteria,constraints=excluded.constraints,evidence_refs=excluded.evidence_refs,updated_at=now();

create table if not exists public.kairon_action_decisions_v7 (
  id uuid primary key default gen_random_uuid(),
  cycle_id uuid references public.kairon_control_cycles_v7(id) on delete restrict,
  decision_key text not null unique,
  subject_type text not null,
  subject_key text not null,
  action_class text not null,
  requested_autonomy text not null check (requested_autonomy in ('L0','L1','L2','L3')),
  decision text not null check (decision in ('observe','recommend','operate','escalate','abstain')),
  score numeric,
  reason text not null,
  requires_owner boolean not null default false,
  reversible boolean not null default false,
  rights_permitted boolean not null default false,
  receipt_capable boolean not null default false,
  connector_ready boolean not null default false,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists kairon_decisions_cycle_idx on public.kairon_action_decisions_v7(cycle_id,created_at);

create table if not exists public.kairon_learning_events_v7 (
  id uuid primary key default gen_random_uuid(),
  event_key text not null unique,
  niche text,
  subject_ref text,
  truth_level text not null check (truth_level in ('verified_external_outcome','executed_connector_receipt','governed_source_evidence','human_approved_business_decision','evidence_backed_inference','hypothesis','generated_narrative')),
  signal numeric,
  observation jsonb not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.kairon_state_v7 enable row level security;
alter table public.kairon_control_cycles_v7 enable row level security;
alter table public.kairon_directives_v7 enable row level security;
alter table public.kairon_action_decisions_v7 enable row level security;
alter table public.kairon_learning_events_v7 enable row level security;

drop trigger if exists kairon_state_v7_set_updated_at on public.kairon_state_v7;
create trigger kairon_state_v7_set_updated_at before update on public.kairon_state_v7 for each row execute function public.creixement_set_updated_at();
drop trigger if exists kairon_directives_v7_set_updated_at on public.kairon_directives_v7;
create trigger kairon_directives_v7_set_updated_at before update on public.kairon_directives_v7 for each row execute function public.creixement_set_updated_at();

create or replace view public.v_kairon_command_v7 as
select
  now() as observed_at,
  s.operator_name,
  s.mode,
  s.autonomy_ceiling,
  s.mission,
  s.last_cycle_at,
  s.last_cycle_status,
  s.current_focus,
  s.current_blockers,
  s.control_snapshot,
  (select count(*) from public.kairon_directives_v7 where status='active') as active_directives,
  (select count(*) from public.kairon_action_decisions_v7 where requires_owner=true and created_at>=now()-interval '7 days') as recent_owner_escalations,
  (select count(*) from public.v_goal_queue_v4 where runnable=true and execution_mode='autonomous') as runnable_autonomous_goals,
  coalesce((select internal_runtime_ready from public.v_runtime_readiness_v5 limit 1),false) as internal_runtime_ready,
  coalesce((select high_frequency_ready from public.v_scheduler_readiness_v6 limit 1),false) as high_frequency_scheduler_ready,
  coalesce((select critical_drift=0 and critical_incidents=0 and open_job_dead_letters=0 and open_outbox_dead_letters=0 and open_handler_circuits=0 from public.v_operating_health_v6 limit 1),false) as safety_clean
from public.kairon_state_v7 s
where s.singleton=true;

insert into public.job_definitions(
  job_key,name,description,trigger_type,schedule_expr,timezone,event_topic,handler_key,owner_agent_slug,
  autonomy_level,policy_key,required_connectors,input_template,enabled,max_runtime_seconds,lease_seconds,
  max_attempts,backoff_seconds,concurrency_limit
) values(
  'kairon-control-cycle-v7','Kairon autonomous control cycle',
  'Compile Creixement state, priorities, self-healing actions and owner escalations. Executes only bounded internal L2 control actions.',
  'cron','*/5 * * * *','Europe/Madrid',null,'kairon.control_cycle','chief-orchestrator','L2','internal-runtime-v7',
  '[]'::jsonb,'{"source":"kairon"}'::jsonb,true,240,240,3,60,1
)
on conflict(job_key) do update set
  name=excluded.name,description=excluded.description,trigger_type=excluded.trigger_type,schedule_expr=excluded.schedule_expr,
  timezone=excluded.timezone,handler_key=excluded.handler_key,owner_agent_slug=excluded.owner_agent_slug,
  autonomy_level=excluded.autonomy_level,policy_key=excluded.policy_key,required_connectors=excluded.required_connectors,
  input_template=excluded.input_template,enabled=excluded.enabled,max_runtime_seconds=excluded.max_runtime_seconds,
  lease_seconds=excluded.lease_seconds,max_attempts=excluded.max_attempts,backoff_seconds=excluded.backoff_seconds,
  concurrency_limit=excluded.concurrency_limit,updated_at=now();
