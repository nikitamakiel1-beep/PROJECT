# CRM & Lead Tracker Setup — Archipelago Design Studio

> **Demonstration — fictional business and synthetic records. Not a client result.**

**Demo ID:** DEMO-CRM-001  
**Service code:** CRM  
**Canonical price:** €299  
**Fictional handover date:** 2026-07-22

## Fictional business brief

Archipelago Design Studio is a five-person multilingual design consultancy that receives enquiries through referrals, website forms and professional networks. The synthetic starting point is a shared spreadsheet with inconsistent stages, duplicated companies and no reliable next-step dates.

## Business objective

Create one practical operating system that allows the studio to:

- assign every active lead to one owner;
- see overdue work immediately;
- separate leads from opportunities;
- calculate open and weighted pipeline consistently;
- preserve referral source evidence; and
- complete a weekly review in under 30 minutes.

## Controlled pipeline

| Stage | Entry condition | Exit condition | Maximum age | Terminal |
|---|---|---|---:|---|
| New | Valid enquiry created | Human review completed | 2 days | No |
| Contacted | First response or attempt logged | Reply or approved sequence completed | 7 days | No |
| Qualified | Need, budget/fit, timing and decision context recorded | Opportunity created or disqualified | 7 days | No |
| Proposal | Approved proposal issued | Accepted, rejected or expired | 14 days | No |
| Won | Written acceptance and payment gate satisfied | Delivery job created | 2 days | Yes |
| Lost | Opportunity ended unsuccessfully | — | — | Yes |
| Disqualified | Not suitable or not ready | — | — | Yes |

## Synthetic lead register

All names and domains are fictional.

| Lead ID | Company | Source | Service | Status | Owner | Next step | Due date |
|---|---|---|---|---|---|---|---:|
| L-DEMO-001 | Meridian Foods Example | Referral | IVA | Qualified | Owner A | Confirm website-review scope | 2026-07-24 |
| L-DEMO-002 | Luma Atelier Example | Website | IOP | Contacted | Owner B | Send discovery questions | 2026-07-23 |
| L-DEMO-003 | North Quay Labs Example | Network | CRM | New | Owner A | Review request | 2026-07-22 |
| L-DEMO-004 | Meridian Foods Example | Referral | IVA | Disqualified | Owner A | None | — |

`L-DEMO-004` is retained as a terminal historical record. It must not appear in active overdue views.

## Synthetic opportunities

| Opportunity ID | Lead | Service | Stage | Value € | Probability % | Weighted € | Expected close | Next step |
|---|---|---|---|---:|---:|---:|---:|---|
| O-DEMO-001 | L-DEMO-001 | IVA | Proposal | 149 | 60 | 89.40 | 2026-07-29 | Review proposal response |
| O-DEMO-002 | L-DEMO-002 | IOP | Qualified | 249 | 35 | 87.15 | 2026-08-05 | Confirm target market |
| O-DEMO-003 | Historical | CRM | Lost | 299 | 0 | 0.00 | 2026-07-10 | None |

**Open pipeline:** €398  
**Weighted pipeline:** €176.55

The lost opportunity is excluded from both values.

## Duplicate-control example

A second form submission arrives for `Meridian Foods Example` with the same normalised domain and service code.

Expected behaviour:

1. reuse the existing Company record;
2. reuse or human-review the existing Contact match;
3. do not create a second active IVA lead;
4. append a new Activity to `L-DEMO-001`;
5. preserve the existing owner and proposal fields;
6. log an aggregate duplicate decision without raw contact data.

## Required fields

### Lead minimum

- Lead ID
- Company ID
- Contact ID where known
- Source
- Consent/version where applicable
- Status
- Service interest
- Owner
- Next step
- Next step date
- Created date

### Opportunity minimum

- Opportunity ID
- Company/Contact/Lead linkage
- Service code
- Stage
- Value
- Probability
- Weighted value
- Expected close
- Owner
- Next step and date
- Proposal reference from Proposal onward
- Loss reason when Lost

## Dashboard demonstration

| KPI | Result | Reconciliation |
|---|---:|---|
| Active leads | 3 | Excludes Disqualified |
| Qualified leads | 1 | `L-DEMO-001` |
| Open opportunities | 2 | Excludes Lost |
| Open pipeline | €398.00 | 149 + 249 |
| Weighted pipeline | €176.55 | 89.40 + 87.15 |
| Overdue active actions on 2026-07-23 | 1 | `L-DEMO-003` due 2026-07-22 |
| Won revenue | €0.00 | No Won record |
| Collected cash | €0.00 | Never inferred from proposal or Won |

## Daily routine demonstration

1. Review overdue active records.
2. Assign an owner to any active record missing one.
3. Complete the concrete next step and record an Activity.
4. Update the stage only when its exit condition is evidenced.
5. Set the next action and due date before leaving the record.
6. Escalate duplicate, consent or price ambiguity to the human CRM owner.

## Weekly review demonstration

- reconcile open/weighted pipeline;
- review all records older than stage maximum;
- inspect lost/disqualified reasons;
- review upcoming delivery capacity;
- inspect failed automations and unresolved data-quality issues;
- assign three next commercial decisions with owners and dates.

## Backup and rollback demonstration

Before bulk import or schema changes:

1. create timestamped spreadsheet backup;
2. export the source unchanged;
3. test mapping in a disposable copy;
4. reconcile record count and sample values;
5. verify formulas and validations;
6. obtain human approval;
7. retain restoration instructions.

A failed import must restore the pre-run snapshot and produce an aggregate error record. Partial row creation is not accepted.

## Handover exercise

The fictional operator completes these tasks:

- creates `L-DEMO-005` using controlled values;
- logs one activity;
- moves it to Contacted with evidence;
- creates an opportunity only after qualification;
- identifies the overdue record;
- reconciles weighted pipeline;
- locates the backup procedure.

## Acceptance result

| Check | Result |
|---|---|
| Pipeline entry/exit definitions | Passed |
| Required fields | Passed |
| Duplicate scenario | Passed in design demonstration |
| Dashboard reconciliation | Passed |
| Backup/rollback instructions | Passed |
| External messaging automation | Disabled |
| Human stage/price custody | Retained |

## Limitations

This document demonstrates a controlled CRM design using synthetic records. It is not evidence of a real implementation, client adoption, conversion improvement or revenue result. A real delivery requires platform-specific configuration, access review, backup evidence and client handover.

> **End label: fictional demonstration. No client records or measured commercial result are represented.**
