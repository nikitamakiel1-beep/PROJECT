-- Creixement v4 initial operating backlog.
-- Truthful seed only: connector/provider rows reflect configured state, never synthetic execution.

-- Mirror current connector declarations into provider registry.
insert into public.provider_registry(provider_key,name,provider_type,runtime_state,rights_status,operations,data_classification,estimated_cost_eur,reliability,evidence_quality,freshness,receipt_support,idempotent_writes,required_secrets,circuit_breaker_key,owner,last_error)
select
  'connector:'||c.slug,
  c.name,
  case
    when c.slug='tectum-cloud-underwriting' then 'underwriting'
    when c.slug='tectum-cloud-renderer' then 'renderer'
    when c.slug='clay' then 'enrichment'
    when c.slug in ('funding-feeds','market-data') then 'data_feed'
    when c.slug='analytics' then 'analytics'
    else 'connector'
  end,
  case
    when c.state='disabled' then 'disabled'
    when c.runtime_connection in ('chat_connector_available_runtime_not_wired','available_not_wired','provider_setup_required','contracts_and_provider_access_required','project_created_build_blocked_by_credits','cloud_service_not_deployed','optional_migration_not_configured','future') then 'not_configured'
    when c.state='degraded' then 'degraded'
    when c.state='connected' then 'configured'
    else 'not_configured'
  end,
  case when c.slug in ('google-drive','google-sheets-crm','github','linear','gmail','google-calendar','google-contacts','lovable') then 'permitted' else 'unknown' end,
  coalesce(c.scopes,'[]'::jsonb),
  coalesce(c.data_classification,'internal'),
  0,
  0,
  0,
  0,
  false,
  coalesce(c.can_write,false),
  coalesce(c.required_secrets,'[]'::jsonb),
  'connector:'||c.slug,
  coalesce(c.owner,'Creixement Runtime'),
  case when c.last_error is null then null else jsonb_build_object('message',c.last_error) end
from public.connectors c
on conflict(provider_key) do update set
  name=excluded.name,provider_type=excluded.provider_type,runtime_state=excluded.runtime_state,rights_status=excluded.rights_status,
  operations=excluded.operations,data_classification=excluded.data_classification,required_secrets=excluded.required_secrets,
  circuit_breaker_key=excluded.circuit_breaker_key,owner=excluded.owner,last_error=excluded.last_error,updated_at=now();

-- Internal deterministic capabilities exist as code/config, not as externally executed services yet.
insert into public.provider_registry(provider_key,name,provider_type,runtime_state,rights_status,operations,data_classification,estimated_cost_eur,reliability,evidence_quality,freshness,receipt_support,idempotent_writes,owner)
values
('internal:opportunity-engine','Creixement Opportunity Engine','internal_service','configured','permitted','["opportunity.score","opportunity.decide"]'::jsonb,'internal',0,1,1,1,true,true,'Creixement'),
('internal:goal-engine','Creixement Goal DAG Engine','internal_service','configured','permitted','["goals.validate","goals.rank"]'::jsonb,'internal',0,1,1,1,true,true,'Creixement'),
('internal:policy-engine','Creixement Policy Engine','internal_service','configured','permitted','["policy.decide","budget.enforce"]'::jsonb,'restricted',0,1,1,1,true,true,'Creixement'),
('internal:evolution-engine','Creixement Evolution Engine','internal_service','configured','permitted','["genomes.score","genomes.mutate","genomes.select"]'::jsonb,'internal',0,1,1,1,true,true,'Creixement'),
('internal:memory-engine','Creixement Provenance Memory','internal_service','configured','permitted','["memory.rank","memory.resolve"]'::jsonb,'restricted',0,1,1,1,true,true,'Creixement')
on conflict(provider_key) do update set runtime_state=excluded.runtime_state,rights_status=excluded.rights_status,operations=excluded.operations,reliability=excluded.reliability,evidence_quality=excluded.evidence_quality,freshness=excluded.freshness,receipt_support=excluded.receipt_support,idempotent_writes=excluded.idempotent_writes,updated_at=now();

insert into public.capability_registry(capability_key,name,capability_type,maturity,execution_contract,evidence_requirements,required_truth_level,source_ref)
values
('opportunity-score','Opportunity Scoring','automation','validated','{"operation":"opportunity.score","deterministic":true}'::jsonb,'["structured_signal"]'::jsonb,'evidence_backed_model_inference','cloud/creixement-agent-core/src/scoring.ts'),
('goal-prioritize','Goal DAG Prioritization','automation','validated','{"operation":"goals.rank","acyclic_required":true}'::jsonb,'["goal_object"]'::jsonb,'human_approved_decision','cloud/creixement-agent-core/src/goals.ts'),
('policy-enforce','Policy & Budget Enforcement','automation','validated','{"operation":"policy.decide","fail_closed":true}'::jsonb,'["authorization_envelope","budget_envelope"]'::jsonb,'human_approved_decision','cloud/creixement-agent-core/src/policy.ts'),
('commercial-evolution','Commercial Genome Evolution','automation','validated','{"operation":"genomes.select","bounded_mutation":true}'::jsonb,'["verified_observations"]'::jsonb,'governed_source_evidence','cloud/creixement-agent-core/src/evolution.ts'),
('provenance-memory','Provenance-aware Memory','automation','validated','{"operation":"memory.rank","truth_hierarchy":true}'::jsonb,'["source_refs","truth_level"]'::jsonb,'governed_source_evidence','cloud/creixement-agent-core/src/memory.ts'),
('drive-records','Google Drive Governed Records','crm','experimental','{"operation":"drive.records"}'::jsonb,'["runtime_connector_receipt"]'::jsonb,'executed_connector_receipt','connector:google-drive'),
('crm-sync','Google Sheets CRM Sync','crm','experimental','{"operation":"crm.sync"}'::jsonb,'["runtime_connector_receipt"]'::jsonb,'executed_connector_receipt','connector:google-sheets-crm'),
('company-enrichment','Company Enrichment','enrichment','experimental','{"operation":"company.enrich"}'::jsonb,'["provider_terms","runtime_connector_receipt"]'::jsonb,'governed_source_evidence','connector:clay'),
('market-research','Market Intelligence Retrieval','market','experimental','{"operation":"market.research"}'::jsonb,'["provider_terms","source_provenance"]'::jsonb,'governed_source_evidence','connector:market-data'),
('funding-research','Funding Feed Retrieval','funding','experimental','{"operation":"funding.refresh"}'::jsonb,'["provider_terms","source_provenance"]'::jsonb,'governed_source_evidence','connector:funding-feeds'),
('tectum-underwriting','Tectum Deterministic Underwriting','underwriting','experimental','{"operation":"underwriting.calculate","cloud_only":true}'::jsonb,'["golden_case_equivalence","calculation_receipt"]'::jsonb,'executed_connector_receipt','connector:tectum-cloud-underwriting'),
('tectum-render','Tectum Cloud Rendering','render','experimental','{"operation":"report.render","digest_bound":true}'::jsonb,'["golden_report_fidelity","render_receipt"]'::jsonb,'executed_connector_receipt','connector:tectum-cloud-renderer')
on conflict(capability_key) do update set name=excluded.name,capability_type=excluded.capability_type,maturity=excluded.maturity,execution_contract=excluded.execution_contract,evidence_requirements=excluded.evidence_requirements,required_truth_level=excluded.required_truth_level,source_ref=excluded.source_ref,updated_at=now();

insert into public.capability_provider_routes(capability_key,provider_key,operation,priority,enabled,max_cost_eur,min_reliability,min_evidence_quality,min_freshness)
values
('opportunity-score','internal:opportunity-engine','opportunity.score',1,true,0,1,1,1),
('goal-prioritize','internal:goal-engine','goals.rank',1,true,0,1,1,1),
('policy-enforce','internal:policy-engine','policy.decide',1,true,0,1,1,1),
('commercial-evolution','internal:evolution-engine','genomes.select',1,true,0,1,1,1),
('provenance-memory','internal:memory-engine','memory.rank',1,true,0,1,1,1),
('drive-records','connector:google-drive','drive.records',10,true,0,0.95,0.9,0.8),
('crm-sync','connector:google-sheets-crm','crm.sync',10,true,0,0.95,0.9,0.8),
('company-enrichment','connector:clay','company.enrich',10,true,0,0.9,0.8,0.8),
('market-research','connector:market-data','market.research',10,true,0,0.9,0.8,0.8),
('funding-research','connector:funding-feeds','funding.refresh',10,true,0,0.9,0.8,0.9),
('tectum-underwriting','connector:tectum-cloud-underwriting','underwriting.calculate',10,true,0,0.99,1,1),
('tectum-render','connector:tectum-cloud-renderer','report.render',10,true,0,0.99,1,1)
on conflict(capability_key,provider_key,operation) do update set priority=excluded.priority,enabled=excluded.enabled,max_cost_eur=excluded.max_cost_eur,min_reliability=excluded.min_reliability,min_evidence_quality=excluded.min_evidence_quality,min_freshness=excluded.min_freshness;

-- Current operating backlog based on verified system blockers.
with m as (select id from public.missions where mission_key='creixement-primary')
insert into public.goals(mission_id,goal_key,goal_class,title,objective,success_condition,owner_agent_slug,status,expected_economic_value,strategic_value,urgency,confidence,reversibility,risk,blocker,required_connectors,required_capabilities,evidence_refs,budget_ref)
select m.id,v.goal_key,v.goal_class,v.title,v.objective,v.success_condition,v.owner_agent_slug,v.status,v.expected_economic_value,v.strategic_value,v.urgency,v.confidence,v.reversibility,v.risk,v.blocker,v.required_connectors,v.required_capabilities,v.evidence_refs,'global-v4-day'
from m cross join (values
('deploy-cloud-runtime','reliability','Deploy Creixement cloud runtime','Create a real managed cloud runtime for scheduler/workers/control-plane API.','A production cloud service can claim and finish a test job with a verified receipt.','automation-engineer','proposed',0,1.0,1.0,0.95,0.8,0.2,'No Vercel project/runtime deployment currently exists.','[]'::jsonb,'["policy-enforce"]'::jsonb,'["verified:vercel-project-list-empty"]'::jsonb),
('wire-drive-crm-runtime','reliability','Wire Drive and CRM runtime OAuth','Authenticate server-side Google Drive and Google Sheets CRM adapters.','A cloud worker completes read syncs for both systems and stores connector_sync receipts.','automation-engineer','blocked',0,1.0,0.95,0.95,0.8,0.2,'Chat connectors exist but production runtime OAuth is not wired.','["google-drive","google-sheets-crm"]'::jsonb,'["drive-records","crm-sync"]'::jsonb,'["verified:connector-state"]'::jsonb),
('complete-lovable-cockpit','product','Complete Lovable Chief Operator cockpit','Build and wire the full private operator UI to live Supabase state.','Required v4 screens query live data and no stale local/backend-absent claims remain.','product-architect','blocked',0,0.9,0.8,0.9,0.9,0.1,'Lovable build remains blocked by workspace credits.','["lovable"]'::jsonb,'[]'::jsonb,'["verified:lovable-credit-blocker"]'::jsonb),
('wire-market-providers','strategic','Wire market and enrichment providers','Connect approved market/company intelligence sources for autonomous opportunity discovery.','At least one lawful provider is runtime-ready with provenance and sync receipts.','market-intelligence','blocked',500,0.9,0.85,0.7,0.8,0.25,'Provider selection/contracts/runtime authentication are not configured.','["market-data","clay"]'::jsonb,'["market-research","company-enrichment"]'::jsonb,'["verified:connector-state"]'::jsonb),
('wire-funding-feed','strategic','Wire funding feed','Connect an approved funding source and automatic freshness checks.','Funding refresh job ingests real calls with provenance and expiry.','funding','blocked',300,0.7,0.6,0.7,0.9,0.15,'Funding provider is not configured.','["funding-feeds"]'::jsonb,'["funding-research"]'::jsonb,'["verified:connector-state"]'::jsonb),
('tectum-cloud-underwriting-golden','tectum','Build Tectum cloud underwriting and golden equivalence','Deploy deterministic cloud Traditional/Rooms/Temporary underwriting and compare with controlled golden cases.','All material golden outputs match accepted tolerances with versioned receipts.','tectum','blocked',1000,1.0,0.8,0.75,0.6,0.35,'Cloud underwriting service is not deployed.','["tectum-cloud-underwriting"]'::jsonb,'["tectum-underwriting"]'::jsonb,'["verified:connector-state"]'::jsonb),
('tectum-cloud-render-golden','tectum','Build Tectum cloud renderer and golden fidelity','Deploy PPTX/PDF/preview renderer with hashes and approval invalidation.','Golden report fidelity passes and byte changes invalidate prior approvals.','tectum','blocked',800,0.9,0.7,0.75,0.6,0.3,'Cloud renderer is not deployed.','["tectum-cloud-renderer"]'::jsonb,'["tectum-render"]'::jsonb,'["verified:connector-state"]'::jsonb),
('execute-first-real-loop','revenue','Execute first real autonomous opportunity loop','Run one real signal through evidence, scoring, action, receipt and outcome update.','A real opportunity produces at least one executed cloud action receipt and externally verifiable outcome state.','chief-orchestrator','blocked',149,1.0,1.0,0.7,0.8,0.2,'Cloud runtime and at least one real signal connector are prerequisites.','["google-drive","google-sheets-crm"]'::jsonb,'["opportunity-score","policy-enforce"]'::jsonb,'["verified:runtime-gap"]'::jsonb),
('define-outreach-envelope','compliance','Define outbound communication authorization envelope','Set sender identity, lawful basis, audiences, channels, rates, templates, stop rules and escalation.','A versioned owner-approved communication envelope exists; no send occurs before activation.','governor','proposed',0,0.8,0.5,0.95,1.0,0.1,'Owner policy definition required before autonomous external sends.','["gmail"]'::jsonb,'[]'::jsonb,'["policy:external-outreach-disabled"]'::jsonb)
) as v(goal_key,goal_class,title,objective,success_condition,owner_agent_slug,status,expected_economic_value,strategic_value,urgency,confidence,reversibility,risk,blocker,required_connectors,required_capabilities,evidence_refs)
on conflict(goal_key) do update set title=excluded.title,objective=excluded.objective,success_condition=excluded.success_condition,owner_agent_slug=excluded.owner_agent_slug,status=excluded.status,expected_economic_value=excluded.expected_economic_value,strategic_value=excluded.strategic_value,urgency=excluded.urgency,confidence=excluded.confidence,reversibility=excluded.reversibility,risk=excluded.risk,blocker=excluded.blocker,required_connectors=excluded.required_connectors,required_capabilities=excluded.required_capabilities,evidence_refs=excluded.evidence_refs,budget_ref=excluded.budget_ref,updated_at=now();

-- Hard dependencies among the operating backlog.
insert into public.goal_dependencies(goal_id,depends_on_goal_id,dependency_type)
select g.id,d.id,'hard' from public.goals g join public.goals d on d.goal_key='deploy-cloud-runtime' where g.goal_key in ('wire-drive-crm-runtime','wire-market-providers','wire-funding-feed','tectum-cloud-underwriting-golden','tectum-cloud-render-golden','execute-first-real-loop')
on conflict do nothing;
insert into public.goal_dependencies(goal_id,depends_on_goal_id,dependency_type)
select g.id,d.id,'hard' from public.goals g join public.goals d on d.goal_key='wire-drive-crm-runtime' where g.goal_key='execute-first-real-loop'
on conflict do nothing;
