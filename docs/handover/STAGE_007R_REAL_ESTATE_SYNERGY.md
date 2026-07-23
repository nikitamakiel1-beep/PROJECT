# Stage 007r Handover

## Read first

1. `docs/operations/REAL_ESTATE_CRM_VERTICAL.md`
2. `docs/architecture/REAL_ESTATE_RUNTIME_AND_MATCHING.md`
3. `docs/operations/REAL_ESTATE_SYNERGY_SYSTEM.md`
4. `config/real-estate-crm-vertical.json`
5. `config/real-estate-synergy-system.json`
6. `schemas/crm/real-estate/runtime-sheets-contract.json`
7. Stage 007r schemas and event contract
8. Restricted Drive folder `08 Real-Estate Synergy System`
9. The copied Synergy CRM, not the original CRM master

## Current state

- Original CRM preserved.
- Synergy CRM working copy created.
- A30 underwriting and pairwise fit runtime retained.
- Ten operational sheets added in Drive.
- Controlled vocabulary and source registry added.
- Stage 007r schemas and event contract prepared.
- Real source rows imported: 0.

## Next increment

Create Stage 008r as a synthetic-only orchestrator. It must validate events, enforce rights and restricted-field quarantine, call only A30 synthetic calculation/matching functions, produce deterministic mutation plans, and write to an in-memory or synthetic fixture only.

It must not contain Google credentials, real Drive identifiers, network calls, spreadsheet write clients, email/WhatsApp clients, proposal/invoice logic or transaction actions.

## Do not

- merge to `main` without review;
- import raw source rows;
- expose personal data or property identifiers;
- treat a score as permission to contact;
- represent calculations as valuation or advice;
- let AutoPPTX control communication, contracting or payments.
