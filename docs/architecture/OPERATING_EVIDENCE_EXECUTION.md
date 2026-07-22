# Operating evidence execution

## Objective

Stage 003p converts the operating-launch source pack into its first reconciled evidence cycle without activating provider runtime, contacting prospects or claiming commercial traction.

The adapter accepts bounded pseudonymous snapshots from CRM, Linear and the customer-discovery register. It verifies source counts, calculates the management digest, generates the ten required interview slots and writes a tamper-evident receipt for human review.

## Current observed state

The connector readback on 22 July 2026 found:

- CRM Leads: zero business rows;
- CRM Opportunities: zero business rows;
- CRM Activities: zero business rows;
- CRM Automation Log: zero execution rows;
- customer interviews: zero completed rows;
- Linear programme: 18 Done, 9 In Progress and 2 Todo;
- overdue open Linear issues: zero as of the snapshot date;
- open pipeline, won revenue and confirmed collected cash: €0.

These figures are recorded as a zero-state evidence receipt, not as a success metric. The corresponding Drive digest remains pending human review.

## Data boundary

The repository adapter rejects:

- names and company names;
- email addresses and telephone numbers;
- addresses, websites and URLs;
- recordings, raw transcripts and raw notes;
- passwords, tokens, API keys and secrets;
- unbounded text fields.

Connector-side extraction must pseudonymise or aggregate evidence before invoking the adapter. Live spreadsheet IDs and private links remain outside source control.

## Reconciliation sequence

```text
bounded connector readback
        ↓
public-safe JSON snapshot
        ↓
recursive personal-data and credential scan
        ↓
asserted row counts versus observed rows
        ↓
weekly management digest
        ↓
data-quality warnings
        ↓
programme-gate action queue
        ↓
ten-slot interview execution queue
        ↓
SHA-256 operating evidence receipt
        ↓
human review
```

A source-count mismatch stops the process. Missing evidence produces a warning and a human action; it does not produce estimated or invented records.

## Interview execution queue

The deterministic queue contains:

- five local or Barcelona-area SMEs;
- two referral professionals;
- one chamber, association, PAE or enterprise-support organisation;
- two founders or commercial managers in specialist B2B.

Every slot starts as `unassigned`. It stores only the target profile, route and contact-basis requirement. A human must select an organisation or person, document the lawful contact basis and approve the channel before outreach.

## Management metrics

The digest keeps the following distinctions explicit:

- open pipeline versus weighted pipeline;
- won revenue versus confirmed collected cash;
- due today versus overdue;
- completed interview evidence versus queued interview capacity;
- source-code completion versus provider execution;
- generated action versus approved human action.

Won revenue is not cash. A payment amount is included only when `payment_confirmed=true`.

## Current Drive evidence

The weekly management register contains one row for 22 July 2026 and a human action queue. Its digest is:

```text
5de3844791f00c7c487eadc0609470fe7d844d186ef6f1b473357f8bc33b0043
```

The public-safe source receipt is stored at:

```text
evidence/operating/2026-07-22-zero-state.json
```

It contains counts and controls only. It does not contain spreadsheet identifiers, contact data or private evidence links.

## Execution and validation

```bash
python scripts/reconcile_operating_evidence.py snapshot.json \
  --as-of 2026-07-22 \
  --output operating-receipt.json

python scripts/test_operating_evidence_execution.py
```

The maximum automated result is a receipt pending human review. The adapter never sends outreach, mutates CRM or Linear, approves a proposal, issues an invoice, activates public intake or advances the stage pointer.

## Remaining evidence gates

1. A human reviews and dispositions the first weekly digest.
2. Ten interview targets are selected and their contact bases are recorded.
3. Interviews are performed and pseudonymous evidence is entered.
4. Interview-derived CRM records are created only after the human post-interview decision.
5. The bound Apps Script provider qualification suite is executed separately.
6. Legal, tax, invoicing and final commercial wording receive professional review.
7. Stage 003 remains active until provider evidence and cleanup are accepted.
