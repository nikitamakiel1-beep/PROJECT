-- Creixement v10 — Kairon-led business portfolio + venture foundry.
-- Tectum is the first operating project inside Business; future projects originate
-- from evidence-linked opportunities and are incubated only behind the supervised L2 gate.
-- Apply after 021_v9_runtime_proof_and_scheduler_autoverify.sql.

alter table public.opportunities
  add column if not exists truth_level text not null default 'hypothesis';

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname='opportunities_truth_level_v10_check'
      and conrelid='public.opportunities'::regclass
  ) then
    alter table public.opportunities add constraint opportunities_truth_level_v10_check
      check (truth_level in (
        'verified_external_outcome','executed_connector_receipt','governed_source_evidence',
        'human_approved_business_decision','evidence_backed_inference','hypothesis','generated_narrative'
      ));
  end if;
end $$;

create table if not exists public.business_projects_v10 (
  id uuid primary key default gen_random_uuid(),
  project_key text not null unique,
  display_name text not null,
  project_type text not null,
  niche text not null,
  portfolio_role text not null default 'venture' check (portfolio_role in ('core','venture')),
  status text not null default 'incubating' check (status in ('incubating','operating','scaling','paused','archived')),
  origin text not null check (origin in ('owner_seeded','kairon_foundry')),
  source_opportunity_id uuid references public.opportunities(id) on delete set null,
  truth_level text not null default 'hypothesis' check (truth_level in (
    'verified_external_outcome','executed_connector_receipt','governed_source_evidence',
    'human_approved_business_decision','evidence_backed_inference','hypothesis','generated_narrative'
  )),
  autonomy_ceiling text not null default 'L2' check (autonomy_ceiling in ('L0','L1','L2')),
  executive_agent text not null default 'Kairon',
  summary text,
  verified_external_outcomes integer not null default 0 check (verified_external_outcomes >= 0),
  executed_receipts integer not null default 0 check (executed_receipts >= 0),
  owner_approved boolean not null default false,
  evidence_refs jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.business_project_candidates_v10 (
  id uuid primary key default gen_random_uuid(),
  candidate_key text not null unique,
  proposed_project_key text not null,
  title text not null,
  niche text not null,
  product_code text,
  source_opportunity_id uuid not null references public.opportunities(id) on delete cascade,
  stage text not null check (stage in ('hypothesis','discovery','experiment','incubating','paused','archived')),
  decision text not null check (decision in ('recommend','experiment','incubate','escalate')),
  autonomy_level text not null default 'L1' check (autonomy_level in ('L0','L1','L2','L3')),
  requires_owner boolean not null default false,
  score numeric not null default 0 check (score >= 0 and score <= 1),
  truth_level text not null default 'hypothesis' check (truth_level in (
    'verified_external_outcome','executed_connector_receipt','governed_source_evidence',
    'human_approved_business_decision','evidence_backed_inference','hypothesis','generated_narrative'
  )),
  gate_snapshot jsonb not null default '{}'::jsonb,
  reasons jsonb not null default '[]'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  promoted_project_id uuid references public.business_projects_v10(id) on delete set null,
  last_evaluated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.business_project_events_v10 (
  id uuid primary key default gen_random_uuid(),
  event_key text not null unique,
  project_id uuid references public.business_projects_v10(id) on delete set null,
  candidate_id uuid references public.business_project_candidates_v10(id) on delete set null,
  event_type text not null,
  actor text not null default 'Kairon',
  truth_level text not null default 'hypothesis',
  payload jsonb not null default '{}'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  occurred_at timestamptz not null default now()
);

create index if not exists business_projects_v10_status_idx on public.business_projects_v10(status, updated_at desc);
create index if not exists business_projects_v10_niche_idx on public.business_projects_v10(niche, status);
create index if not exists business_candidates_v10_decision_idx on public.business_project_candidates_v10(decision, score desc);
create index if not exists business_candidates_v10_source_idx on public.business_project_candidates_v10(source_opportunity_id);
create index if not exists business_events_v10_time_idx on public.business_project_events_v10(occurred_at desc);

alter table public.business_projects_v10 enable row level security;
alter table public.business_project_candidates_v10 enable row level security;
alter table public.business_project_events_v10 enable row level security;

revoke all on public.business_projects_v10, public.business_project_candidates_v10, public.business_project_events_v10 from public, anon, authenticated;
grant all on public.business_projects_v10, public.business_project_candidates_v10, public.business_project_events_v10 to service_role;

create or replace function public.creixement_guard_business_project_v10()
returns trigger
language plpgsql
set search_path=public
as $$
begin
  if new.origin='kairon_foundry' and new.status in ('operating','scaling') then
    if new.owner_approved is not true
       or coalesce(new.verified_external_outcomes,0) < 1
       or coalesce(new.executed_receipts,0) < 1 then
      raise exception 'Kairon-foundry projects cannot self-declare operating/scaling without owner approval, verified external outcome and executed receipt';
    end if;
  end if;
  if new.autonomy_ceiling='L3' then
    raise exception 'Business projects cannot raise Kairon above the constitutional L2 ceiling';
  end if;
  return new;
end;
$$;

drop trigger if exists business_projects_v10_guard on public.business_projects_v10;
create trigger business_projects_v10_guard
before insert or update on public.business_projects_v10
for each row execute function public.creixement_guard_business_project_v10();

insert into public.business_projects_v10(
  project_key,display_name,project_type,niche,portfolio_role,status,origin,truth_level,
  autonomy_ceiling,executive_agent,summary,owner_approved,evidence_refs,metadata
)
values(
  'tectum','Tectum','real_estate_intelligence','real-estate','core','operating','owner_seeded',
  'human_approved_business_decision','L2','Kairon',
  'Creixement real-estate intelligence, underwriting and controlled report operation.',
  true,'["config:creixement-business-portfolio-v10.json"]'::jsonb,
  '{"businessParent":"creixement","specialistAgent":"tectum","legacyRoute":"/tectum"}'::jsonb
)
on conflict(project_key) do update set
  display_name=excluded.display_name,
  project_type=excluded.project_type,
  niche=excluded.niche,
  portfolio_role='core',
  origin='owner_seeded',
  truth_level='human_approved_business_decision',
  executive_agent='Kairon',
  summary=excluded.summary,
  owner_approved=true,
  evidence_refs=excluded.evidence_refs,
  metadata=excluded.metadata,
  updated_at=now();

create or replace function public.creixement_run_venture_foundry_v10()
returns table(
  evaluated integer,
  retained_candidates integer,
  experiments_ready integer,
  incubated_projects integer,
  economic_l2_open boolean
)
language plpgsql
security definer
set search_path=public
as $$
declare
  v_op public.opportunities%rowtype;
  v_candidate public.business_project_candidates_v10%rowtype;
  v_project public.business_projects_v10%rowtype;
  v_economic_l2 boolean := false;
  v_project_slots integer := 0;
  v_strength integer := 0;
  v_evidence_present boolean := false;
  v_source_usable boolean := false;
  v_experiment_ready boolean := false;
  v_incubate_ready boolean := false;
  v_decision text;
  v_stage text;
  v_autonomy text;
  v_score numeric;
  v_candidate_key text;
  v_project_key text;
  v_evaluated integer := 0;
  v_retained integer := 0;
  v_experiments integer := 0;
  v_incubated integer := 0;
begin
  select coalesce((s.control_snapshot->'supervisor'->'authority'->>'supervisedEconomicL2Open')::boolean,false)
  into v_economic_l2
  from public.kairon_state_v7 s
  where s.singleton=true
  limit 1;
  v_economic_l2 := coalesce(v_economic_l2,false);

  select greatest(0, 12-count(*))::integer
  into v_project_slots
  from public.business_projects_v10
  where status in ('incubating','operating','scaling');

  for v_op in
    select o.*
    from public.opportunities o
    where o.status in ('qualified','actionable','testing','exploring')
      and o.blocker is null
      and (o.expires_at is null or o.expires_at>now())
    order by coalesce(o.opportunity_score,0) desc, o.updated_at desc
    limit 50
  loop
    v_evaluated := v_evaluated + 1;
    v_evidence_present := jsonb_typeof(coalesce(v_op.evidence_refs,'[]'::jsonb))='array'
      and jsonb_array_length(coalesce(v_op.evidence_refs,'[]'::jsonb))>0;
    v_source_usable := v_evidence_present;
    if not v_source_usable then
      continue;
    end if;

    v_strength := case v_op.truth_level
      when 'verified_external_outcome' then 7
      when 'executed_connector_receipt' then 6
      when 'governed_source_evidence' then 5
      when 'human_approved_business_decision' then 4
      when 'evidence_backed_inference' then 3
      when 'hypothesis' then 2
      else 1
    end;

    v_score := greatest(0,least(1,coalesce(v_op.opportunity_score,
      0.19*coalesce(v_op.evidence_quality,0)
      +0.15*coalesce(v_op.confidence,0)
      +0.18*coalesce(v_op.strategic_fit,0)
      +0.10*coalesce(v_op.automation_potential,0)
      +0.09*coalesce(v_op.recurring_potential,0)
      +0.08*coalesce(v_op.reversibility,0)
      -0.10*coalesce(v_op.downside_risk,0)
      -0.08*coalesce(v_op.uncertainty,0)
      -0.08*coalesce(v_op.rights_legal_complexity,0)
    )));

    v_decision := 'recommend';
    v_stage := 'discovery';
    v_autonomy := 'L1';

    v_experiment_ready := v_economic_l2
      and v_strength>=3
      and coalesce(v_op.evidence_quality,0)>=0.45
      and coalesce(v_op.confidence,0)>=0.45
      and coalesce(v_op.strategic_fit,0)>=0.55
      and coalesce(v_op.downside_risk,1)<=0.45
      and coalesce(v_op.rights_legal_complexity,1)<=0.50;

    if v_experiment_ready then
      v_decision := 'experiment';
      v_stage := 'experiment';
      v_autonomy := 'L2';
      v_experiments := v_experiments + 1;
    end if;

    v_incubate_ready := v_experiment_ready
      and v_strength>=5
      and coalesce(v_op.evidence_quality,0)>=0.65
      and coalesce(v_op.confidence,0)>=0.60
      and coalesce(v_op.reversibility,0)>=0.80
      and v_project_slots>0;

    if v_incubate_ready then
      v_decision := 'incubate';
      v_stage := 'incubating';
      v_autonomy := 'L2';
    end if;

    v_candidate_key := 'venture:'||v_op.id::text;
    v_project_key := 'venture-'||left(regexp_replace(lower(coalesce(v_op.niche,'venture')),'[^a-z0-9]+','-','g'),32)||'-'||left(v_op.id::text,8);

    insert into public.business_project_candidates_v10(
      candidate_key,proposed_project_key,title,niche,product_code,source_opportunity_id,
      stage,decision,autonomy_level,requires_owner,score,truth_level,gate_snapshot,reasons,evidence_refs,last_evaluated_at
    ) values(
      v_candidate_key,v_project_key,v_op.title,coalesce(v_op.niche,'venture'),v_op.product_code,v_op.id,
      v_stage,v_decision,v_autonomy,false,v_score,v_op.truth_level,
      jsonb_build_object(
        'economicL2Open',v_economic_l2,
        'truthStrength',v_strength,
        'evidencePresent',v_evidence_present,
        'evidenceQuality',coalesce(v_op.evidence_quality,0),
        'confidence',coalesce(v_op.confidence,0),
        'strategicFit',coalesce(v_op.strategic_fit,0),
        'reversibility',coalesce(v_op.reversibility,0),
        'downsideRisk',coalesce(v_op.downside_risk,1),
        'rightsLegalComplexity',coalesce(v_op.rights_legal_complexity,1),
        'projectSlotsRemaining',v_project_slots
      ),
      jsonb_build_array(
        case v_decision
          when 'incubate' then 'Governed evidence and supervised economic L2 permit reversible incubation.'
          when 'experiment' then 'Evidence-backed opportunity is eligible for a bounded internal L2 experiment.'
          else 'Retained as an evidence-linked L1 project recommendation.'
        end
      ),
      coalesce(v_op.evidence_refs,'[]'::jsonb),now()
    )
    on conflict(candidate_key) do update set
      proposed_project_key=excluded.proposed_project_key,
      title=excluded.title,
      niche=excluded.niche,
      product_code=excluded.product_code,
      stage=excluded.stage,
      decision=excluded.decision,
      autonomy_level=excluded.autonomy_level,
      requires_owner=excluded.requires_owner,
      score=excluded.score,
      truth_level=excluded.truth_level,
      gate_snapshot=excluded.gate_snapshot,
      reasons=excluded.reasons,
      evidence_refs=excluded.evidence_refs,
      last_evaluated_at=now(),
      updated_at=now()
    returning * into v_candidate;

    v_retained := v_retained + 1;

    insert into public.business_project_events_v10(
      event_key,candidate_id,event_type,actor,truth_level,payload,evidence_refs
    ) values(
      v_candidate_key||':'||v_decision,
      v_candidate.id,
      'foundry.'||v_decision,
      'Kairon',v_op.truth_level,
      jsonb_build_object('score',v_score,'stage',v_stage,'sourceOpportunityId',v_op.id,'economicL2Open',v_economic_l2),
      coalesce(v_op.evidence_refs,'[]'::jsonb)
    ) on conflict(event_key) do nothing;

    if v_incubate_ready then
      insert into public.business_projects_v10(
        project_key,display_name,project_type,niche,portfolio_role,status,origin,source_opportunity_id,
        truth_level,autonomy_ceiling,executive_agent,summary,owner_approved,evidence_refs,metadata
      ) values(
        v_project_key,v_op.title,'kairon_venture',coalesce(v_op.niche,'venture'),'venture','incubating','kairon_foundry',v_op.id,
        v_op.truth_level,'L2','Kairon','Evidence-backed venture incubated by Kairon under the supervised economic L2 gate.',false,
        coalesce(v_op.evidence_refs,'[]'::jsonb),jsonb_build_object('candidateKey',v_candidate_key,'source','venture_foundry_v10')
      )
      on conflict(project_key) do update set
        display_name=excluded.display_name,
        niche=excluded.niche,
        truth_level=excluded.truth_level,
        evidence_refs=excluded.evidence_refs,
        metadata=public.business_projects_v10.metadata || excluded.metadata,
        updated_at=now()
      returning * into v_project;

      update public.business_project_candidates_v10
      set promoted_project_id=v_project.id, updated_at=now()
      where id=v_candidate.id;

      insert into public.business_project_events_v10(
        event_key,project_id,candidate_id,event_type,actor,truth_level,payload,evidence_refs
      ) values(
        v_candidate_key||':project-incubated',v_project.id,v_candidate.id,'project.incubated','Kairon',v_op.truth_level,
        jsonb_build_object('projectKey',v_project.project_key,'autonomyCeiling','L2'),coalesce(v_op.evidence_refs,'[]'::jsonb)
      ) on conflict(event_key) do nothing;

      v_project_slots := greatest(0,v_project_slots-1);
      v_incubated := v_incubated + 1;
    end if;
  end loop;

  return query select v_evaluated,v_retained,v_experiments,v_incubated,v_economic_l2;
end;
$$;

revoke all on function public.creixement_run_venture_foundry_v10() from public, anon, authenticated;
grant execute on function public.creixement_run_venture_foundry_v10() to service_role;

create or replace view public.v_business_portfolio_v10 as
select
  p.id,p.project_key,p.display_name,p.project_type,p.niche,p.portfolio_role,p.status,p.origin,
  p.source_opportunity_id,p.truth_level,p.autonomy_ceiling,p.executive_agent,p.summary,
  p.verified_external_outcomes,p.executed_receipts,p.owner_approved,p.evidence_refs,p.metadata,
  p.created_at,p.updated_at,
  case when p.origin='owner_seeded' then 'owner-established' else 'Kairon-foundry' end as origin_label
from public.business_projects_v10 p
order by case p.status when 'operating' then 1 when 'scaling' then 2 when 'incubating' then 3 when 'paused' then 4 else 5 end,
         p.updated_at desc;

create or replace view public.v_business_foundry_v10 as
select
  c.id,c.candidate_key,c.proposed_project_key,c.title,c.niche,c.product_code,c.source_opportunity_id,
  c.stage,c.decision,c.autonomy_level,c.requires_owner,c.score,c.truth_level,c.gate_snapshot,c.reasons,
  c.evidence_refs,c.promoted_project_id,c.last_evaluated_at,c.created_at,c.updated_at,
  o.expected_revenue_low,o.expected_revenue_high,o.probability,o.confidence,o.evidence_quality,
  o.strategic_fit,o.automation_potential,o.recurring_potential,o.reversibility,o.time_to_cash_days,
  o.downside_risk,o.rights_legal_complexity,o.uncertainty,o.next_test,o.blocker
from public.business_project_candidates_v10 c
join public.opportunities o on o.id=c.source_opportunity_id
where c.stage not in ('archived');

create or replace view public.v_business_portfolio_summary_v10 as
select
  now() as observed_at,
  count(*) filter (where status in ('operating','scaling'))::integer as operating_projects,
  count(*) filter (where status='incubating')::integer as incubating_projects,
  count(*) filter (where status='paused')::integer as paused_projects,
  count(*) filter (where project_key='tectum' and status in ('operating','scaling'))::integer as tectum_operating,
  (select count(*)::integer from public.business_project_candidates_v10 where stage not in ('archived')) as foundry_candidates,
  (select count(*)::integer from public.business_project_candidates_v10 where decision='incubate' and stage='incubating') as incubation_ready_or_active,
  (select count(*)::integer from public.opportunities where status in ('qualified','actionable','testing','exploring')) as actionable_opportunities,
  coalesce((select (control_snapshot->'supervisor'->'authority'->>'supervisedEconomicL2Open')::boolean from public.kairon_state_v7 where singleton=true limit 1),false) as supervised_economic_l2_open,
  'Kairon'::text as executive_agent
from public.business_projects_v10;

revoke all on public.v_business_portfolio_v10, public.v_business_foundry_v10, public.v_business_portfolio_summary_v10 from public, anon, authenticated;
grant select on public.v_business_portfolio_v10, public.v_business_foundry_v10, public.v_business_portfolio_summary_v10 to service_role;

insert into public.job_definitions(
  job_key,name,description,trigger_type,schedule_expr,timezone,event_topic,handler_key,owner_agent_slug,
  autonomy_level,policy_key,required_connectors,enabled,max_runtime_seconds,max_attempts,concurrency_limit
)
values(
  'business-venture-foundry-v10','Kairon venture foundry V10',
  'Converts evidence-linked opportunities into project recommendations, bounded experiments and reversible incubating projects without crossing the L2 ceiling.',
  'cron','37 */6 * * *','Europe/Madrid',null,'business.venture_foundry_cycle','chief-orchestrator',
  'L2','internal-runtime-v9','[]'::jsonb,true,90,3,1
)
on conflict(job_key) do update set
  name=excluded.name,description=excluded.description,trigger_type=excluded.trigger_type,
  schedule_expr=excluded.schedule_expr,timezone=excluded.timezone,handler_key=excluded.handler_key,
  owner_agent_slug=excluded.owner_agent_slug,autonomy_level=excluded.autonomy_level,
  policy_key=excluded.policy_key,required_connectors=excluded.required_connectors,enabled=excluded.enabled,
  max_runtime_seconds=excluded.max_runtime_seconds,max_attempts=excluded.max_attempts,concurrency_limit=excluded.concurrency_limit,
  updated_at=now();

insert into public.desired_runtime_state_v4(state_key,kind,desired,source_ref,active)
values(
  'business-venture-foundry-v10','job',
  '{"enabled":true,"handler_key":"business.venture_foundry_cycle","autonomy_level":"L2","schedule":"37 */6 * * *","executive_agent":"Kairon"}'::jsonb,
  'db/migrations/022_v10_business_portfolio_and_venture_foundry.sql',true
)
on conflict(kind,state_key) do update set
  desired=excluded.desired,source_ref=excluded.source_ref,active=true,updated_at=now();

comment on table public.business_projects_v10 is 'Creixement business portfolio. Tectum is the first operating project; Kairon may add evidence-backed incubating ventures under L2.';
comment on table public.business_project_candidates_v10 is 'Evidence-linked Kairon venture foundry candidates. Generated hypotheses are never represented as verified businesses.';
comment on function public.creixement_run_venture_foundry_v10() is 'Fail-closed Kairon venture foundry cycle; no external effect and no automatic operating/scaling promotion.';
