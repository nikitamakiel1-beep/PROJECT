-- Creixement Autonomous Economic Brain v2
-- Cloud-only control-plane migration. Safe to apply after the v1 Lovable/Supabase schema.
-- Production callers should use server-side/service-role access; RLS is enabled with no anon policies here.

create extension if not exists pgcrypto;

create or replace function public.creixement_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.autonomy_constitutions (
  id uuid primary key default gen_random_uuid(),
  version text not null unique,
  status text not null default 'draft' check (status in ('draft','active','retired')),
  constitution jsonb not null,
  source_ref text,
  digest text,
  activated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.opportunity_signals (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null default gen_random_uuid(),
  source_type text not null,
  source_ref text,
  source_event_id text,
  observed_at timestamptz not null default now(),
  freshness_at timestamptz,
  rights_status text not null default 'unknown' check (rights_status in ('unknown','permitted','restricted','blocked')),
  signal_type text not null,
  title text not null,
  summary text,
  payload jsonb not null default '{}'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  dedupe_key text,
  content_digest text,
  status text not null default 'new' check (status in ('new','verified','rejected','consumed','expired')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(source_type, source_event_id)
);

create index if not exists opportunity_signals_status_idx on public.opportunity_signals(status, observed_at desc);
create index if not exists opportunity_signals_dedupe_idx on public.opportunity_signals(dedupe_key);
create index if not exists opportunity_signals_type_idx on public.opportunity_signals(signal_type, observed_at desc);

create table if not exists public.opportunities (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null default gen_random_uuid(),
  niche text not null,
  product_code text,
  target_entity_ref text,
  title text not null,
  problem_evidence text,
  source_signal_ids jsonb not null default '[]'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  expected_revenue_low numeric,
  expected_revenue_high numeric,
  expected_contribution_margin_pct numeric,
  probability numeric check (probability is null or (probability >= 0 and probability <= 1)),
  confidence numeric check (confidence is null or (confidence >= 0 and confidence <= 1)),
  evidence_quality numeric check (evidence_quality is null or (evidence_quality >= 0 and evidence_quality <= 1)),
  strategic_fit numeric check (strategic_fit is null or (strategic_fit >= 0 and strategic_fit <= 1)),
  automation_potential numeric check (automation_potential is null or (automation_potential >= 0 and automation_potential <= 1)),
  recurring_potential numeric check (recurring_potential is null or (recurring_potential >= 0 and recurring_potential <= 1)),
  reversibility numeric check (reversibility is null or (reversibility >= 0 and reversibility <= 1)),
  delivery_effort_hours numeric,
  time_to_cash_days numeric,
  uncertainty numeric check (uncertainty is null or (uncertainty >= 0 and uncertainty <= 1)),
  rights_legal_complexity numeric check (rights_legal_complexity is null or (rights_legal_complexity >= 0 and rights_legal_complexity <= 1)),
  downside_risk numeric check (downside_risk is null or (downside_risk >= 0 and downside_risk <= 1)),
  decision_mode text check (decision_mode is null or decision_mode in ('USE','BUILD','BUY','COMBINE','ABSTAIN')),
  opportunity_score numeric,
  next_test text,
  blocker text,
  status text not null default 'detected' check (status in ('detected','researching','qualified','testing','authorized','executing','won','lost','archived','expired','rejected')),
  expires_at timestamptz,
  owner_agent text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists opportunities_radar_idx on public.opportunities(status, opportunity_score desc nulls last, created_at desc);
create index if not exists opportunities_niche_idx on public.opportunities(niche, status);
create index if not exists opportunities_target_idx on public.opportunities(target_entity_ref);

create table if not exists public.commercial_genomes (
  id uuid primary key default gen_random_uuid(),
  lineage_id uuid not null default gen_random_uuid(),
  parent_ids jsonb not null default '[]'::jsonb,
  niche text not null,
  generation integer not null default 1,
  variant_name text not null,
  genes jsonb not null,
  exploration_budget numeric not null default 1,
  telomere numeric not null default 1 check (telomere >= 0),
  fitness numeric,
  confidence numeric check (confidence is null or (confidence >= 0 and confidence <= 1)),
  verified_observations integer not null default 0,
  verified_successes integer not null default 0,
  paid_successes integer not null default 0,
  status text not null default 'experimental' check (status in ('experimental','active','champion','senescent','archived','blocked')),
  model_version text not null default 'v2',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists commercial_genomes_niche_idx on public.commercial_genomes(niche, status, fitness desc nulls last);
create index if not exists commercial_genomes_lineage_idx on public.commercial_genomes(lineage_id, generation);

create table if not exists public.genome_observations (
  id uuid primary key default gen_random_uuid(),
  genome_id uuid not null references public.commercial_genomes(id) on delete restrict,
  opportunity_id uuid references public.opportunities(id) on delete set null,
  observation_type text not null,
  verified boolean not null default false,
  paid boolean not null default false,
  revenue numeric,
  direct_cost numeric,
  contribution_margin numeric,
  outcome_score numeric,
  evidence_refs jsonb not null default '[]'::jsonb,
  receipt_ref text,
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists genome_observations_genome_idx on public.genome_observations(genome_id, occurred_at desc);

create table if not exists public.counterparties (
  id uuid primary key default gen_random_uuid(),
  entity_key text not null unique,
  entity_type text not null,
  display_name text,
  relationship_types jsonb not null default '[]'::jsonb,
  business_context jsonb not null default '{}'::jsonb,
  product_fit jsonb not null default '{}'::jsonb,
  interaction_summary jsonb not null default '{}'::jsonb,
  commercial_outcomes jsonb not null default '{}'::jsonb,
  consent_constraints jsonb not null default '{}'::jsonb,
  provenance jsonb not null default '[]'::jsonb,
  freshness_at timestamptz,
  next_useful_action text,
  status text not null default 'active' check (status in ('active','watch','do_not_contact','archived','blocked')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists counterparties_status_idx on public.counterparties(status, freshness_at desc nulls last);

create table if not exists public.capability_evidence (
  id uuid primary key default gen_random_uuid(),
  capability_key text not null,
  product_code text,
  niche text,
  execution_count integer not null default 0,
  verified_success_count integer not null default 0,
  paid_success_count integer not null default 0,
  qa_pass_count integer not null default 0,
  evidence_refs jsonb not null default '[]'::jsonb,
  reproducibility_score numeric,
  unit_economics_score numeric,
  promotion_state text not null default 'observed' check (promotion_state in ('observed','candidate','promoted','paused','retired')),
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(capability_key, product_code)
);

create table if not exists public.attention_allocations (
  id uuid primary key default gen_random_uuid(),
  niche text not null,
  allocation_epoch text not null,
  exploit numeric not null check (exploit >= 0),
  adjacency numeric not null check (adjacency >= 0),
  exploration numeric not null check (exploration >= 0),
  rationale jsonb not null default '{}'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  policy_version text not null,
  created_at timestamptz not null default now(),
  unique(niche, allocation_epoch),
  check (abs((exploit + adjacency + exploration) - 1.0) < 0.000001)
);

create table if not exists public.evolution_events (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null default gen_random_uuid(),
  niche text not null,
  event_type text not null check (event_type in ('mutation','crossover','selection','senescence','archive','restore','promotion','allocation_change')),
  parent_genome_ids jsonb not null default '[]'::jsonb,
  child_genome_ids jsonb not null default '[]'::jsonb,
  changed_genes jsonb not null default '{}'::jsonb,
  rationale jsonb not null default '{}'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  policy_version text not null,
  created_at timestamptz not null default now()
);

create index if not exists evolution_events_niche_idx on public.evolution_events(niche, created_at desc);

create table if not exists public.execution_receipts (
  id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null,
  idempotency_key text not null unique,
  actor_agent text not null,
  action_class text not null,
  connector_slug text,
  policy_version text not null,
  policy_decision text not null,
  input_digest text not null,
  output_digest text,
  connector_receipt jsonb,
  status text not null check (status in ('started','succeeded','failed','blocked','queued','cancelled')),
  error jsonb,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists execution_receipts_correlation_idx on public.execution_receipts(correlation_id, created_at);
create index if not exists execution_receipts_action_idx on public.execution_receipts(action_class, created_at desc);

create or replace function public.creixement_opportunity_score(
  expected_contribution_margin_pct numeric,
  paid_demand_evidence numeric,
  qualified_demand_evidence numeric,
  automation_potential numeric,
  recurring_potential numeric,
  strategic_fit numeric,
  reversibility numeric,
  evidence_quality numeric,
  delivery_effort_hours numeric,
  time_to_cash_days numeric,
  uncertainty numeric,
  rights_legal_complexity numeric,
  downside_risk numeric
) returns numeric
language sql
immutable
as $$
  select
    coalesce(expected_contribution_margin_pct,0) * 0.010
    + coalesce(paid_demand_evidence,0) * 1.40
    + coalesce(qualified_demand_evidence,0) * 0.80
    + coalesce(automation_potential,0) * 0.50
    + coalesce(recurring_potential,0) * 0.80
    + coalesce(strategic_fit,0) * 0.50
    + coalesce(reversibility,0) * 0.40
    + coalesce(evidence_quality,0) * 0.90
    - least(coalesce(delivery_effort_hours,0) / 40.0, 1.0) * 0.50
    - least(coalesce(time_to_cash_days,0) / 90.0, 1.0) * 0.40
    - coalesce(uncertainty,0) * 0.80
    - coalesce(rights_legal_complexity,0) * 1.20
    - coalesce(downside_risk,0) * 1.20;
$$;

create or replace view public.v_opportunity_radar as
select
  o.*,
  case
    when o.status in ('won','lost','archived','expired','rejected') then false
    when o.expires_at is not null and o.expires_at < now() then false
    else true
  end as actionable
from public.opportunities o;

create or replace view public.v_genome_fitness as
select
  g.*,
  coalesce(sum(case when x.verified then 1 else 0 end),0) as observed_verified_count,
  coalesce(sum(case when x.verified and x.outcome_score > 0 then 1 else 0 end),0) as positive_verified_count,
  coalesce(sum(case when x.paid then 1 else 0 end),0) as observed_paid_count,
  coalesce(sum(case when x.paid then coalesce(x.contribution_margin,0) else 0 end),0) as verified_contribution_margin
from public.commercial_genomes g
left join public.genome_observations x on x.genome_id = g.id
group by g.id;

-- Default deny from browser/anon until authenticated server routes and explicit policies exist.
alter table public.autonomy_constitutions enable row level security;
alter table public.opportunity_signals enable row level security;
alter table public.opportunities enable row level security;
alter table public.commercial_genomes enable row level security;
alter table public.genome_observations enable row level security;
alter table public.counterparties enable row level security;
alter table public.capability_evidence enable row level security;
alter table public.attention_allocations enable row level security;
alter table public.evolution_events enable row level security;
alter table public.execution_receipts enable row level security;

drop trigger if exists autonomy_constitutions_set_updated_at on public.autonomy_constitutions;
create trigger autonomy_constitutions_set_updated_at before update on public.autonomy_constitutions for each row execute function public.creixement_set_updated_at();
drop trigger if exists opportunity_signals_set_updated_at on public.opportunity_signals;
create trigger opportunity_signals_set_updated_at before update on public.opportunity_signals for each row execute function public.creixement_set_updated_at();
drop trigger if exists opportunities_set_updated_at on public.opportunities;
create trigger opportunities_set_updated_at before update on public.opportunities for each row execute function public.creixement_set_updated_at();
drop trigger if exists commercial_genomes_set_updated_at on public.commercial_genomes;
create trigger commercial_genomes_set_updated_at before update on public.commercial_genomes for each row execute function public.creixement_set_updated_at();
drop trigger if exists counterparties_set_updated_at on public.counterparties;
create trigger counterparties_set_updated_at before update on public.counterparties for each row execute function public.creixement_set_updated_at();
drop trigger if exists capability_evidence_set_updated_at on public.capability_evidence;
create trigger capability_evidence_set_updated_at before update on public.capability_evidence for each row execute function public.creixement_set_updated_at();

insert into public.autonomy_constitutions(version, status, constitution, source_ref, activated_at)
values (
  '2.0.0',
  'active',
  jsonb_build_object(
    'runtime','cloud_only',
    'buy_mode_enabled',false,
    'default_attention',jsonb_build_object('exploit',0.70,'adjacency',0.20,'exploration',0.10),
    'external_outreach_enabled',false,
    'public_content_publication_enabled',false,
    'product_catalog_publication_enabled',false,
    'archive_not_delete',true,
    'bounded_mutation',true,
    'max_genes_changed_per_mutation',2
  ),
  'config/creixement-autonomy-constitution-v2.json',
  now()
)
on conflict (version) do update
set constitution = excluded.constitution,
    source_ref = excluded.source_ref,
    status = excluded.status,
    activated_at = coalesce(public.autonomy_constitutions.activated_at, excluded.activated_at),
    updated_at = now();
