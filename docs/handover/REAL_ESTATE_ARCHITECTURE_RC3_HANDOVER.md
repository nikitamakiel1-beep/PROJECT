# RC3 Operator-Control Handover

## Branch

`release/real-estate-architecture-rc3-operator-control`

Base: `release/real-estate-architecture-rc2`

## Purpose

RC3 converts RC2 into a guided operator workflow with deterministic programme and per-property readiness percentages.

## Read first

1. `docs/manuals/REAL_ESTATE_DAILY_OPERATOR_RUNBOOK_RC3.md`
2. `docs/status/REAL_ESTATE_RELEASE_STATUS_RC3.md`
3. `config/real-estate-release-readiness-rc3.json`
4. `evidence/readiness/2026-07-23-real-estate-release-evidence-rc3.json`
5. `intelligence/real_estate/operator_control.py`
6. `intelligence/real_estate/release_readiness.py`
7. `scripts/real_estate_operator_control.py`
8. `scripts/test_real_estate_operator_control_rc3.py`
9. `scripts/audit_real_estate_operator_control_rc3.py`

## Current scores

- Architecture package: 98.8% — ready for release review.
- Controlled operator use: 81.5% — controlled use ready.
- Live client production: 47.0% — not ready.

## Defects closed

- Watermark cleanup is isolated to one approved source file.
- Unexpected extra cleanup outputs fail the job.
- Original overwrite is rejected.
- AutoPPTX managed media staging is idempotent.
- Duplicate media are removed by hash.
- Copied media hashes are verified.
- Transfer tax is no longer assumed to be a real workbook header.
- The Excel receipt indicates whether manual transfer-tax binding remains necessary.

## Operator commands

```powershell
python scripts/real_estate_operator_control.py release-status
python scripts/real_estate_operator_control.py init-case ...
python scripts/real_estate_operator_control.py mark ...
python scripts/real_estate_operator_control.py status ...
```

## Remaining live blockers

1. Source permissions.
2. Controller/processor/privacy/service identity approval.
3. Authorised live source adapter.
4. Three-address La Vanguardia validation and approved legend.
5. Copied-USANDO test.
6. Authorised media-cleanup test.
7. Three golden reports.
8. Excel/PPTX/PDF parity receipts.
9. Named reviewers and observed rehearsal.

## Boundary

No live source collection, CRM write, report delivery, offer, financing, contract, invoice, payment or purchase execution is enabled.
