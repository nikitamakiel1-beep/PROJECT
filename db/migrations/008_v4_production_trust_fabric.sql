-- Creixement v4 production trust fabric.
-- Signed service metadata, replay protection, capability contracts, lineage, retention,
-- desired-state reconciliation and reproducible release manifests.

create table if not exists public.service_identity_keys_v4 (
  id uuid primary key default gen_random_uuid(),
  service_key text not null,
  key_id text not null,
  algorithm text not null default 'hmac-sha256',
  public_fingerprint text,
  status text not null default 'active' check (status in ('active','retiring','revoked','expired')),
  not_before timestamptz not null default now(),
  expires_at timestamptz,
  rotated_from_key_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(service_key,key_id)
);

create table if not exists public.request_nonces_v4 (
  service_key text not null,
  nonce text not null,
  correlation_id text,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  primary key(service_key,nonce)
);
create index if not exists request_nonces_v4_expiry_idx on public.request_nonces_v4(expires_at);

create or replace function public.creixement_register_nonce_v4(
  p_service_key text,
  p_nonce text,
  p_correlation_id text,
  p_expires_at timestamptz
) returns boolean
language plpgsql
security definer
set search_path=public
as $$
begin
  delete from public.request_nonces_v4 where expires_at <= now();
  insert into public.request_nonces_v4(service_key,nonce,correlation_id,expires_at)
  values(p_service_key,p_nonce,p_correlation_id,p_expires_at)
  on conflict(service_key,nonce) do nothing;
  return found;
end;
$$;

create table if not exists public.capability_contracts_v4 (
  id uuid primary key default gen_random_uuid(),
  capability_key text not null,
  version text not null,
  description text not null,
  input_schema_ref text not null,
  output_schema_ref text not null,
  required_evidence_kinds jsonb not null default '[]'::jsonb,
  required_rights jsonb not null default '[]'::jsonb,
  max_autonomy text not null check (max_autonomy in ('L0','L1','L2','L3')),
  reversible boolean not null,
  receipt_required boolean not null default true,
  idempotency_required boolean not null default true,
  max_external_cost_eur numeric not null default 0 check (max_external_cost_eur >= 0),
  allowed_providers jsonb not null default '[]'::jsonb,
  forbidden_effects jsonb not null default '[]'::jsonb,
  active boolean not null default true,
  source_ref text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(capability_key,version)
);

create table if not exists public.lineage_nodes_v4 (
  id uuid primary key default gen_random_uuid(),
  node_key text not null unique,
  kind text not null check (kind in ('source','normalized','analysis','action','receipt','deliverable','outcome')),
  content_digest text not null check (content_digest ~ '^[0-9A-Fa-f]{64}$'),
  source_ref text,
  truth_level text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.lineage_edges_v4 (
  id uuid primary key default gen_random_uuid(),
  parent_node_id uuid not null references public.lineage_nodes_v4(id) on delete restrict,
  child_node_id uuid not null references public.lineage_nodes_v4(id) on delete restrict,
  relation text not null check (relation in ('derived_from','executed_as','verified_by','rendered_as','supersedes')),
  created_at timestamptz not null default now(),
  unique(parent_node_id,child_node_id,relation),
  check (parent_node_id <> child_node_id)
);
create index if not exists lineage_edges_v4_parent_idx on public.lineage_edges_v4(parent_node_id);
create index if not exists lineage_edges_v4_child_idx on public.lineage_edges_v4(child_node_id);

create table if not exists public.retention_policies_v4 (
  id uuid primary key default gen_random_uuid(),
  classification text not null unique check (classification in ('ephemeral','operational','commercial','financial','legal','evidence')),
  retain_days integer check (retain_days is null or retain_days >= 0),
  archive_after_days integer check (archive_after_days is null or archive_after_days >= 0),
  delete_allowed boolean not null default false,
  require_approval_for_deletion boolean not null default true,
  source_ref text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.retention_holds_v4 (
  id uuid primary key default gen_random_uuid(),
  record_ref text not null,
  reason text not null,
  source_ref text,
  active boolean not null default true,
  placed_by text not null,
  placed_at timestamptz not null default now(),
  released_by text,
  released_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists retention_holds_v4_record_idx on public.retention_holds_v4(record_ref,active);

create table if not exists public.retention_actions_v4 (
  id uuid primary key default gen_random_uuid(),
  record_ref text not null,
  classification text not null,
  proposed_action text not null check (proposed_action in ('keep','archive','delete_candidate','hold')),
  status text not null default 'proposed' check (status in ('proposed','approved','executed','rejected','cancelled')),
  requires_approval boolean not null default false,
  reason text not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  executed_receipt_ref text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.desired_runtime_state_v4 (
  id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('connector','job','agent','policy','service','release')),
  state_key text not null,
  desired jsonb not null,
  auto_remediate boolean not null default false,
  source_ref text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(kind,state_key)
);

create table if not exists public.observed_runtime_state_v4 (
  id uuid primary key default gen_random_uuid(),
  kind text not null,
  state_key text not null,
  observed jsonb not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(kind,state_key)
);

create table if not exists public.runtime_drift_findings_v4 (
  id uuid primary key default gen_random_uuid(),
  kind text not null,
  state_key text not null,
  field text not null,
  desired jsonb,
  observed jsonb,
  severity text not null check (severity in ('info','warning','critical')),
  remediation text not null check (remediation in ('none','automatic','approval_required')),
  status text not null default 'open' check (status in ('open','remediating','resolved','accepted','blocked')),
  evidence_refs jsonb not null default '[]'::jsonb,
  detected_at timestamptz not null default now(),
  resolved_at timestamptz,
  unique(kind,state_key,field,status)
);
create index if not exists runtime_drift_findings_v4_open_idx on public.runtime_drift_findings_v4(status,severity,detected_at desc);

create table if not exists public.release_manifests_v4 (
  id uuid primary key default gen_random_uuid(),
  release_id text not null unique,
  branch text not null,
  commit_sha text not null,
  manifest_digest text not null unique check (manifest_digest ~ '^[0-9A-Fa-f]{64}$'),
  migration_head text not null,
  constitution_version text not null,
  scheduler_version text not null,
  components jsonb not null default '[]'::jsonb,
  status text not null default 'candidate' check (status in ('candidate','verified','promoted','rejected','rolled_back')),
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  promoted_at timestamptz
);
create index if not exists release_manifests_v4_status_idx on public.release_manifests_v4(status,created_at desc);

create table if not exists public.release_manifest_components_v4 (
  id uuid primary key default gen_random_uuid(),
  release_manifest_id uuid not null references public.release_manifests_v4(id) on delete cascade,
  component_key text not null,
  component_version text not null,
  digest text not null check (digest ~ '^[0-9A-Fa-f]{64}$'),
  kind text not null check (kind in ('code','migration','config','schema','prompt','template','model')),
  created_at timestamptz not null default now(),
  unique(release_manifest_id,component_key)
);

alter table public.service_identity_keys_v4 enable row level security;
alter table public.request_nonces_v4 enable row level security;
alter table public.capability_contracts_v4 enable row level security;
alter table public.lineage_nodes_v4 enable row level security;
alter table public.lineage_edges_v4 enable row level security;
alter table public.retention_policies_v4 enable row level security;
alter table public.retention_holds_v4 enable row level security;
alter table public.retention_actions_v4 enable row level security;
alter table public.desired_runtime_state_v4 enable row level security;
alter table public.observed_runtime_state_v4 enable row level security;
alter table public.runtime_drift_findings_v4 enable row level security;
alter table public.release_manifests_v4 enable row level security;
alter table public.release_manifest_components_v4 enable row level security;

drop trigger if exists service_identity_keys_v4_set_updated_at on public.service_identity_keys_v4;
create trigger service_identity_keys_v4_set_updated_at before update on public.service_identity_keys_v4 for each row execute function public.creixement_set_updated_at();
drop trigger if exists capability_contracts_v4_set_updated_at on public.capability_contracts_v4;
create trigger capability_contracts_v4_set_updated_at before update on public.capability_contracts_v4 for each row execute function public.creixement_set_updated_at();
drop trigger if exists retention_policies_v4_set_updated_at on public.retention_policies_v4;
create trigger retention_policies_v4_set_updated_at before update on public.retention_policies_v4 for each row execute function public.creixement_set_updated_at();
drop trigger if exists retention_actions_v4_set_updated_at on public.retention_actions_v4;
create trigger retention_actions_v4_set_updated_at before update on public.retention_actions_v4 for each row execute function public.creixement_set_updated_at();
drop trigger if exists desired_runtime_state_v4_set_updated_at on public.desired_runtime_state_v4;
create trigger desired_runtime_state_v4_set_updated_at before update on public.desired_runtime_state_v4 for each row execute function public.creixement_set_updated_at();

insert into public.retention_policies_v4(classification,retain_days,archive_after_days,delete_allowed,require_approval_for_deletion,source_ref)
values
('ephemeral',7,2,true,false,'v4-default-retention'),
('operational',90,30,true,true,'v4-default-retention'),
('commercial',null,365,false,true,'explicit-policy-required'),
('financial',null,365,false,true,'explicit-policy-required'),
('legal',null,null,false,true,'explicit-policy-required'),
('evidence',null,365,false,true,'governed-evidence-default')
on conflict(classification) do update set retain_days=excluded.retain_days,archive_after_days=excluded.archive_after_days,delete_allowed=excluded.delete_allowed,require_approval_for_deletion=excluded.require_approval_for_deletion,source_ref=excluded.source_ref,updated_at=now();

insert into public.capability_contracts_v4(capability_key,version,description,input_schema_ref,output_schema_ref,required_evidence_kinds,required_rights,max_autonomy,reversible,receipt_required,idempotency_required,max_external_cost_eur,allowed_providers,forbidden_effects,active,source_ref)
values
('opportunity.score','4.0.0','Score a structured opportunity from governed evidence.','schema:opportunity-input:v4','schema:opportunity-score:v4','["governed_source"]'::jsonb,'["read"]'::jsonb,'L2',true,true,true,0,'["internal"]'::jsonb,'["external_send","payment","property_commitment"]'::jsonb,true,'v4-core'),
('report.draft','4.0.0','Draft a report from approved evidence without releasing it.','schema:report-input:v4','schema:report-draft:v4','["governed_source"]'::jsonb,'["read"]'::jsonb,'L2',true,true,true,0,'["internal"]'::jsonb,'["client_release","public_publish"]'::jsonb,true,'v4-core'),
('crm.reversible_write','4.0.0','Perform an idempotent reversible internal CRM write.','schema:crm-write:v4','schema:connector-receipt:v4','[]'::jsonb,'["write"]'::jsonb,'L2',true,true,true,0,'["google-sheets-crm"]'::jsonb,'["external_send","destructive_delete"]'::jsonb,true,'v4-core'),
('genome.evolve','4.0.0','Run bounded commercial evolution from verified observations.','schema:genome-input:v4','schema:evolution-event:v4','["verified_outcome"]'::jsonb,'["internal"]'::jsonb,'L2',true,true,true,0,'["internal"]'::jsonb,'["mutate_constitution","spend_money","external_send"]'::jsonb,true,'v4-core')
on conflict(capability_key,version) do update set description=excluded.description,input_schema_ref=excluded.input_schema_ref,output_schema_ref=excluded.output_schema_ref,required_evidence_kinds=excluded.required_evidence_kinds,required_rights=excluded.required_rights,max_autonomy=excluded.max_autonomy,reversible=excluded.reversible,receipt_required=excluded.receipt_required,idempotency_required=excluded.idempotency_required,max_external_cost_eur=excluded.max_external_cost_eur,allowed_providers=excluded.allowed_providers,forbidden_effects=excluded.forbidden_effects,active=excluded.active,source_ref=excluded.source_ref,updated_at=now();

create or replace view public.v_runtime_drift_summary_v4 as
select severity,status,count(*) as findings,min(detected_at) as oldest_detected_at,max(detected_at) as newest_detected_at
from public.runtime_drift_findings_v4
group by severity,status;

create or replace view public.v_release_manifest_status_v4 as
select release_id,branch,commit_sha,manifest_digest,migration_head,constitution_version,scheduler_version,status,
       jsonb_array_length(components) as component_count,created_at,promoted_at
from public.release_manifests_v4
order by created_at desc;
