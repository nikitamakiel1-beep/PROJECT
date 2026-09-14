-- Creixement v9 — Conway-inspired bioecology.
-- Applies biological/evolutionary metaphors only as bounded operational mechanisms.
-- No consciousness/sentience claims; constitutional policy remains outside evolution.
-- Apply after 017_v8_release_attestation.sql.

create table if not exists public.bio_mechanism_registry_v9 (
  mechanism_key text primary key,
  biological_source text not null,
  operational_mapping text not null,
  max_autonomy text not null default 'L2' check (max_autonomy in ('L0','L1','L2')),
  enabled boolean not null default true,
  constitutional boolean not null default false,
  config jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.bio_mechanism_registry_v9(mechanism_key,biological_source,operational_mapping,max_autonomy,constitutional,config)
values
('slime_mold_routing','physarum/slime mould','Allocate attention across opportunity paths using nutrient, friction, risk and reinforced trail strength.','L2',false,'{"evaporation":0.12,"riskPenalty":2.0}'::jsonb),
('pheromone_foraging','ants/social insects','Reinforce verified productive routes and evaporate stale/unverified routes.','L2',false,'{"verifiedOnly":true}'::jsonb),
('swarm_quorum','bees/social insects','Require weighted agreement plus independent evidence sources before high-confidence collective recommendations.','L1',false,'{"threshold":0.67,"minIndependentSources":2}'::jsonb),
('asexual_budding','clonal reproduction','Spawn bounded experimental variants from one proven parent with confidence reset.','L2',false,'{}'::jsonb),
('sexual_recombination','sexual reproduction','Cross compatible high-evidence variants inside the same niche; reset child confidence and fitness.','L2',false,'{"sameNicheDefault":true}'::jsonb),
('mutation','evolution','Change a bounded number of evolvable genes using evidence-backed reasons.','L2',false,'{}'::jsonb),
('epigenetic_adaptation','epigenetics','Temporarily change phenotype/expression in response to environment without rewriting protected genome/constitution.','L2',false,'{}'::jsonb),
('telomere_senescence','cellular ageing','Decay exploration life after failures/generations; restore partially on verified paid success; archive senescent variants.','L2',false,'{}'::jsonb),
('red_queen_pressure','Red Queen dynamics','Increase adaptation pressure when competition/volatility/failure rises or novelty/fitness falls.','L2',false,'{}'::jsonb),
('niche_speciation','ecological speciation','Separate sufficiently divergent strategies into niches to avoid destructive one-size-fits-all optimization.','L2',false,'{}'::jsonb),
('homeostasis','physiology','Maintain operating energy/stress/resource envelopes and prioritize recovery when outside bounds.','L2',false,'{}'::jsonb),
('hormesis','adaptive stress response','Use modest verified stress to increase adaptation while suppressing risky exploration under extreme stress.','L2',false,'{}'::jsonb),
('immune_memory','adaptive immunity','Remember recurrent failure signatures; challenge or block suspicious patterns without weakening global policy.','L2',false,'{}'::jsonb),
('apoptosis_archive','programmed cell death','Archive persistently weak/senescent variants; never silently delete lineage/evidence.','L2',false,'{"archiveNotDelete":true}'::jsonb),
('hibernation','dormancy/torpor','Pause low-value organisms under scarcity/stress and wake them when demand/resource conditions improve.','L2',false,'{}'::jsonb),
('migration','animal migration','Shift bounded attention/variants toward niches with better verified resource-demand gradients.','L2',false,'{}'::jsonb),
('symbiosis','mutualism','Pair complementary specialists/strategies when diversity and health produce higher joint value.','L2',false,'{}'::jsonb),
('competition','intraspecific competition','Measure stronger peers inside a niche and apply selection pressure without deleting historical evidence.','L2',false,'{}'::jsonb),
('predator_prejudice_check','predator detection','Treat high-risk anomalies as challenge signals; require evidence before escalation to block.','L2',false,'{"failClosed":true}'::jsonb),
('wound_healing','tissue repair','Prioritize lease recovery, dead-letter triage, circuit recovery and drift repair after runtime injury.','L2',false,'{}'::jsonb),
('resource_metabolism','metabolism','Allocate scarce budget to maintenance first, bounded execution second, exploration last, keeping reserve.','L2',false,'{"maintenanceFirst":true}'::jsonb),
('constitutional_membrane','cell membrane/organism boundary','Keep rights, consent, secrets, payment, contract and irreversible-action authority outside evolutionary mutation.','L0',true,'{"evolvable":false}'::jsonb)
on conflict(mechanism_key) do update set
  biological_source=excluded.biological_source,operational_mapping=excluded.operational_mapping,
  max_autonomy=excluded.max_autonomy,constitutional=excluded.constitutional,config=excluded.config,updated_at=now();

create table if not exists public.ecology_niches_v9 (
  niche_key text primary key,
  display_name text not null,
  carrying_capacity numeric not null default 1 check (carrying_capacity>=0),
  resource_level numeric not null default 0.5 check (resource_level between 0 and 1),
  demand numeric not null default 0.5 check (demand between 0 and 1),
  competition numeric not null default 0.5 check (competition between 0 and 1),
  volatility numeric not null default 0.5 check (volatility between 0 and 1),
  evidence_scarcity numeric not null default 0.5 check (evidence_scarcity between 0 and 1),
  failure_pressure numeric not null default 0 check (failure_pressure between 0 and 1),
  selection_pressure numeric not null default 0.5 check (selection_pressure between 0 and 1),
  state text not null default 'active' check (state in ('active','scarce','volatile','hibernating','retired')),
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.ecology_organisms_v9 (
  id uuid primary key default gen_random_uuid(),
  organism_key text not null unique,
  organism_type text not null check (organism_type in ('genome','agent','strategy','product','workflow')),
  source_ref text,
  niche_key text not null references public.ecology_niches_v9(niche_key) on delete restrict,
  lineage_key text not null,
  generation integer not null default 1 check (generation>=0),
  parent_refs jsonb not null default '[]'::jsonb,
  genome jsonb not null default '{}'::jsonb,
  phenotype jsonb not null default '{}'::jsonb,
  epigenome jsonb not null default '{}'::jsonb,
  telomere numeric not null default 1 check (telomere between 0 and 1),
  energy numeric not null default 0.5 check (energy between 0 and 1),
  fitness numeric not null default 0 check (fitness between 0 and 1),
  confidence numeric not null default 0 check (confidence between 0 and 1),
  novelty numeric not null default 0.5 check (novelty between 0 and 1),
  stress numeric not null default 0 check (stress between 0 and 1),
  dormancy numeric not null default 0 check (dormancy between 0 and 1),
  status text not null default 'experimental' check (status in ('experimental','active','champion','senescent','hibernating','archived','blocked')),
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ecology_organisms_niche_idx on public.ecology_organisms_v9(niche_key,status,fitness desc,confidence desc);
create index if not exists ecology_organisms_lineage_idx on public.ecology_organisms_v9(lineage_key,generation);

create table if not exists public.ecology_trails_v9 (
  id uuid primary key default gen_random_uuid(),
  trail_key text not null unique,
  from_ref text not null,
  to_ref text not null,
  niche_key text references public.ecology_niches_v9(niche_key) on delete set null,
  nutrient numeric not null default 0.5 check (nutrient between 0 and 1),
  pheromone numeric not null default 0.5 check (pheromone between 0 and 1),
  friction numeric not null default 0 check (friction>=0),
  risk numeric not null default 0 check (risk between 0 and 1),
  capacity numeric not null default 1 check (capacity>=0),
  verified_reinforcements integer not null default 0,
  verified_failures integer not null default 0,
  last_reinforced_at timestamptz,
  last_evaporated_at timestamptz,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.ecology_interactions_v9 (
  id uuid primary key default gen_random_uuid(),
  interaction_key text not null unique,
  organism_a text not null,
  organism_b text not null,
  interaction_type text not null check (interaction_type in ('symbiosis','competition','predation_challenge','cooperation','quorum','recombination')),
  score numeric check (score is null or score between 0 and 1),
  outcome text check (outcome is null or outcome in ('beneficial','neutral','harmful','blocked','unknown')),
  verified boolean not null default false,
  evidence_refs jsonb not null default '[]'::jsonb,
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists public.ecology_immune_memory_v9 (
  signature text primary key,
  observations integer not null default 0,
  failures integer not null default 0,
  severity numeric not null default 0 check (severity between 0 and 1),
  disposition text not null default 'challenge' check (disposition in ('allow','challenge','block')),
  last_seen_at timestamptz,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.ecology_red_queen_v9 (
  id uuid primary key default gen_random_uuid(),
  niche_key text not null references public.ecology_niches_v9(niche_key) on delete restrict,
  organism_key text,
  competition_pressure numeric not null default 0 check (competition_pressure between 0 and 1),
  volatility_pressure numeric not null default 0 check (volatility_pressure between 0 and 1),
  novelty_deficit numeric not null default 0 check (novelty_deficit between 0 and 1),
  failure_pressure numeric not null default 0 check (failure_pressure between 0 and 1),
  mutation_pressure numeric not null default 0 check (mutation_pressure between 0 and 1),
  evidence_refs jsonb not null default '[]'::jsonb,
  observed_at timestamptz not null default now()
);
create index if not exists ecology_red_queen_niche_idx on public.ecology_red_queen_v9(niche_key,observed_at desc);

create table if not exists public.ecology_resource_pools_v9 (
  pool_key text primary key,
  available numeric not null default 0 check (available>=0),
  maintenance_reserve numeric not null default 0 check (maintenance_reserve>=0),
  execution_reserve numeric not null default 0 check (execution_reserve>=0),
  exploration_reserve numeric not null default 0 check (exploration_reserve>=0),
  unit text not null default 'attention',
  evidence_refs jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.ecology_cycles_v9 (
  id uuid primary key default gen_random_uuid(),
  cycle_key text not null unique,
  correlation_id uuid not null default gen_random_uuid(),
  runtime_id text not null,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null default 'running' check (status in ('running','healthy','degraded','blocked','failed')),
  population_count integer not null default 0,
  active_niches integer not null default 0,
  senescent_count integer not null default 0,
  hibernating_count integer not null default 0,
  archived_count integer not null default 0,
  champion_count integer not null default 0,
  mean_telomere numeric,
  mean_energy numeric,
  mean_fitness numeric,
  red_queen_pressure numeric,
  wound_healing_priority numeric,
  homeostasis jsonb not null default '{}'::jsonb,
  routing jsonb not null default '[]'::jsonb,
  quorum jsonb not null default '{}'::jsonb,
  immune_state jsonb not null default '{}'::jsonb,
  actions jsonb not null default '[]'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  receipt_ref text,
  error jsonb
);
create index if not exists ecology_cycles_started_idx on public.ecology_cycles_v9(started_at desc);

alter table public.bio_mechanism_registry_v9 enable row level security;
alter table public.ecology_niches_v9 enable row level security;
alter table public.ecology_organisms_v9 enable row level security;
alter table public.ecology_trails_v9 enable row level security;
alter table public.ecology_interactions_v9 enable row level security;
alter table public.ecology_immune_memory_v9 enable row level security;
alter table public.ecology_red_queen_v9 enable row level security;
alter table public.ecology_resource_pools_v9 enable row level security;
alter table public.ecology_cycles_v9 enable row level security;

insert into public.ecology_niches_v9(niche_key,display_name)
values
('commercial','Commercial Systems'),('market-intelligence','Market Intelligence'),('funding','Funding'),
('tectum','Tectum Real Estate'),('reports','Report Factory'),('research','Research'),('product-factory','Product Factory'),
('runtime','Runtime & Automation'),('counterparty','Counterparty Intelligence'),('marketing','Marketing')
on conflict(niche_key) do nothing;

create or replace view public.v_bioecology_dashboard_v9 with (security_invoker=on) as
select
  now() as observed_at,
  (select count(*) from public.bio_mechanism_registry_v9 where enabled=true) as enabled_mechanisms,
  (select count(*) from public.ecology_niches_v9 where state<>'retired') as active_niches,
  (select count(*) from public.ecology_organisms_v9 where status not in ('archived','blocked')) as active_population,
  (select count(*) from public.ecology_organisms_v9 where status='champion') as champions,
  (select count(*) from public.ecology_organisms_v9 where status='senescent') as senescent,
  (select count(*) from public.ecology_organisms_v9 where status='hibernating') as hibernating,
  (select count(*) from public.ecology_immune_memory_v9 where disposition='block') as blocked_signatures,
  (select count(*) from public.ecology_immune_memory_v9 where disposition='challenge') as challenged_signatures,
  (select coalesce(avg(telomere),0) from public.ecology_organisms_v9 where status<>'archived') as mean_telomere,
  (select coalesce(avg(energy),0) from public.ecology_organisms_v9 where status<>'archived') as mean_energy,
  (select coalesce(avg(fitness),0) from public.ecology_organisms_v9 where status<>'archived') as mean_fitness,
  (select coalesce(avg(mutation_pressure),0) from public.ecology_red_queen_v9 where observed_at>=now()-interval '7 days') as recent_red_queen_pressure,
  (select count(*) from public.ecology_trails_v9 where pheromone>=0.6) as reinforced_routes,
  (select count(*) from public.ecology_interactions_v9 where verified=true and outcome='beneficial') as verified_beneficial_interactions;

insert into public.job_definitions(
  job_key,name,description,trigger_type,schedule_expr,timezone,event_topic,handler_key,owner_agent_slug,
  autonomy_level,policy_key,required_connectors,input_template,enabled,max_runtime_seconds,lease_seconds,
  max_attempts,backoff_seconds,concurrency_limit
) values(
  'bioecology-cycle-v9','Kairon bioecology cycle',
  'Observe population/ecology state, refresh bounded evolutionary pressures, homeostasis, routing, immune and recovery recommendations. No constitutional or L3 authority is evolvable.',
  'cron','*/30 * * * *','Europe/Madrid',null,'evolution.bioecology_cycle','evolution','L2','internal-runtime-v9',
  '[]'::jsonb,'{"source":"kairon-bioecology"}'::jsonb,true,180,180,3,60,1
)
on conflict(job_key) do update set
  name=excluded.name,description=excluded.description,trigger_type=excluded.trigger_type,schedule_expr=excluded.schedule_expr,
  timezone=excluded.timezone,handler_key=excluded.handler_key,owner_agent_slug=excluded.owner_agent_slug,
  autonomy_level=excluded.autonomy_level,policy_key=excluded.policy_key,required_connectors=excluded.required_connectors,
  input_template=excluded.input_template,enabled=excluded.enabled,max_runtime_seconds=excluded.max_runtime_seconds,
  lease_seconds=excluded.lease_seconds,max_attempts=excluded.max_attempts,backoff_seconds=excluded.backoff_seconds,
  concurrency_limit=excluded.concurrency_limit,updated_at=now();

insert into public.desired_runtime_state_v4(kind,state_key,desired,auto_remediate,source_ref,active)
values(
  'job','bioecology-cycle-v9',
  '{"enabled":true,"handler_key":"evolution.bioecology_cycle","autonomy_level":"L2"}'::jsonb,
  true,'db/migrations/018_v9_conway_bioecology.sql',true
)
on conflict(kind,state_key) do update set
  desired=excluded.desired,auto_remediate=excluded.auto_remediate,source_ref=excluded.source_ref,active=true,updated_at=now();
