# Stage 008r Handover

## Branch

`venture/stage-008r-synthetic-synergy-orchestrator`

Base: `venture/stage-007r-real-estate-synergy-runtime`

## What exists

- A30 underwriting and pairwise matching remain authoritative.
- Stage 007r schemas and Drive working CRM remain intact.
- `intelligence/real_estate/synergy.py` adds synthetic event processing, idempotency, quarantine, in-memory mutation plans and report approval separation.
- Twelve adversarial tests cover the supported runtime paths.
- No real spreadsheet, Drive, mail, messaging or payment client exists.

## Next increment

Stage 009r should add a deterministic synthetic workbook-to-event adapter and a fixture export receipt. It may read a local synthetic CSV/JSON fixture and emit Stage 008r events, but it must not open the real workbook or access Drive.

Recommended sequence:

1. synthetic fixture schema;
2. local fixture adapter;
3. batch correlation and replay handling;
4. per-row quarantine receipts;
5. generated fixture workbook for manual inspection;
6. cross-check against the Synergy CRM sheet contract;
7. no network or real write client.

## Real-data gate remains closed

Before any real dry-run:

- source rights must be documented;
- data-controller purpose and processor terms must be signed;
- privacy and retention controls must be approved;
- restricted Drive service identity must be configured outside GitHub;
- named reviewers must approve the specific import batch;
- rollback and reconciliation evidence must exist.
