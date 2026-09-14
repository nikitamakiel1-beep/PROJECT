-- Creixement v9 — materialized ecological population + executable Conway courts.
-- Apply after 019_v9_conway_adversarial_courts.sql.

create or replace function public.creixement_sync_commercial_genomes_v9()
returns table(inserted_or_updated integer, active_population integer)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count integer := 0;
begin
  insert into public.ecology_niches_v9(niche_key,display_name,state)
  select distinct g.niche, initcap(replace(g.niche,'-',' ')), 'active'
  from public.commercial_genomes g
  where g.niche is not null and length(trim(g.niche)) > 0
  on conflict(niche_key) do nothing;

  insert into public.ecology_organisms_v9(
    organism_key,organism_type,source_ref,niche_key,lineage_key,generation,parent_refs,
    genome,phenotype,epigenome,telomere,energy,fitness,confidence,novelty,stress,dormancy,status,evidence_refs,updated_at
  )
  select
    'commercial-genome:'||g.id::text,
    'genome',
    'commercial_genomes:'||g.id::text,
    g.niche,
    g.lineage_id::text,
    greatest(g.generation,0),
    coalesce(g.parent_ids,'[]'::jsonb),
    coalesce(g.genes,'{}'::jsonb),
    jsonb_build_object(
      'variantName',g.variant_name,
      'modelVersion',g.model_version,
      'verifiedObservations',g.verified_observations,
      'verifiedSuccesses',g.verified_successes,
      'paidSuccesses',g.paid_successes,
      'commercialStatus',g.status
    ),
    '{}'::jsonb,
    least(1,greatest(0,coalesce(g.telomere,1))),
    least(1,greatest(0,coalesce(g.exploration_budget,0.5))),
    least(1,greatest(0,coalesce(g.fitness,0))),
    least(1,greatest(0,coalesce(g.confidence,0))),
    least(1,greatest(0,1-(least(g.generation,20)::numeric/20))),
    least(1,greatest(0,1-coalesce(g.telomere,1))),
    case when g.status='senescent' then 0.45 else 0 end,
    case
      when g.status='archived' then 'archived'
      when g.status='blocked' then 'blocked'
      when g.status='champion' then 'champion'
      when g.status='senescent' then 'senescent'
      when g.status='active' then 'active'
      else 'experimental'
    end,
    jsonb_build_array('commercial_genomes:'||g.id::text),
    now()
  from public.commercial_genomes g
  on conflict(organism_key) do update set
    niche_key=excluded.niche_key,
    lineage_key=excluded.lineage_key,
    generation=excluded.generation,
    parent_refs=excluded.parent_refs,
    genome=excluded.genome,
    phenotype=excluded.phenotype,
    telomere=excluded.telomere,
    energy=excluded.energy,
    fitness=excluded.fitness,
    confidence=excluded.confidence,
    novelty=excluded.novelty,
    stress=excluded.stress,
    dormancy=excluded.dormancy,
    status=excluded.status,
    evidence_refs=excluded.evidence_refs,
    updated_at=now();

  get diagnostics v_count = row_count;

  return query
  select v_count,
         count(*)::integer
  from public.ecology_organisms_v9
  where status not in ('archived','blocked');
end;
$$;

revoke all on function public.creixement_sync_commercial_genomes_v9() from public;
revoke all on function public.creixement_sync_commercial_genomes_v9() from anon;
revoke all on function public.creixement_sync_commercial_genomes_v9() from authenticated;
grant execute on function public.creixement_sync_commercial_genomes_v9() to service_role;

insert into public.authority_graph_v9(node_key,action_class,max_autonomy,forbidden,next_nodes,source_ref)
values
('root','sense_and_decide','L0',false,'["research","internal-write","external-boundary"]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('research','research','L1',false,'["draft","internal-write"]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('draft','draft_asset','L1',false,'[]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('internal-write','internal_reversible_write','L2',false,'[]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('external-boundary','external_effect_boundary','L1',false,'["external-message","publication","payment","contract","property","financing","irreversible-delete"]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('external-message','external_message','L3',true,'[]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('publication','public_publication','L3',true,'[]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('payment','payment_authority','L3',true,'[]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('contract','contract_authority','L3',true,'[]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('property','property_commitment_authority','L3',true,'[]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('financing','financing_commitment_authority','L3',true,'[]'::jsonb,'020_v9_population_and_courts_runtime.sql'),
('irreversible-delete','irreversible_governed_deletion','L3',true,'[]'::jsonb,'020_v9_population_and_courts_runtime.sql')
on conflict(node_key) do update set
  action_class=excluded.action_class,
  max_autonomy=excluded.max_autonomy,
  forbidden=excluded.forbidden,
  next_nodes=excluded.next_nodes,
  source_ref=excluded.source_ref,
  updated_at=now();

insert into public.job_definitions(
  job_key,name,description,trigger_type,schedule_expr,timezone,event_topic,handler_key,owner_agent_slug,
  autonomy_level,policy_key,required_connectors,enabled,max_runtime_seconds,max_attempts,concurrency_limit
)
values(
  'conway-courts-v9','Conway adversarial courts V9',
  'Runs deterministic authority traversal, Faustian hard-veto checks, auditor mutation checks and canary promotion verification.',
  'cron','17 * * * *','Europe/Madrid',null,'evolution.conway_courts','evolution-agent',
  'L1','internal-runtime-v9','[]'::jsonb,true,60,3,1
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
  'conway-courts-v9','job',
  '{"enabled":true,"handler_key":"evolution.conway_courts","autonomy_level":"L1","schedule":"17 * * * *"}'::jsonb,
  'db/migrations/020_v9_population_and_courts_runtime.sql',true
)
on conflict(kind,state_key) do update set desired=excluded.desired,source_ref=excluded.source_ref,active=true,updated_at=now();

select * from public.creixement_sync_commercial_genomes_v9();
