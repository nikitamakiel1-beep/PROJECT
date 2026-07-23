# Real-Estate Architecture RC1 Handover

## Current branch

`release/real-estate-architecture-rc1`

Base:

`venture/stage-010r-synthetic-reconciliation-rollback`

## What RC1 adds

- authorised Spanish source connector registry;
- source-candidate schema;
- deterministic source validation and channel classification;
- no-write Property Sources and RE Import Staging plans;
- official Idealista Search API request construction without execution;
- public Catastro and INE enrichment contracts;
- digest-bound three-role architecture approval;
- governed local AutoPPTX/PDF report jobs;
- four-role report approval with distinct reviewers;
- local renderer execution with `shell=False`;
- PPTX/PDF hash verification;
- complete architecture release document, regression tests and release audit.

## Read in this order

1. `docs/architecture/REAL_ESTATE_ARCHITECTURE_RELEASE_RC1.md`
2. `config/real-estate-architecture-release.json`
3. `config/real-estate-source-connectors.json`
4. `config/real-estate-report-renderer.json`
5. `schemas/crm/real-estate/source-candidate.schema.json`
6. `intelligence/real_estate/acquisition.py`
7. `intelligence/real_estate/report_release.py`
8. `intelligence/real_estate/release_approval.py`
9. `scripts/test_real_estate_architecture_release.py`
10. `scripts/audit_real_estate_architecture_release.py`

## Live deployment prerequisites

### Property sources

- approved Idealista API access and credentials;
- written feed/export rights for other portals or partners;
- dedicated alert mailbox;
- documented terms review for each connector;
- source provenance and media-rights controls.

### Real data

- data-controller instruction;
- privacy and retention review;
- restricted runtime identity;
- dry-run profile and quarantine evidence;
- named batch approval;
- reconciliation and rollback proof.

### Reports

- restricted AutoPPTX workspace;
- recovered credentials revoked and replaced;
- patched programme and financial model;
- golden project for each rental strategy;
- PPTX/PDF visual QA;
- four distinct report approvals.

## Important operating decision

Do not build generic web scrapers for Spanish portals. Use provider APIs, contracted feeds, user-owned alerts or supervised capture. The portal registry is deliberately fail-closed: a portal without verified API/feed rights remains manual or disabled.

## Next implementation after RC1 review

Create a private deployment branch or private runtime repository containing only approved provider clients and secret references. It should:

1. implement the approved Idealista API client;
2. implement partner-feed parsers with signed schema versions;
3. ingest user-owned alerts;
4. connect no-write plans to a restricted CRM staging copy;
5. run one approved real dry-run batch;
6. reconcile and roll back the dry-run;
7. configure AutoPPTX and generate three golden reports;
8. retain all evidence outside the public repository.

Do not merge RC1 to `main` until the release audit, workflow chain and three-role architecture approval are complete.
