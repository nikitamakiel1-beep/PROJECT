# Real-Estate Release Status RC3

As of 23 July 2026.

## Current percentages

| Release mode | Percentage | Decision |
|---|---:|---|
| Architecture package | 98.8% | Ready for release review |
| Controlled operator use | 81.5% | Ready for controlled manual use |
| Live client production | 47.0% | Not ready |

These values are calculated from `config/real-estate-release-readiness-rc3.json` and `evidence/readiness/2026-07-23-real-estate-release-evidence-rc3.json`.

A percentage is not release authority. Critical blockers and named approvals override the numerical score.

## What can be used now

The following can be used in a local restricted workspace:

- case initialisation and folder generation;
- case percentage and next-action reporting;
- manual listing-link or confidential intake;
- source and evidence classification;
- USANDO update-plan generation;
- Windows Excel COM execution on a copied workbook;
- supervised La Vanguardia capture and evidence validation;
- authorised one-file WatermarkRemover planning;
- idempotent AutoPPTX media staging;
- local report-generation planning;
- manual report checklist and four-role approval collection.

## What is not released

The following remain prohibited:

- unattended scraping;
- portal access-control or CAPTCHA bypass;
- unapproved source or media use;
- automatic writes to the live CRM;
- automatic report sending;
- client outreach;
- offer, reservation or financing submission;
- contract, invoice, payment or purchase execution.

## Main blockers to live production

1. Written permission or authorised API terms for every live property source.
2. Approved data-controller, processor, service-identity and retention package.
3. At least one authorised live source adapter.
4. Three real La Vanguardia address-validation receipts and an approved legend.
5. One copied-USANDO execution and field/formula reconciliation.
6. One authorised WatermarkRemover sample validation.
7. Traditional, room-rental and temporary-rental golden reports.
8. Excel/PPTX/PDF numerical and visual parity receipts.
9. Named live reviewers and an observed operating rehearsal.

## Commands

Release status:

```powershell
python scripts/real_estate_operator_control.py release-status
```

Start a case:

```powershell
python scripts/real_estate_operator_control.py init-case `
  "C:\RealEstate\Projects" `
  BA_BARCELONA_GRACIA01 `
  "Example apartment" `
  listing_link `
  --date 2026-07-23
```

View a case:

```powershell
python scripts/real_estate_operator_control.py status `
  "C:\RealEstate\Projects\BA_BARCELONA_GRACIA01\case-control.json"
```
