# Real-estate CRM vertical

## Purpose

This extension merges a property-investment operating model into the existing venture CRM without replacing the shared commercial core.

The source material is a private real-estate opportunity workbook with approximately 770 populated property rows, three rental strategies, property underwriting, viewings, investor candidates, fees, presentations and outcome tracking. Only its **structure, field taxonomy and aggregate workflow evidence** are represented in the repository. Row-level property records, names, URLs, cadastral references and free-text notes remain outside source control.

## Non-negotiable object boundary

The two meanings of “opportunity” are separated:

- **Commercial Opportunity** — a CRM sale of a service to a client.
- **Property Opportunity** — a property or building being researched, underwritten, matched, viewed, offered, reserved or acquired.

A property match cannot create a CRM Opportunity automatically. A human must separately approve a service engagement, fee, scope and payment path.

## Shared CRM core

The existing sheets remain authoritative for:

- Companies
- Contacts
- Leads
- Commercial Opportunities
- Activities
- Services
- Dashboard
- Config
- Automation Log

The real-estate vertical references core IDs rather than duplicating prospect or client identity.

## Extension sheets

The extension contract adds:

1. **Properties** — one record per property/building.
2. **Property Scenarios** — strategy and downside/base/upside underwriting.
3. **Investor Mandates** — pseudonymous buyer requirements linked to Leads/Contacts.
4. **Property Matches** — many-to-many mandate/property/scenario ranking.
5. **Viewings & Offers** — calls, document requests, viewings, offers, counters and reservations.
6. **Due Diligence** — cadastral, title, rental, occupancy, taxation and evidence checks.
7. **Transactions** — reservation through completion and advisory-fee evidence.
8. **Tenancies** — post-acquisition rental operations linked to Contacts where lawful.
9. **RE Import Staging** — rights, PII and restricted-field quarantine.
10. **RE Dashboard** — real-estate operating metrics.
11. **RE Config** — controlled vocabularies and status aliases.

## Source-workbook findings

Aggregate findings used to design the extension:

- Approximately 770 populated opportunity rows.
- 656 rows in the initial spreadsheet-analysis state.
- 37 presentation-ready rows.
- 18 validated rows.
- 17 shared rows.
- 15 rejected rows.
- 12 work-in-progress rows.
- 4 reserved rows.
- Traditional-rental analysis is nearly universal.
- Room-rental and temporary-rental analysis are optional per property.
- Source records combine acquisition economics, property facts, owner assignment, agency/source, property links, cadastral data, investor candidates and free-text notes.

These aggregates are architecture evidence, not a licence to reproduce the source dataset.

## Underwriting model

Each enabled strategy may produce downside, base and upside scenarios.

Inputs include:

- purchase price;
- renovation;
- transfer tax supplied by the operator;
- notary and registry;
- agency and advisory fees;
- financing ratio, rate and term;
- monthly rent;
- property tax, community, maintenance and insurance;
- vacancy.

Outputs include:

- total acquisition cost;
- monthly debt service;
- gross yield;
- net yield;
- return on equity;
- cash-on-cash return;
- monthly cash flow.

The engine is transparent and deterministic. It does not certify market value, tax treatment, legal title, tenancy legality, finance availability or future returns.

## Investor matching

Investor mandates include budget, cash, financing, geography, allowed strategies, return floors, renovation limits, risk appetite and timeline.

The match score combines:

- budget fit — 24%;
- geography fit — 18%;
- strategy fit — 18%;
- return fit — 24%;
- risk/renovation fit — 10%;
- data confidence — 6%.

Every match is `review_required` and `human_approved=false`. The engine cannot contact an investor, share a property, submit an offer or create a reservation.

## Data and rights custody

Before any row-level import:

1. record whether the source is owned, licensed, client-authorised or public;
2. identify the data controller and permitted purpose;
3. quarantine names, client references, raw notes and internal operators;
4. tokenise listing URLs and cadastral references in evidence-safe packages;
5. keep raw evidence in restricted Drive storage;
6. approve each import batch through a named human review.

`rights_status=unverified` blocks import.

## Fields that must not enter repository evidence

- personal names;
- potential-client names;
- direct telephone or email data;
- raw listing URLs;
- raw cadastral references;
- addresses precise enough to identify a private residence where unnecessary;
- free-text property notes;
- raw presentations or case histories;
- internal operator identities.

## CRM lifecycle

```text
Lead or referral
→ investor qualification
→ Investor Mandate
→ property research
→ Property Opportunity
→ strategy underwriting
→ human-reviewed Property Match
→ shared with investor
→ viewing / document request
→ offer / counteroffer
→ reservation
→ due diligence
→ completion
→ tenancy / aftercare
```

A separate commercial engagement may be created for advisory, audit, CRM, one-pager or other approved services. Property purchase value is never counted as venture revenue.

## Dashboard metrics

Recommended metrics:

- properties by acquisition status;
- validated and presentation-ready inventory;
- active investor mandates;
- approved matches;
- viewings booked and completed;
- offers, reservations and completed purchases;
- median acquisition cost;
- median base gross/net yield;
- median cash-on-cash return;
- data-confidence distribution;
- time from discovery to validation;
- time from sharing to viewing;
- advisory fees invoiced and collected;
- source/agency conversion;
- rejection reasons;
- due-diligence blockers.

## Current boundary

The extension is architecture-ready and synthetic-testable. It does not:

- import the private source workbook;
- assume a licence to reuse the business’s data;
- create real investors, properties or contacts;
- alter the live website;
- expose real-estate inventory publicly;
- provide regulated legal, tax, valuation, mortgage or investment advice;
- automate external communication, offers or reservations.
