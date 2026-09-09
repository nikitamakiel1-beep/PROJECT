# Creixement Overhaul v4 — Autonomous Company Operating System

Status: implementation contract
Date: 2026-09-09
Runtime: cloud-only
Supersedes: v3 as the target architecture; v3 remains the stable base.

## Objective

Creixement v4 is a cloud-native autonomous company operating system. It must continuously discover lawful opportunities, maintain a portfolio of products and ventures, allocate bounded resources, coordinate specialist agents, learn from verified outcomes, operate internal systems, and surface only the decisions that genuinely require the owner.

The system must optimize for verified economic outcomes, not activity volume. It must never fabricate external execution, demand, customer acceptance, revenue, connector state, or release readiness.

## Core principles

1. Cloud-only production. No workstation, desktop Excel, local scheduler, local filesystem, operator browser session, or local daemon can be required for production.
2. One operator surface, many bounded specialists. The Lovable Chief Operator is the human-facing interface; specialist and child agents are permissioned internal workers.
3. Truth before autonomy. Verified outcomes outrank connector receipts, which outrank governed evidence, which outrank model inference and hypotheses.
4. Authorization is explicit. L0–L2 can execute automatically only inside valid envelopes with real adapters and receipts. Consequential L3 remains non-delegable unless an explicit narrow constitution says otherwise.
5. Economic selection. Attention and experiment capacity are scarce resources; allocate toward proven value while preserving exploration.
6. Reversible by default. New capabilities and experiments start bounded, observable and easy to stop.
7. Evidence-linked memory. Every reusable fact, inference and decision has source, freshness, authority, truth level and supersession semantics.
8. Fail closed. Missing credentials, ambiguous rights, expired authorization, broken receipts, open circuit breakers, stale evidence or failed release gates block execution.

## Operating organism

```text
                         CREIXEMENT CHIEF OPERATOR
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
     GOAL SYSTEM              OPPORTUNITY SYSTEM         MEMORY SYSTEM
          │                        │                        │
     mission → DAG            signals → scoring        evidence → context
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │
                           SPECIALIST ROUTER
                                   │
   ┌──────────┬──────────┬─────────┼─────────┬──────────┬───────────┐
   │          │          │         │         │          │           │
 Research  Commercial  Product   Tectum   Funding   Marketing   Evolution
   │          │          │         │         │          │           │
   └──────────┴──────────┴─────────┼─────────┴──────────┴───────────┘
                                   │
                         POLICY + BUDGET ENGINE
                                   │
                         CLOUD EXECUTION FABRIC
                                   │
                    RECEIPTS / EVIDENCE / OUTCOMES
                                   │
                         ECONOMIC FITNESS UPDATE
                                   │
                           PORTFOLIO REALLOCATION
```

## Persistent mission and goal DAG

The Chief Operator owns a persistent mission and a dynamic directed acyclic graph of goals.

A goal has:
- objective and measurable success condition;
- parent mission / parent goal;
- dependencies;
- owner agent;
- priority;
- expected economic value;
- strategic value;
- urgency / deadline;
- confidence;
- reversibility;
- risk;
- budget envelope;
- required connectors/capabilities;
- evidence refs;
- current blocker;
- status;
- expiry / review cadence.

The planner must prevent dependency cycles. Runnable goals are those whose dependencies have reached acceptable terminal states and whose policy/connector prerequisites are satisfied.

The Chief Operator reprioritizes goals from verified changes, not from narrative enthusiasm.

## Goal classes

- Revenue: qualified demand, proposal conversion, paid delivery, repeat purchase.
- Product: validate, productize, automate, improve quality, reduce delivery cost.
- Opportunity: investigate a signal, market, company, property, funding call or partnership.
- Client delivery: produce and QA contracted deliverables.
- Tectum: source/evaluate/report property cases.
- Reliability: repair connectors, workers, tests, dead letters or drift.
- Strategic: build reusable capability, provider integration or differentiated IP.
- Compliance: rights, privacy, consent, contracts, data lifecycle.

## Economic budget system

Creixement separates resource allocation from payment authority.

Budget types:
- attention units;
- agent-run quota;
- research/enrichment records;
- experiment capacity;
- external API cost ceiling;
- publication/outreach quotas;
- delivery hours estimate;
- owner-review capacity.

A budget authorization is not a bank/payment authorization. Real money movement remains governed by payment authority.

Every bounded action consumes budget units and is rejected if its envelope would be exceeded.

## Portfolio allocator

Portfolio allocation works at three levels:

1. Venture / product family.
2. Niche / commercial genome.
3. Individual experiment or opportunity.

Default seed remains 70% exploit / 20% adjacency / 10% exploration, but v4 introduces evidence-weighted reallocation with floors and caps.

Signals for allocation:
- verified contribution margin;
- paid conversion;
- repeat purchase;
- qualified pipeline quality;
- delivery burden;
- automation ratio;
- customer acceptance / outcome evidence;
- evidence quality;
- strategic moat;
- recurrence;
- rights / legal burden;
- connector/provider fragility;
- confidence interval width.

No variant can consume the entire exploration budget solely from one noisy observation.

## Provider and capability router

Every external or internal capability is represented explicitly.

Provider descriptor:
- provider/capability key;
- operation classes;
- runtime readiness;
- rights/terms status;
- data classification;
- geography/sector coverage;
- estimated cost;
- latency;
- reliability/SLO;
- evidence quality;
- freshness;
- rate limits;
- receipt support;
- idempotency support;
- secrets required;
- circuit breaker state.

The router evaluates:
- USE existing capability;
- BUILD reusable internal capability;
- BUY a third-party capability only if procurement/spend authority exists;
- COMBINE compatible capabilities;
- ABSTAIN when evidence/economics/rights are weak.

Providers are interchangeable behind operation contracts so the business is not structurally dependent on one vendor.

## Provenance-aware memory

Memory is not a bag of embeddings. v4 uses structured knowledge records with:
- subject / predicate / object or structured payload;
- namespace/project/product;
- truth level;
- source refs;
- observed/fetched time;
- valid-from / valid-until;
- source authority;
- freshness score;
- confidence;
- sensitivity/data class;
- consent/rights state;
- digest;
- supersedes / superseded-by;
- contradiction group;
- usage count;
- last-used time.

Memory retrieval scores authority, freshness, truth level and task relevance. A newer low-authority inference cannot overwrite a verified external outcome.

Contradictions remain visible until resolved by stronger evidence.

## Experiment adjudication

Experiments require:
- hypothesis;
- target metric;
- baseline/control where appropriate;
- arm definitions;
- sample/observation budget;
- minimum effect worth caring about;
- stop rules;
- rights/consent constraints;
- expected cost;
- expiry;
- interpretation policy.

The system can stop for:
- clear evidence of benefit;
- clear evidence of harm/underperformance;
- budget exhaustion;
- stale context;
- policy violation;
- insufficient power / inconclusive completion.

It must not declare a winner from one anecdote unless the experiment is explicitly single-case qualitative validation.

## Autonomous child agents

Child agents remain bounded templates, but v4 adds:
- spawn budget per parent and niche;
- TTL;
- maximum depth;
- capability and connector intersection only;
- no privilege inheritance above parent;
- output schema contract;
- evidence requirement;
- promotion threshold;
- automatic retirement;
- no autonomous creation of new authorization envelopes.

A successful child capability may be promoted only after repeatable verified success and QA evidence.

## Runtime fabric

Execution services use:
- durable outbox/events;
- leased jobs;
- idempotency keys;
- correlation IDs;
- structured traces;
- heartbeats;
- exponential backoff;
- dead-letter queues;
- replay controls;
- connector circuit breakers;
- per-handler concurrency;
- priority with aging/fairness;
- terminal-state immutability;
- receipt verification.

No worker may mark success solely because an LLM returned text.

## Observability

v4 adds service-level objectives and incident state.

Tracked dimensions include:
- job success rate;
- connector sync success;
- p50/p95 latency;
- queue age;
- dead-letter rate;
- stale evidence rate;
- receipt verification rate;
- policy-block rate;
- opportunity-to-experiment conversion;
- experiment-to-paid-outcome conversion;
- delivery acceptance;
- verified contribution margin.

Incidents are opened from violated SLOs or repeated failures, not hidden in logs.

## Service identities and secrets

Every cloud worker/service has a named service identity with minimum necessary scopes.

Secret records store metadata only:
- secret name;
- provider;
- owning service;
- environment;
- rotation policy;
- last rotated timestamp;
- next rotation due;
- required/optional state.

Secret values never enter the Lovable browser, GitHub source, audit narrative or model prompts.

## Release gates

A release is promotable only if required gates pass:
- CI/typecheck/tests;
- database migrations clean-install + upgrade path;
- constitution/schema validation;
- cloud-only regression gate;
- no critical unresolved incidents;
- backup/restore rehearsal current;
- secret requirements satisfied for enabled services;
- runtime connectors healthy for enabled workflows;
- approval semantics tested;
- Tectum golden-case equivalence for Tectum release;
- Tectum golden-report fidelity for renderer release;
- cockpit truth-state checks;
- rollback plan present.

Release readiness is computed from evidence. It is never manually represented as 100% simply because code exists.

## Tectum v4

Tectum remains one vertical and receives stricter cloud contracts:

- canonical property/evidence input schema;
- deterministic underwriting service with version/digest receipt;
- explicit Traditional / Rooms / Temporary calculators;
- uncertainty and assumption register;
- source-rights state for every material fact/media item;
- exact-address/zone evidence where required;
- cloud report renderer;
- four distinct digest-bound approval roles;
- report byte change invalidates approvals;
- golden-case equivalence before underwriting promotion;
- golden-report render fidelity before renderer promotion;
- no automatic property/financing/contract/payment/purchase commitment.

## Commercial autonomy

The system should eventually be able to:
- discover companies and needs from lawful sources;
- enrich and qualify accounts;
- match products;
- create proposals/assets;
- maintain CRM;
- run experiments;
- generate follow-up drafts;
- send bounded outreach only inside an explicitly activated communication envelope;
- detect buying/reply signals;
- generate and deliver permitted low-risk digital products;
- update economic fitness;
- recommend price/scope changes;
- reallocate attention.

External communication remains disabled until the owner defines sender identity, lawful basis, audience, channel, rate, template/claim bounds, follow-up limits, stop/unsubscribe semantics and escalation rules.

## v4 completion definition

v4 is operational, not merely specified, when all are true:

1. A cloud runtime is deployed.
2. Supabase migrations are applied and verified.
3. At least one real connector ingests signals automatically.
4. The Chief Operator creates/reprioritizes a real goal DAG.
5. One opportunity proceeds signal -> evidence -> score -> experiment/action -> policy -> execution -> receipt -> outcome.
6. Provider routing rejects unavailable providers and chooses a real runtime-ready adapter.
7. Memory retrieval uses provenance/freshness/truth hierarchy.
8. Budget consumption and hard limits are enforced.
9. Job retries/dead-letter/replay are tested.
10. SLO violation creates an incident.
11. Release readiness is evidence-backed.
12. Lovable shows live state from Supabase without synthetic success.
13. Tectum production paths are cloud-only and pass required golden tests before activation.
14. No enabled production action depends on an operator machine.
