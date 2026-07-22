# Operating launch system

## Purpose

Stage 003o converts the existing service, CRM and intelligence infrastructure into a repeatable human-controlled operating path:

```text
research invitation approval
        ↓
customer-discovery interview
        ↓
pseudonymous evidence coding
        ↓
human qualification decision
        ↓
controlled proposal and input request
        ↓
service delivery and named QA release
        ↓
acceptance, feedback and permission custody
        ↓
time, collection and contribution evidence
        ↓
aggregate weekly management digest
        ↓
human programme decisions
```

The system standardises evidence and decisions. It does not autonomously contact people, sell services, issue invoices, change pipeline stages or publish client material.

## Systems of record

- Google Sheets CRM: identifiable contacts, companies, opportunities and authorised activities.
- Google Drive: editable masters, client inputs, delivery files and permission evidence.
- GitHub: schemas, public-safe templates, deterministic digest engine and validation.
- Linear: programme work, blockers, deadlines and named decisions.

Identifiable CRM records, private Drive links and live provider identifiers must not be copied into public source control.

## Shared master pack

The pack covers:

1. lead qualification;
2. client input request and secure-channel custody;
3. delivery handover and acceptance;
4. optional feedback and exact publication permission;
5. actual time, payment and contribution evidence;
6. customer-discovery interviews;
7. pseudonymous research aggregation.

Each master carries a version identifier and named human-decision fields.

## Weekly management digest

`intelligence/venture_brain/management_digest.py` consumes a bounded JSON snapshot containing pseudonymous or aggregate-safe records. It calculates:

- open, qualified and overdue leads;
- open and weighted pipeline;
- won revenue;
- explicitly confirmed collected cash;
- completed activities;
- actual and estimated delivery hours;
- overdue delivery work;
- failed automations;
- overdue programme issues;
- interview completion, repeated problem codes, referral signals and willingness-to-pay evidence.

The action queue is prioritised but never executed automatically. Each item has `human_decision_required: true`.

## Revenue and cash boundary

A won opportunity is commercial evidence, not payment evidence. Collected cash enters the digest only when both conditions exist:

- `payment_confirmed` is true;
- `collected_eur` is explicitly recorded.

This prevents revenue, invoices and cash from being conflated.

## Customer-discovery boundary

Interviews are research, not sales calls. The operating rules require:

- a human-approved invitation and valid contact basis;
- no recording without explicit permission;
- no confidential records or passwords;
- problem coding before service mapping;
- no proposal during the interview;
- no automatic follow-up;
- pseudonymous aggregate evidence in GitHub-compatible artifacts.

## Safety and privacy

The current repository safety boundary remains public-safe until GitHub reports private visibility. A16 therefore forbids live names, email addresses, phone numbers, recordings, raw transcripts, provider URLs, spreadsheet IDs, credentials and private evidence links in source.

## Validation

Run:

```bash
python scripts/test_operating_launch_system.py
```

Expected result: six passing cases covering exact metrics, cash evidence, human gates, aggregate research, master completeness and the A16 fail-closed contract.

Generate a digest with:

```bash
python scripts/generate_weekly_digest.py snapshot.json --as-of 2026-07-22 --output weekly-management-digest.json
```

## Activation status

Source completion does not mean operational completion. The following remain external or human gates:

- repository privacy verification;
- actual customer-discovery invitations and interviews;
- provider-runtime execution;
- Spanish legal, invoice and tax review;
- proposal issue;
- payment confirmation;
- final delivery release;
- feedback publication permission;
- first paid beta.
