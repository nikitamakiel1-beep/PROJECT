# Synthetic Real-Estate Reconciliation and Rollback

**Stage:** 010r  
**Automation:** A27  
**Status:** Local synthetic reconciliation only.

## Purpose

Stage 010r compares two synthetic CRM fixture states, explains their differences by stable row ID, constructs a reversible mutation plan and proves rollback by restoring the original snapshot digest.

It operates after Stage 009r. It does not import real rows, connect to Drive, mutate Google Sheets or perform any commercial or transaction action.

## Runtime flow

```text
Stage 009r batch result or Stage 010r bundle
→ canonical fixture snapshot
→ stable-ID index and collision check
→ added / removed / changed / unchanged rows
→ quarantine introduction / resolution / change
→ field-level diff
→ forward mutation plan
→ exact target-digest verification
→ inverse rollback plan
→ original-digest restoration proof
→ deterministic reconciliation bundle
```

## Stable identities

Known CRM sheets use their governed primary IDs, including Property ID, Scenario ID, Match ID, Visit ID, Evidence ID, Report ID and Import ID. An unknown sheet is accepted only when exactly one populated field ends in ` ID`.

Duplicate stable IDs fail closed. Reconciliation never falls back to row position.

Quarantine receipts use a deterministic ID derived from batch ID and source row. This allows a quarantine to be introduced, resolved or changed across two synthetic states.

## Diff model

For each sheet, the diff records:

- added rows;
- removed rows;
- changed rows;
- unchanged stable IDs;
- exact field-level before and after values.

Quarantines are reconciled separately and included in aggregate totals.

## Mutation and rollback

Each operation contains:

- collection type and name;
- stable row ID;
- action: add, update or remove;
- before value;
- after value;
- canonical operation digest.

Application requires the exact source snapshot digest. Updates and removals also require the current row to equal the recorded before value. The completed state must equal the target snapshot digest.

The rollback plan reverses operation order, swaps before and after values and reverses additions/removals. Rollback qualifies only when the restored digest exactly equals the original snapshot digest.

## Reconciliation bundle

The deterministic ZIP can contain:

- `snapshot.json`;
- one CSV per populated sheet;
- quarantine CSV;
- machine-readable diff;
- human-readable Markdown diff;
- forward plan;
- rollback plan;
- rollback receipt;
- manifest with SHA-256 digests.

File ordering and ZIP timestamps are fixed. Tampered files are rejected on load.

## Safety boundary

Permitted:

- local synthetic snapshots and bundles;
- stable-ID comparisons;
- local mutation simulation;
- local rollback simulation;
- deterministic evidence generation.

Blocked:

- real source workbook access;
- Google Drive or Google Sheets access;
- real CRM mutation;
- external communication;
- proposals, invoices or payments;
- offers, reservations, financing, contracts or closings.
