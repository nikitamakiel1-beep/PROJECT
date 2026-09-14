-- Creixement v8 — Kairon runtime contract convergence.
-- Apply after 015_v7_kairon_schema_convergence.sql.
-- Canonicalises the mixed Lovable/GitHub schema and adds a fail-closed autonomy preflight.

alter table public.kairon_control_cycles_v7 add column if not exists sensed jsonb not null default '{}'::jsonb;
alter table public.kairon_control_cycles_v7 add column if not exists escalation_details jsonb not null default '[]'::jsonb;
alter table public.kairon_control_cycles_v7 add column if not exists receipt_ref text;
alter table public.kairon_control_cycles_v7 add column if not exists error jsonb;
alter table public.kairon_control_cycles_v7 add column if not exists summary jsonb not null default '{}'::jsonb;
alter table public.kairon_control_cycles_v7 add column if not exists blockers jsonb not null default '[]'::jsonb;
alter table public.kairon_control_cycles_v7 add column if not exists evidence_refs jsonb not null default '[]'::jsonb;
alter table public.kairon_control_cycles_v7 add column if not exists signals_sensed integer not null default 0;
alter table public.kairon_control_cycles_v7 add column if not exists decisions_made integer not null default 0;
alter table public.kairon_control_cycles_v7 add column if not exists actions_executed integer not null default 0;
alter table public.kairon_control_cycles_v7 add column if not exists self_heal_actions integer not null default 0;

-- Lovable initially modelled escalations as a count, while the first governed migration modelled it as JSON.
-- Converge on an integer count and preserve structured details separately.
do $$
declare v_type text;
begin
  select data_type into v_type
  from information_schema.columns
  where table_schema='public' and table_name='kairon_control_cycles_v7' and column_name='escalations';

  if v_type is null then
    alter table public.kairon_control_cycles_v7 add column escalations integer not null default 0;
  elsif v_type='jsonb' then
    alter table public.kairon_control_cycles_v7 alter column escalations drop default;
    alter table public.kairon_control_cycles_v7
      alter column escalations type integer
      using case
        when escalations is null then 0
        when jsonb_typeof(escalations)='array' then jsonb_array_length(escalations)
        when jsonb_typeof(escalations)='number' then greatest(0,(escalations::text)::integer)
        else 0
      end;
    alter table public.kairon_control_cycles_v7 alter column escalations set default 0;
    alter table public.kairon_control_cycles_v7 alter column escalations set not null;
  end if;
end;
$$;

alter table public.kairon_control_cycles_v7 add column if not exists cycle_key text;
alter table public.kairon_control_cycles_v7 add column if not exists idempotency_key text;
alter table public.kairon_control_cycles_v7 add column if not exists correlation_id uuid;
alter table public.kairon_control_cycles_v7 add column if not exists runtime_id text;
alter table public.kairon_control_cycles_v7 alter column cycle_key set default ('cycle:' || gen_random_uuid()::text);
alter table public.kairon_control_cycles_v7 alter column correlation_id set default gen_random_uuid();
update public.kairon_control_cycles_v7 set cycle_key='cycle:'||id::text where cycle_key is null;
update public.kairon_control_cycles_v7 set idempotency_key=cycle_key where idempotency_key is null;
update public.kairon_control_cycles_v7 set correlation_id=gen_random_uuid() where correlation_id is null;
update public.kairon_control_cycles_v7 set runtime_id='legacy-unattributed' where runtime_id is null;
alter table public.kairon_control_cycles_v7 alter column cycle_key set not null;
alter table public.kairon_control_cycles_v7 alter column idempotency_key set not null;
alter table public.kairon_control_cycles_v7 alter column correlation_id set not null;
alter table public.kairon_control_cycles_v7 alter column runtime_id set not null;
create unique index if not exists kairon_cycles_cycle_key_uq on public.kairon_control_cycles_v7(cycle_key);
create unique index if not exists kairon_cycles_idempotency_uq on public.kairon_control_cycles_v7(idempotency_key);
create index if not exists kairon_cycles_runtime_started_idx on public.kairon_control_cycles_v7(runtime_id,started_at desc);

-- Completed cycles are historical evidence. Their identity and captured decision surface are immutable.
create or replace function public.creixement_guard_kairon_cycle_v8()
returns trigger language plpgsql set search_path=public
as $$
begin
  if new.id is distinct from old.id
     or new.cycle_key is distinct from old.cycle_key
     or new.correlation_id is distinct from old.correlation_id
     or new.idempotency_key is distinct from old.idempotency_key
     or new.runtime_id is distinct from old.runtime_id
     or new.started_at is distinct from old.started_at then
    raise exception 'Kairon cycle identity is immutable';
  end if;

  if old.status in ('healthy','degraded','blocked','failed') then
    if new.status is distinct from old.status
       or new.sensed is distinct from old.sensed
       or new.priorities is distinct from old.priorities
       or new.automatic_actions is distinct from old.automatic_actions
       or new.escalations is distinct from old.escalations
       or new.escalation_details is distinct from old.escalation_details
       or new.self_heal is distinct from old.self_heal
       or new.outcome is distinct from old.outcome
       or new.summary is distinct from old.summary
       or new.blockers is distinct from old.blockers then
      raise exception 'Completed Kairon cycle evidence is immutable';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists kairon_cycles_v8_guard on public.kairon_control_cycles_v7;
create trigger kairon_cycles_v8_guard
before update on public.kairon_control_cycles_v7
for each row execute function public.creixement_guard_kairon_cycle_v8();

-- Central fail-closed answer for Kairon's two autonomy planes:
-- maintenance L2 (internal reversible repair) and economic L2 (business execution).
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

  select coalesce(healthy_runtime_instances,0)>0,
         coalesce(critical_drift,0)=0
           and coalesce(critical_incidents,0)=0
           and coalesce(open_job_dead_letters,0)=0
           and coalesce(open_outbox_dead_letters,0)=0
           and coalesce(open_handler_circuits,0)=0
  into v_runtime_alive,v_safety
  from public.v_operating_health_v6 limit 1;
  v_runtime_alive := coalesce(v_runtime_alive,false);
  v_safety := coalesce(v_safety,false);

  select coalesce(high_frequency_ready,false) into v_scheduler
  from public.v_scheduler_readiness_v6 limit 1;
  v_scheduler := coalesce(v_scheduler,false);

  select coalesce(promotable,false) into v_promotable
  from public.v_production_gate_v6 limit 1;
  v_promotable := coalesce(v_promotable,false);

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
      when not v_runtime_alive then 'no recent healthy runtime heartbeat'
      when not v_safety then 'runtime safety gate is not clean'
      when not v_scheduler then 'high-frequency scheduler is not verified'
      when not v_promotable then 'current release is not evidence-promotable'
      else 'Kairon maintenance and bounded economic L2 are permitted'
    end,
    v_global,v_runtime_alive,v_scheduler,v_safety,v_promotable;
end;
$$;

create or replace view public.v_kairon_command_v8 with (security_invoker=on) as
with preflight as (
  select * from public.creixement_kairon_preflight_v8() limit 1
)
select
  now() as observed_at,
  s.operator_name,
  s.mode as recorded_mode,
  p.effective_mode,
  s.autonomy_ceiling,
  s.mission as mission_statement,
  p.maintenance_allowed,
  p.economic_l2_allowed,
  p.reason as autonomy_reason,
  p.global_runtime_state,
  p.runtime_alive,
  p.scheduler_ready,
  p.safety_clean,
  p.release_promotable,
  s.last_cycle_at,
  s.last_cycle_status,
  s.last_cycle_id,
  s.current_focus,
  s.current_blockers,
  s.control_snapshot,
  (select count(*) from public.kairon_directives_v7 where coalesce(status,'active')='active' and coalesce(active,true)=true) as active_directives,
  (select count(*) from public.v_owner_decision_queue_v6) as owner_decisions_open,
  (select count(*) from public.v_owner_action_queue_v4) as owner_actions_open,
  (select count(*) from public.opportunities where status in ('qualified','actionable','testing','exploring')) as actionable_opportunities,
  (select count(*) from public.agents) as specialist_agents,
  (select count(*) from public.agents where health='healthy') as healthy_agents
from public.kairon_state_v7 s
cross join preflight p
where s.singleton=true;

-- Keep the v7 cockpit alias stable while all consumers migrate to v8.
create or replace view public.v_kairon_command_v7 with (security_invoker=on) as
select * from public.v_kairon_command_v8;

-- Desired state makes Kairon itself observable by runtime reconciliation.
insert into public.desired_runtime_state_v4(kind,state_key,desired,auto_remediate,active,evidence_refs)
values(
  'job','kairon-control-cycle-v7',
  '{"enabled":true,"handler_key":"kairon.control_cycle","autonomy_level":"L2"}'::jsonb,
  true,true,'["db/migrations/016_v8_kairon_runtime_contract.sql"]'::jsonb
)
on conflict(kind,state_key) do update set desired=excluded.desired,auto_remediate=excluded.auto_remediate,active=true,evidence_refs=excluded.evidence_refs,updated_at=now();
