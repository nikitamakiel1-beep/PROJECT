# Real-estate runtime and pairwise mandate-fit layer

## Purpose

A30 supplements the existing A23 restricted real-estate CRM vertical with executable underwriting, operational runtime sheets and pairwise mandate-fit assessment.

It does not replace A23. A23 remains authoritative for:

- legal and real-estate authority boundaries;
- restricted-data custody;
- generic CRM bridging;
- property, deal, counterparty, investor, financing, underwriting, due-diligence and fee schemas;
- dry-run import quarantine;
- prohibition of mediation, investment advice, valuation approval, mortgage advice, outreach and transaction action.

A30 adds only the missing execution layer:

- detailed field mapping for the observed private opportunity workbook;
- deterministic property and scenario identifiers;
- traditional, room-rental and temporary-rental calculations;
- downside, base and upside scenarios;
- transparent acquisition cost, debt service, yield and cash-flow metrics;
- a pairwise fit calculation for one supplied mandate and one supplied property scenario;
- operational property, mandate, match, viewing, transaction and tenancy sheets;
- dashboard metrics and controlled legacy aliases.

## Source boundary

The source workbook contains approximately 770 populated property-opportunity rows and includes private or proprietary material such as internal operators, prospective clients, listing URLs, cadastral references, property notes and transaction history.

Only aggregate structure and field taxonomy are represented in GitHub. The workbook and its row-level records remain restricted.

Current source status:

```text
rights_status: unverified
row-level import permitted: false
source rows imported: 0
real property rows created: 0
investor mandates created: 0
```

Import requires documented evidence that the source is owned, licensed, client-authorised or public, plus a named data-controller purpose and row-level human approval.

## Object model

The generic CRM remains authoritative for Companies, Contacts, Leads, commercial Opportunities, Activities, Services and Automation Log.

A **commercial Opportunity** is a sale of a venture service to a client.

A **property opportunity** is a property being researched, underwritten, matched, viewed, offered, reserved or acquired.

A property match cannot automatically create a commercial Opportunity. Property acquisition values, offers, deposits and financing are not venture revenue. Only separately approved service or advisory fees may enter commercial pipeline and cash metrics.

## Runtime sheets

A30 defines the following operational sheets as supplements to the A23 restricted tables:

- Properties;
- Property Scenarios;
- Investor Mandates;
- Property Matches;
- Viewings & Offers;
- Due Diligence;
- Transactions;
- Tenancies;
- RE Import Staging;
- RE Dashboard;
- RE Config.

The current merged CRM contains these sheets as header-only controlled structures. No source rows have been imported.

## Underwriting model

Each enabled strategy may generate downside, base and upside scenarios.

Inputs include:

- purchase price;
- renovation;
- operator-supplied transfer tax;
- notary and registry;
- agency and advisory fees;
- financing ratio, interest rate and term;
- rent;
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

The engine does not infer legal tax treatment, certify value, guarantee returns or approve financing.

## Pairwise mandate-fit assessment

The fit function evaluates one supplied mandate against one supplied property scenario. It does not search the investor database or select investors for solicitation.

Weighted evidence:

- budget fit: 24%;
- geography fit: 18%;
- strategy fit: 18%;
- return fit: 24%;
- renovation/risk fit: 10%;
- data confidence: 6%.

Every result is:

```json
{
  "status": "review_required",
  "human_approved": false
}
```

The result cannot contact an investor, share a property, submit an offer, reserve an asset, create a contract or process payment.

## Data quarantine

The runtime detects and quarantines:

- internal operator names;
- prospective-client names;
- email addresses and telephone numbers;
- raw listing URLs;
- raw cadastral references;
- identifiable property notes;
- unbounded free text.

Evidence-safe records use deterministic digests, aliases and tokens. Raw evidence stays in restricted Drive storage.

## Validation

`python scripts/test_real_estate_runtime.py` covers 13 synthetic/adversarial cases:

- rights rejection;
- deterministic normalisation;
- sensitive-field quarantine;
- three-strategy scenario generation;
- transparent underwriting;
- pairwise fit;
- strategy mismatch;
- commercial/property separation;
- missing property code;
- malformed financial input;
- A23 baseline preservation;
- field-mapping governance;
- runtime-sheet contract.

## Current boundary

Permitted now:

- schema and runtime development;
- synthetic tests;
- empty CRM sheet construction;
- aggregate source profiling;
- internal human-reviewed calculations.

Not permitted now:

- row-level source import;
- public property inventory;
- investor solicitation;
- real-estate mediation or negotiation;
- transaction recommendation;
- valuation, legal, tax or mortgage advice;
- offers, reservations, contracts, payments or closing actions;
- automatic external communication.
