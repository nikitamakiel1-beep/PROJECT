-- Creixement v9 — Conway adversarial courts, hysteresis and canary promotion.
-- Apply after 018_v9_conway_bioecology.sql.

create table if not exists public.authority_graph_v9 (
  node_key text primary key,
  action_class text not null,
  max_autonomy text not null check (max_autonomy in ('L0','L1','L2','L3')),
  forbidden boolean not null default false,
  next_nodes jsonb not null default '[]'::jsonb,
  source_ref text,
  digest text,
  updated_at timestamptz not null default now()
);

create table if not exists public.adversarial_court_runs_v9 (
  id uuid primary key default gen_random_uuid(),
  court_key text not null unique,
  court_type text not null check (court_type in ('slime_path_exploration','faustian_fuzz','authority_traversal','auditor_of_auditors','mutation_detection')),
  seed text not null,
  explored_states integer not null default 0,
  forbidden_hits integer not null default 0,
  safe_terminal_states integer not null default 0,
  hard_veto_count integer not null default 0,
  baseline_digest text,
  candidate_digest text,
  passed boolean not null default false,
  findings jsonb not null default '[]'::jsonb,
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.capability_canaries_v9 (
  id uuid primary key default gen_random_uuid(),
  capability_key text not null,
  version text not null,
  canary_key text not null unique,
  passed boolean not null default false,
  receipted boolean not null default false,
  deterministic_replay boolean not null default false,
  digest_match boolean not null default false,
  receipt_ref text,
  evidence_refs jsonb not null default '[]'::jsonb,
  observed_at timestamptz not null default now()
);
create index if not exists capability_canaries_v9_capability_idx on public.capability_canaries_v9(capability_key,version,observed_at desc);

create table if not exists public.hysteresis_states_v9 (
  state_key text primary key,
  state text not null check (state in ('off','candidate','on','degrading')),
  score numeric not null default 0,
  enter_threshold numeric not null default 0.7,
  exit_threshold numeric not null default 0.4,
  dwell_enter integer not null default 2,
  dwell_exit integer not null default 2,
  consecutive_above integer not null default 0,
  consecutive_below integer not null default 0,
  evidence_refs jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  check (exit_threshold<=enter_threshold)
);

create table if not exists public.public_projection_manifests_v9 (
  projection_key text primary key,
  stable_payload jsonb not null,
  digest text not null,
  volatile_fields_removed jsonb not null default '[]'::jsonb,
  source_ref text,
  verified boolean not null default false,
  updated_at timestamptz not null default now()
);

alter table public.authority_graph_v9 enable row level security;
alter table public.adversarial_court_runs_v9 enable row level security;
alter table public.capability_canaries_v9 enable row level security;
alter table public.hysteresis_states_v9 enable row level security;
alter table public.public_projection_manifests_v9 enable row level security;

create or replace view public.v_conway_court_status_v9 with (security_invoker=on) as
select
  now() as observed_at,
  (select count(*) from public.adversarial_court_runs_v9) as total_courts,
  (select count(*) from public.adversarial_court_runs_v9 where passed=true) as passed_courts,
  (select count(*) from public.adversarial_court_runs_v9 where passed=false) as failed_courts,
  (select coalesce(sum(explored_states),0) from public.adversarial_court_runs_v9) as explored_states,
  (select coalesce(sum(forbidden_hits),0) from public.adversarial_court_runs_v9) as forbidden_hits,
  (select count(*) from public.capability_canaries_v9 where passed and receipted and deterministic_replay and digest_match) as verified_canaries,
  (select count(*) from public.hysteresis_states_v9 where state='on') as stable_on_states,
  (select count(*) from public.hysteresis_states_v9 where state in ('candidate','degrading')) as transitional_states;

insert into public.bio_mechanism_registry_v9(mechanism_key,biological_source,operational_mapping,max_autonomy,constitutional,config)
values
('dwell_hysteresis','neural/endocrine persistence','Require sustained evidence before state transitions and sustained degradation before rollback.','L2',false,'{"enter":0.7,"exit":0.4,"dwellEnter":2,"dwellExit":2}'::jsonb),
('faustian_adversarial_court','predator/prey adversarial testing','Fuzz seductive high-value paths and require hard-veto dominance over value maximization.','L1',true,'{"hardVetoDominates":true}'::jsonb),
('authority_graph_traversal','territorial boundary graph','Exhaustively traverse reachable authority paths and surface forbidden L3 edges.','L1',true,'{"maxPaths":200000}'::jsonb),
('auditor_of_auditors','immune meta-surveillance','Digest-bind auditors and detect mutation/drift in the auditor itself.','L1',true,'{"digestBound":true}'::jsonb),
('canary_promotion','sentinel organisms','Promote evolved capabilities only after receipted deterministic canary evidence.','L2',true,'{"minRuns":5,"passRate":1}'::jsonb),
('deterministic_projection','stable phenotype projection','Keep public capability identity deterministic and exclude volatile telemetry/timestamps.','L1',true,'{"volatileTelemetryForbidden":true}'::jsonb)
on conflict(mechanism_key) do update set operational_mapping=excluded.operational_mapping,max_autonomy=excluded.max_autonomy,constitutional=excluded.constitutional,config=excluded.config,updated_at=now();
