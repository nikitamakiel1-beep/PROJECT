# Creixement Cloud Control Plane v1

Status: implementation contract
Date: 2026-09-09

## Non-negotiable runtime rule

All production Creixement workflows are cloud-only. No operator laptop, desktop Excel installation, local scheduler, local filesystem, local browser session, or workstation daemon may be a production dependency. Local development may exist transiently, but production execution, custody, scheduling, calculation, rendering, orchestration, auditing and recovery must run in managed cloud services.

## System roles

- Lovable: private operator cockpit only. It does not hold secrets or become the canonical business record.
- Supabase/PostgreSQL: control-plane state, products, agents, recommendations, actions, approvals, runs, connectors, policies, audit events, resources and report metadata.
- Google Drive: governed business records, evidence, client files, source artefacts and human-readable deliverables.
- Google Sheets CRM: validation-stage commercial ledger for leads, companies, contacts, opportunities, activities, services, next actions and revenue.
- GitHub: versioned code, contracts, schemas, prompts/config, tests, release manifests and technical documentation.
- Linear: execution backlog, milestones, dependencies and implementation evidence.
- Managed cloud compute: deterministic jobs, research workers, report generation, scheduled automations and connector workers.

## Control loop

LISTEN -> INGEST CHANGES -> NORMALISE -> VERIFY AUTHORITY / RIGHTS / FRESHNESS -> UPDATE MEMORY -> DETECT OPPORTUNITIES / BLOCKERS / DEADLINES -> COMPILE CONTEXT -> ROUTE SCOPED AGENTS -> DELIBERATE -> CRITIQUE -> RANK -> POLICY CHECK -> EXECUTE L0-L2 OR QUEUE L3 -> VERIFY RESULT -> WRITE RECEIPT -> LEARN.

Every execution requires a correlation ID, idempotency key, input digest, policy decision, output digest, status and audit receipt.

## Agent model

Agents are scoped and permissioned; no unrestricted super-agent exists.

1. Chief Orchestrator: decomposes objectives and routes work; cannot directly perform consequential external actions.
2. Research Agent: public/company/market research, evidence collection and source freshness.
3. Product Architect Agent: converts recurring work into productised offers, tests and schemas.
4. Commercial Agent: lead/account scoring, opportunity matching, proposal and follow-up preparation.
5. Report Factory Agent: generates controlled report drafts from approved evidence/templates.
6. Tectum Agent: coordinates Tectum property intelligence using cloud-native underwriting and report services.
7. Funding Agent: discovers and scores funding programmes without guaranteed-eligibility claims.
8. Marketing Agent: positioning, campaigns, content and landing-page preparation.
9. Finance Agent: unit economics, pricing, margin, pipeline and verified revenue analysis; no payment authority.
10. QA/Critic Agent: evidence, arithmetic, contradictions, unsupported claims and release-readiness review.
11. Compliance/Governor Agent: rights, consent, privacy, permissions and policy enforcement.
12. Automation Engineer Agent: connector health, retries, idempotency, schedules and runbooks.
13. Synthesis Agent: ranks recommendations across agent outputs.

## Autonomy levels

- L0 Observe: read/summarise only.
- L1 Recommend: draft recommendations, reports, experiments and actions.
- L2 Operate: bounded, reversible, auditable internal actions explicitly allowed by policy.
- L3 Consequential: external sends, publication, client delivery, contractual/financial commitments, irreversible deletion and payments. Requires explicit policy/approval.

No global autonomy toggle is allowed.

## Product-factory architecture

Creixement is a shared venture/product factory. Initial families include International Growth, Commercial Systems, Sales Assets, Market Intelligence, Prospect/Account Intelligence, Funding Intelligence, Web Products and Tectum Real Estate.

Common pipeline:

Intake -> Research -> Evidence -> Analysis/Scoring -> Recommendation -> Policy/Human Gate -> Generation/Execution -> QA -> Delivery -> CRM -> Revenue -> Learning.

The same infrastructure should support multiple SKUs rather than separate applications per product.

## Cloud-only Tectum migration

### Principle

The existing USANDO workbook may remain a controlled artefact/projection, but it must no longer require desktop Excel as the production calculation engine.

### Target cloud pipeline

Permitted source -> rights/evidence validation -> property candidate -> canonical property/scenario model -> deterministic cloud underwriting -> Traditional/Rooms/Temporary scenarios -> readiness/blockers -> exact-address/zone/media evidence -> cloud report job -> structural/visual QA -> four digest-bound approvals -> client-ready candidate -> CRM event/snapshot.

### Underwriting service

Port the financial logic required for Tectum decisions into a versioned deterministic service with explicit input/output schemas. Preserve formulas, thresholds, scenario definitions and rounding rules. The service must be independently testable and must emit a calculation receipt containing model version, input digest, output digest and test-suite version.

The current workbook remains a reference and optional export/projection until the cloud model passes golden-case equivalence.

### Migration verification

Before live release, execute golden-case regression for representative Traditional, Rooms and Temporary scenarios. Compare every material input, intermediate and output needed by the report. Any unexplained discrepancy blocks promotion. Store golden fixtures and expected outputs in versioned test data, excluding personal/confidential data.

### Workbook compatibility

If Excel-compatible cloud manipulation is required during migration, use an authenticated cloud Office service such as Microsoft 365/Graph against a controlled OneDrive/SharePoint workbook. This is a compatibility layer, not the long-term source of computational truth. No desktop Excel/COM dependency is permitted.

### Report generation

Move AutoPPTX/PDF generation into managed cloud compute. The renderer must:

- read only approved structured inputs and permitted media;
- deterministically order assets;
- generate editable PPTX;
- render PDF and preview images in cloud compute;
- generate layout/verification metadata;
- hash all inputs and outputs;
- bind approvals to the exact deliverable digest;
- invalidate approvals after any byte change.

The renderer may use a managed container with a validated office/rendering stack, or a cloud-native presentation generation pipeline, but fidelity must be regression-tested against the golden report.

### Tectum prohibitions retained

- no unattended unauthorised portal scraping;
- no access-control bypass;
- no unlicensed media use;
- no silent tax/zone assumptions;
- no automatic property offer, financing commitment, contract, invoice, payment or purchase;
- no client release without the required approval policy.

## Cloud service decomposition

Recommended logical services:

1. control-plane-api: authenticated API for projects/products/recommendations/actions/approvals/runs/connectors/audit.
2. ingestion-workers: webhook/poll workers for Drive, CRM, GitHub, Linear, Gmail, Calendar, Contacts and approved providers.
3. research-worker: evidence-gathering and structured research jobs.
4. recommendation-worker: opportunity detection, scoring, agent routing, critic pass and ranked output.
5. action-worker: executes allowed L2 actions and queues L3 approvals.
6. report-worker: generic report generation.
7. tectum-underwriting-service: deterministic real-estate calculation engine.
8. tectum-render-service: PPTX/PDF/previews/hashes/receipts.
9. scheduler: recurring workflows and condition checks.
10. audit-receipt-service: append-only audit projection and immutable artefact digests.

These may initially share one deployment while keeping clear module boundaries.

## Connector policy

All secrets are server-side only. Browser code receives connector state, never reusable credentials.

Required first-wave connectors:

- Google Drive
- Google Sheets CRM
- GitHub
- Linear
- Gmail
- Google Calendar
- Google Contacts
- Lovable
- approved market/funding data providers
- Clay or equivalent approved enrichment provider
- Tectum Cloud Underwriting
- Tectum Cloud Renderer

Optional migration connector:

- Microsoft 365 cloud workbook compatibility

Every connector exposes capability matrix, scopes, data classification, last sync, cursor, error, retry policy, rate limit, health and owner.

## Recommendation object

Each recommendation contains objective, product/project, recommendation, evidence references, alternatives, expected value, cost, confidence, uncertainty, strategic fit, reversibility, risk, required permission, expiry and proposed actions.

Hard policy gates override ranking scores.

## Revenue truth

Revenue is recorded only when the actual commercial condition has been satisfied. Leads, proposals, invoices sent, self-payments, paper projections or theoretical pipeline are not revenue.

## Production acceptance criteria

Cloud Control Plane v1 is not considered operationally complete until:

1. Lovable private cockpit is functional and authenticated.
2. Supabase persistence is live and migrations are versioned.
3. Drive and CRM read sync runs automatically in cloud.
4. GitHub and Linear sync runs automatically in cloud.
5. Gmail/Calendar/Contacts are connected with explicit scopes.
6. At least one product workflow executes intake -> recommendation -> allowed action -> receipt entirely in cloud.
7. Tectum underwriting passes golden-case cloud equivalence.
8. Tectum cloud renderer passes golden-report fidelity checks.
9. No production path depends on an operator machine.
10. L3 actions remain approval/policy gated.
11. Connector health, agent runs, recommendations and receipts are visible in Lovable.
12. Backup/recovery and secret rotation procedures are tested.
