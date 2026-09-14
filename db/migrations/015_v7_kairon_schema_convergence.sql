-- Creixement v7 — Kairon schema convergence.
-- Makes the Lovable-created read model and the governed GitHub runtime mutually compatible.
-- Apply after 014_v7_kairon_autonomous_operator.sql; safe on the existing live Supabase schema.

alter table public.kairon_control_cycles_v7 add column if not exists cycle_key text;
alter table public.kairon_control_cycles_v7 add column if not exists idempotency_key text;
alter table public.kairon_control_cycles_v7 add column if not exists priorities jsonb not null default '[]'::jsonb;
alter table public.kairon_control_cycles_v7 add column if not exists automatic_actions jsonb not null default '[]'::jsonb;
alter table public.kairon_control_cycles_v7 add column if not exists self_heal jsonb not null default '[]'::jsonb;
alter table public.kairon_control_cycles_v7 add column if not exists outcome jsonb not null default '{}'::jsonb;
alter table public.kairon_control_cycles_v7 alter column cycle_key set default ('cycle:' || gen_random_uuid()::text);
update public.kairon_control_cycles_v7 set cycle_key='cycle:'||id::text where cycle_key is null;
update public.kairon_control_cycles_v7 set idempotency_key=cycle_key where idempotency_key is null;
create unique index if not exists kairon_cycles_cycle_key_uq on public.kairon_control_cycles_v7(cycle_key);
create unique index if not exists kairon_cycles_idempotency_uq on public.kairon_control_cycles_v7(idempotency_key);

alter table public.kairon_directives_v7 add column if not exists objective text;
alter table public.kairon_directives_v7 add column if not exists scope text not null default 'global';
alter table public.kairon_directives_v7 add column if not exists status text not null default 'active';
alter table public.kairon_directives_v7 add column if not exists priority numeric not null default 50;
alter table public.kairon_directives_v7 add column if not exists execution_mode text not null default 'autonomous';
alter table public.kairon_directives_v7 add column if not exists max_autonomy text not null default 'L2';
alter table public.kairon_directives_v7 add column if not exists success_criteria jsonb not null default '[]'::jsonb;
alter table public.kairon_directives_v7 add column if not exists constraints jsonb not null default '[]'::jsonb;
alter table public.kairon_directives_v7 add column if not exists evidence_refs jsonb not null default '[]'::jsonb;
update public.kairon_directives_v7 set objective=coalesce(objective,statement),max_autonomy=coalesce(max_autonomy,autonomy_ceiling);

alter table public.kairon_action_decisions_v7 add column if not exists subject_type text;
alter table public.kairon_action_decisions_v7 add column if not exists subject_key text;
alter table public.kairon_action_decisions_v7 add column if not exists requested_autonomy text;
alter table public.kairon_action_decisions_v7 add column if not exists score numeric;
alter table public.kairon_action_decisions_v7 add column if not exists reason text;
alter table public.kairon_action_decisions_v7 add column if not exists reversible boolean not null default false;
alter table public.kairon_action_decisions_v7 add column if not exists rights_permitted boolean not null default false;
alter table public.kairon_action_decisions_v7 add column if not exists receipt_capable boolean not null default false;
alter table public.kairon_action_decisions_v7 add column if not exists connector_ready boolean not null default false;
update public.kairon_action_decisions_v7
set requested_autonomy=coalesce(requested_autonomy,autonomy_level),reason=coalesce(reason,rationale),subject_type=coalesce(subject_type,'action'),subject_key=coalesce(subject_key,target_ref,decision_key);

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
alter table public.kairon_state_v7 enable row level security;
insert into public.kairon_state_v7(singleton,mission)
values(true,'Continuously improve verified economic output by sensing opportunities, allocating attention, coordinating specialist agents, executing bounded reversible actions, repairing operational drift, learning from outcomes and escalating only constitutionally non-delegable decisions.')
on conflict(singleton) do update set mission=excluded.mission,updated_at=now();

drop trigger if exists kairon_state_v7_set_updated_at on public.kairon_state_v7;
create trigger kairon_state_v7_set_updated_at before update on public.kairon_state_v7 for each row execute function public.creixement_set_updated_at();

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
alter table public.kairon_learning_events_v7 enable row level security;

create or replace view public.v_kairon_command_v7 with (security_invoker=on) as
with health as (
  select * from public.v_operating_health_v6 limit 1
), scheduler as (
  select * from public.v_scheduler_readiness_v6 limit 1
), gate as (
  select * from public.v_production_gate_v6 limit 1
)
select
  now() as observed_at,
  s.operator_name,
  s.mode,
  s.autonomy_ceiling,
  s.mission as mission_statement,
  s.last_cycle_at,
  s.last_cycle_status,
  s.current_focus,
  s.current_blockers,
  s.control_snapshot,
  (select count(*) from public.kairon_directives_v7 where coalesce(status,'active')='active' and coalesce(active,true)=true) as active_directives,
  (select count(*) from public.v_owner_decision_queue_v6) as owner_decisions_open,
  (select count(*) from public.opportunities where status in ('qualified','actionable','testing','exploring')) as actionable_opportunities,
  case
    when coalesce((select healthy_runtime_instances from health),0)>0
      and coalesce((select critical_drift from health),0)=0
      and coalesce((select critical_incidents from health),0)=0
      and coalesce((select open_job_dead_letters from health),0)=0
      and coalesce((select open_outbox_dead_letters from health),0)=0
      and coalesce((select open_handler_circuits from health),0)=0 then 'healthy'
    when coalesce((select healthy_runtime_instances from health),0)>0 then 'degraded'
    else 'unavailable'
  end as health_state,
  case when coalesce((select high_frequency_ready from scheduler),false) then 'verified_ready' else 'not_verified' end as scheduler_state,
  case
    when coalesce((select promotable from gate),false) then 'promotable'
    when coalesce((select ci_verified_green from gate),false) then 'blocked'
    else 'unverified'
  end as production_gate_state,
  (select count(*) from public.agents) as specialist_agents,
  (select count(*) from public.agents where health='healthy') as healthy_agents
from public.kairon_state_v7 s where s.singleton=true;

insert into public.job_definitions(
  job_key,name,description,trigger_type,schedule_expr,timezone,event_topic,handler_key,owner_agent_slug,
  autonomy_level,policy_key,required_connectors,input_template,enabled,max_runtime_seconds,lease_seconds,
  max_attempts,backoff_seconds,concurrency_limit
) values(
  'kairon-control-cycle-v7','Kairon autonomous control cycle',
  'Compile state, priorities, self-healing actions and owner escalations. Executes only bounded internal L2 control actions.',
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
