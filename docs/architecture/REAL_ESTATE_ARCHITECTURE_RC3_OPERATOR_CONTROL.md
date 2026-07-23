# Real-Estate Architecture RC3 — Operator Control and Readiness

RC3 turns the RC2 collection of controlled tools into one operator workflow.

## New control plane

Every property receives a local `case-control.json` with nine weighted components:

1. source intake and rights — 10%;
2. property facts and evidence — 10%;
3. USANDO underwriting — 20%;
4. La Vanguardia zone evidence — 10%;
5. property and surroundings media — 10%;
6. PPTX/PDF generation — 15%;
7. four-role report approvals — 10%;
8. legal, technical and occupancy due diligence — 10%;
9. client decision and instruction — 5%.

The control file is updated only by explicit operator actions. The system reports the percentage, missing gates, blockers, the next five manual actions and the automation available for each action.

## Release percentages

RC3 separates three concepts that must not be conflated:

- **Architecture package release:** code, tests, boundaries, manuals, traceability and review custody.
- **Controlled operator use:** the ability to analyse properties using the local tools plus named manual review.
- **Live client production:** authorised live sources, privacy/controller approval, service identities, real validations and golden reports.

The baseline evidence produces:

| Mode | Score | Decision |
|---|---:|---|
| Architecture package | 98.8% | ready for release review |
| Controlled operator use | 81.5% | controlled use ready |
| Live client production | 47.0% | not ready |

A percentage never overrides a critical blocker or approval gate.

## RC2 defects closed

### Single-file cleanup isolation

The recovered WatermarkRemover command accepts directories. RC2 passed the original source directory, which could process unrelated images. RC3 creates an isolated one-file input directory for each approved job and rejects unexpected extra outputs.

### Idempotent AutoPPTX media staging

RC2 copied new files but did not remove old managed images. RC3 removes only previously managed `NN_piso.*` and `NN_zona.*` files, deduplicates inputs by SHA-256, copies in natural order and verifies every target digest.

### Transfer-tax header truth

RC2 exposed `Transfer Tax Rate` as if it were a confirmed workbook header. RC3 retains it as reviewed metadata until the actual USANDO header is identified. The Excel writer excludes metadata-only fields and reports whether manual transfer-tax binding remains necessary.

## Execution boundary

RC3 remains local and fail-closed. It adds no live scraping, portal bypass, live CRM write, automatic report delivery, offer, contract, financing request, invoice, payment or purchase execution.
