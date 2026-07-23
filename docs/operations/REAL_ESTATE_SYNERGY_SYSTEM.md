# Real-Estate Synergy System

**Control:** NIK-137  
**Stage:** 007r  
**Status:** Restricted working CRM and orchestration contracts prepared; no real source rows imported.

## Integration decision

The generic CRM remains authoritative for Companies, Contacts, Leads, commercial Opportunities, Activities, Services and Automation Log. The real-estate domain owns property sources, properties, mandates, scenarios, visits, evidence, renovation estimates, reports, approvals, fees, transactions and tenancies.

A property is not automatically a commercial Opportunity. A match cannot contact an investor or create an Opportunity without a named human approval and an actual client-service process.

## Relationship to A23 and A30

- A23 remains authoritative for restricted custody, generic CRM bridges, normalized real-estate entities and authority boundaries.
- A30 provides the synthetic underwriting engine, deterministic workbook mapping, runtime sheet contract and one-mandate/one-scenario fit assessment.
- A24/Stage 007r orchestrates the modules around A30: source registry, partner/captor intake, visits, evidence, renovation, report approvals, fee custody and event logging.

Stage 007r does not replace A23 or A30.

## Restricted Drive implementation

A working copy of the CRM was created under `08 Real-Estate Synergy System`; the original CRM master was not changed. The working copy preserves all existing sheets and adds:

- Property Sources
- Partners & Captors
- Visits
- Evidence & Media
- Renovation Estimates
- Reports & Approvals
- Fee Arrangements
- Synergy Event Log
- Source Registry
- Synergy Dashboard

The Source Registry contains metadata and controlled pointers only. No personal identity, full property address, cadastral reference or real source row is stored in GitHub.

## Operating flow

```text
source captured
→ rights and duplicate review
→ property record
→ visit/evidence collection
→ A30 underwriting scenarios
→ named underwriting approval
→ AutoPPTX/PDF draft
→ financial + evidence + legal + commercial approval
→ transparent pairwise match proposal
→ named match approval
→ CRM Opportunity only for a real client/service engagement
```

## Event contract

Events require:

- event ID;
- correlation ID;
- idempotency key;
- payload digest;
- producer and consumer;
- entity type and ID;
- explicit human-gate state.

Events may carry restricted pointers but not raw restricted values in public logs.

## Formula controls

Underwriting must record formula version, input snapshot digest, explicit tax rate, monthly loan convention, data confidence and named human review. Cached workbook values are not authoritative. Outputs are scenarios, not certified valuations, guarantees, legal/tax conclusions or investment advice.

## Current boundary

Permitted:

- schemas and synthetic runtime development;
- empty controlled sheet construction;
- source metadata registry;
- synthetic underwriting and pairwise fit;
- draft report metadata;
- read-only dashboard metrics.

Blocked:

- real row import;
- autonomous outreach;
- investor solicitation or suitability decision;
- valuation, offer or financing approval;
- due-diligence clearance;
- contract, invoice, payment or transaction action;
- live publication and paid delivery.
