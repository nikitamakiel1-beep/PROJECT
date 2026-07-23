# Deterministic Synthetic Real-Estate Batch Adapter

**Stage:** 009r  
**Automation:** A26  
**Status:** Local synthetic batch runtime only.

## Purpose

Stage 009r converts local synthetic CSV or mapping fixtures into Stage 008r events. It provides batch-level correlation, row-level idempotency, non-blocking quarantine and a deterministic CSV workbook bundle for manual inspection.

It does not open the real opportunity workbook, connect to Drive, mutate the CRM or perform external communication.

## Processing model

```text
local synthetic CSV / mappings
→ batch contract validation
→ row envelope and rights selection
→ duplicate-code detection
→ Stage 008r property-case event
→ A30 normalization and scenarios
→ processed / replay / quarantine receipt
→ in-memory fixture
→ contract validation
→ deterministic CSV ZIP + manifest
```

One invalid row does not abort the batch. Duplicate external codes quarantine the later duplicate. Replaying the same batch against the same orchestrator produces replay receipts and does not duplicate rows.

## Correlation and idempotency

- Batch IDs must begin `SYN-BATCH-`.
- Source profiles must begin `SYNTHETIC_`.
- One correlation ID is derived from the batch ID.
- One idempotency key is derived from batch ID, source row and canonical row digest.
- A conflicting replay is quarantined by Stage 008r.

## Portable workbook bundle

The local export is a ZIP containing:

- one UTF-8 CSV per populated synthetic CRM sheet;
- `manifest.json` with counts, headers, file digests and contract reconciliation.

ZIP timestamps and file ordering are fixed, making repeated exports byte-for-byte deterministic.

The bundle is not uploaded or imported automatically. It exists for local inspection and synthetic schema comparison.

## Contract reconciliation

The adapter checks every generated sheet and field against `runtime-sheets-contract.json`. Unknown sheets or fields fail reconciliation. Missing optional fields are permitted because mutation plans may be partial.

## Current boundary

Permitted:

- local synthetic fixture parsing;
- local in-memory processing;
- deterministic local ZIP creation;
- synthetic contract validation;
- row-level quarantine evidence.

Blocked:

- real workbook access;
- Drive or Google Sheets access;
- real CRM writes;
- personal or property-identifying source data;
- outbound contact;
- offers, financing, contracts, invoices, payments or transactions.
