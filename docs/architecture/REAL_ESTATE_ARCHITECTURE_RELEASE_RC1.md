# Real-Estate Acquisition, Underwriting and Reporting Architecture — RC1

**Release:** `REAL-ESTATE-ARCHITECTURE-RC1`  
**Branch:** `release/real-estate-architecture-rc1`  
**Base:** `venture/stage-010r-synthetic-reconciliation-rollback`  
**Date:** 23 July 2026  
**Status:** Architecture release candidate; live acquisition and real-data execution remain gated.

## 1. Product objective

The release combines the existing commercial CRM, the normalized real-estate vertical, the recovered Maumer operating procedure, deterministic underwriting, evidence custody, property–investor matching, AutoPPTX/PDF reporting, reconciliation and rollback into one controlled product.

The system is intended to:

1. discover or receive Spanish property opportunities through authorised sources;
2. normalize each source into one governed property candidate;
3. deduplicate and assign an immutable project code;
4. enrich it with public and field evidence;
5. calculate versioned traditional, room-rental and temporary-rental scenarios;
6. match approved properties to investor mandates without autonomous outreach;
7. generate PPTX and PDF reports from approved data and media;
8. retain approvals, evidence, source rights, fees, transactions and rollback receipts.

## 2. Systems of record

- **Generic CRM:** leads, companies, contacts, commercial opportunities, activities, services, consent, ownership, next actions and revenue.
- **Real-estate CRM vertical:** properties, sources, scenarios, mandates, matches, visits, evidence, renovation estimates, reports, approvals, fees, transactions and tenancies.
- **Restricted Drive:** raw workbooks, personal data, full addresses, cadastral references, media, due-diligence documents, agreements and generated identifiable reports.
- **GitHub:** code, schemas, synthetic fixtures, configuration templates, tests, CI and public-safe receipts.
- **Linear:** execution work, decisions, dependencies, acceptance evidence and release tasks.

A raw property is not automatically a generic CRM Opportunity. A CRM Opportunity is created only when a real client or service process exists.

## 3. Source acquisition policy

### 3.1 Permitted acquisition modes

- Official provider API with approved credentials.
- Contracted agency, bank, fund or portal feed.
- Alerts requested by the user and received in a user-controlled mailbox.
- Supervised capture where a person supplies the listing reference and selected facts.
- Off-market or partner data supplied under a documented relationship.

### 3.2 Prohibited acquisition modes

- Unauthorised scraping, spiders or robots.
- CAPTCHA, login, rate-limit or robot-exclusion bypass.
- Account impersonation.
- Bulk copying or republication of portal media without rights.
- Silent use of a feed whose agreement, schema or provenance is unknown.

### 3.3 Portal matrix

| Source | Release mode | Live prerequisite |
|---|---|---|
| Idealista | Official Search API or supervised capture | API access approval and credentials, or named manual review |
| Fotocasa | Contracted feed, user alert or supervised capture | Written feed/export right or manual workflow |
| Habitaclia | Contracted feed, user alert or supervised capture | Written feed/export right or manual workflow |
| Pisos.com | Contracted feed, user alert or supervised capture | Terms/permission review |
| Yaencontre | Contracted feed, user alert or supervised capture | Terms/permission review |
| Milanuncios | Contracted feed, user alert or supervised capture | Terms/permission review |
| Bank/fund asset portals | Partner feed or supervised capture | Feed agreement or documented manual source |
| Agency sites | Partner feed or supervised capture | Agency authorisation or manual source review |
| Social/off-market sources | Supervised capture | Provenance, contact basis and off-market verification |

Idealista currently advertises a Search API by application. Its current general conditions prohibit automatic copying/extraction, robot or scraper access and circumvention of access restrictions without written permission. Therefore the release contains an API request builder but no Idealista web scraper.

## 4. Internal channel rules

The latest internal analysis procedure is encoded as follows:

- An Idealista listing is excluded from PSI+.
- A non-Idealista portal source may be PSI+ eligible after review.
- Channel distribution generally requires a verified off-market source.
- Bank, fund and social-source exceptions remain reviewable exceptions rather than automatic eligibility.
- An off-market claim is not sufficient; it must be verified.

These decisions are written into each acquisition plan and are not inferred later from free text.

## 5. Public-data enrichment

### Catastro

The architecture supports non-protected Catastro services, INSPIRE WFS/ATOM downloads and individual WMS views. Protected data requires authority. Massive tiled WMS downloading is explicitly blocked because the public WMS service is not intended for that use.

### INE

The INE JSON API can provide population, household and socioeconomic context. It must not be used to infer personal characteristics about occupants or owners.

### Field evidence

The visit workflow remains authoritative for building condition, distribution, systems, legal/technical documents and original media. Portal descriptions are not treated as verified facts.

## 6. Acquisition flow

```text
provider API / partner feed / user alert / supervised capture
→ source candidate schema
→ rights and review gate
→ portal/channel classification
→ Property Sources plan
→ RE Import Staging plan
→ deduplication
→ project-ID allocation
→ cadastral and visit evidence
→ underwriting approval
→ report generation
```

The release runtime produces no-write CRM mutation plans. A future deployment adapter must preserve the same idempotency, quarantine and rollback contracts before real writes can be enabled.

## 7. Underwriting

A30 remains the calculation engine. It provides:

- deterministic property normalization;
- traditional, room-rental and temporary-rental strategies;
- downside, base and upside scenarios;
- monthly debt service;
- gross yield, net yield, ROE, cash-on-cash and monthly cash flow;
- transparent mandate-fit scoring.

Required repairs remain part of the release gate:

- monthly-rate and monthly-payment-count PMT/IPMT convention;
- explicit reviewed transfer-tax rate;
- source evidence for rents and recurring costs;
- no silent default for unavailable rent-zone extraction;
- calculation version and input snapshot digest on every scenario.

The outputs remain analytical scenarios, not certified valuations, legal/tax advice or guaranteed returns.

## 8. Report generation

The release uses the recovered AutoPPTX package through a local adapter. It does not embed recovered credentials or large binaries in GitHub.

A report job requires:

- property and project identifiers;
- approved underwriting case and scenario IDs;
- calculation and template versions;
- input and source-candidate digests;
- verified evidence;
- owned, licensed, client-authorised or portal-authorised media;
- four approvals from distinct financial, evidence, legal and commercial reviewers.

The adapter:

1. writes an immutable job JSON;
2. executes a configured local Python entry point with `shell=False`;
3. supplies the job path and digest through environment variables;
4. verifies non-empty PPTX and, when required, PDF outputs;
5. calculates SHA-256 hashes;
6. leaves the report non-shareable until a separate delivery gate.

Known AutoPPTX repairs that remain mandatory:

- select the project through `#Pre-analisis!B3` unless a reviewed workbook version changes the control;
- initialize copied-image state;
- use natural numeric media ordering;
- preserve generated slide order;
- rotate recovered API/OAuth credentials;
- validate the financial formulas;
- fail closed on missing rent-zone evidence;
- validate one golden project per rental strategy.

## 9. Architecture-release approval

RC1 approval is bound to exact digests for:

- source connector registry;
- source candidate schema;
- report renderer configuration;
- release manifest.

Three distinct reviewers are required:

1. source-policy reviewer;
2. privacy reviewer;
3. architecture-release approver.

Changing any bound artifact invalidates prior approval.

## 10. Release sequence

### Phase A — complete before any live acquisition

1. Request Idealista API access.
2. Identify portals, banks, funds and agencies willing to provide a feed or professional export.
3. Document terms and data rights for every connector.
4. Configure a dedicated user-controlled alert mailbox.
5. Revoke and rotate recovered credentials.
6. Complete privacy, retention and controller/processor documentation.

### Phase B — complete before any real CRM write

1. Deploy a restricted service identity.
2. Implement the approved API/feed clients outside the public repository.
3. Run a no-write real-data profile.
4. Validate deduplication and project-ID allocation.
5. Produce reconciliation and rollback evidence.
6. Obtain named batch approval.

### Phase C — complete before report production

1. Configure the recovered AutoPPTX workspace.
2. Apply all known repairs.
3. Run traditional, room and temporary golden cases.
4. Compare generated PPTX/PDF against the workbook and checklist.
5. Obtain four-role report approval.

### Phase D — complete before external delivery

1. Confirm recipient and communication basis.
2. Confirm report approval is current and digest-bound.
3. Confirm PDF and PPTX hashes.
4. Record share event and recipient evidence.
5. Keep proposals, invoices, payments, offers and contracts in separate governed workflows.

## 11. RC1 boundary

RC1 prepares the architecture and local adapters. It does not activate live portal acquisition, real-data imports, real CRM writes, external report delivery, offers, financing, contracts, invoices, payments, merge to `main`, release tags or deployment.
