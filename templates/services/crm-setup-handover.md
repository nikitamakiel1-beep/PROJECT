# CRM & Lead Tracker Setup — controlled handover template

> Service code: `CRM` · Canonical price: €299 · Target delivery: 5 working days · Included revisions: 1

## Control record

| Field | Value |
|---|---|
| Delivery job ID | [ID] |
| Client / demonstration | [Name] |
| System | [Google Sheets / approved platform] |
| Handover date | [YYYY-MM-DD] |
| Prepared by | [Name] |
| Human reviewer | [Name] |
| Template version | CRM-v1 |
| Backup reference | [Private location] |

## Business objective

[Describe the lead-management problem, the people who use the system and the measurable operating outcome.]

**Success indicators:**

- every active lead has one owner;
- every active lead has a next step and due date;
- pipeline value reconciles to open opportunities;
- duplicate creation is controlled;
- overdue work is visible without reading raw notes;
- management can review the system in under 20 minutes per week.

## Scope boundary

Included:

- controlled pipeline definition;
- agreed fields and validation rules;
- configured lead/opportunity tracker;
- management dashboard definitions;
- daily and weekly operating routine;
- import, backup and rollback instructions.

Excluded unless separately agreed:

- migration from unstructured or materially defective data;
- email, WhatsApp or external-message automation;
- accounting, payment or invoice automation;
- regulated profiling or significant automated decisions;
- custom software integrations or API development;
- indefinite support after the handover window.

## Users and ownership

| Role | Named owner | Responsibilities | Access level |
|---|---|---|---|
| CRM owner | [Name] | Definitions, permissions and data quality | Admin |
| Commercial owner | [Name] | Pipeline review and decisions | Edit |
| Lead owner | [Name/role] | Next steps and activity records | Edit |
| Read-only reviewer | [Name/role] | Management reporting | View |

No shared credentials. Access is granted to named accounts and reviewed at handover.

## Pipeline stages

| Stage | Entry condition | Required fields | Exit condition | Maximum age | Terminal |
|---|---|---|---|---:|---|
| New | Valid lead received | Source, owner, consent/version, created date | First review completed | 2 days | No |
| Contacted | Human contact attempted | Activity, next step, due date | Reply or documented sequence completed | 7 days | No |
| Qualified | Need, fit and timing confirmed | Service code, fit, need, timeline | Opportunity created or disqualified | 7 days | No |
| Proposal | Approved proposal issued | Proposal URL, value, expected close | Accepted, rejected or expired | 14 days | No |
| Won | Written acceptance and payment gate satisfied | Won date, payment/invoice status | Delivery job created | 2 days | Yes |
| Lost | Opportunity ended unsuccessfully | Lost date, loss reason | None | — | Yes |
| Disqualified | Lead is not currently suitable | Reason and review date | None | — | Yes |

Stage names may be adapted, but entry/exit conditions and terminal states must remain explicit.

## Required fields

### Leads

| Field | Required when | Validation |
|---|---|---|
| Lead ID | Always | Unique and immutable |
| Company ID | Business identified | Existing company or controlled creation |
| Contact ID | Contact identified | Existing contact or controlled creation |
| Source | Always | Approved list |
| Consent version | Public intake | Effective approved version |
| Status | Always | Approved status list |
| Service interest | When known | Active canonical service code |
| Owner | Active lead | Named user |
| Next step | Active lead | Concrete action |
| Next step date | Active lead | Valid date |
| Fit / qualification evidence | Qualified | Factual notes or structured fields |

### Opportunities

| Field | Required when | Validation |
|---|---|---|
| Opportunity ID | Always | Unique and immutable |
| Service code | Always | Active canonical service |
| Stage | Always | Approved pipeline stage |
| Value € | Proposal onward | Canonical price or approved exception |
| Probability % | Open opportunity | Controlled range and definition |
| Weighted value € | Open opportunity | Formula: value × probability |
| Expected close | Open opportunity | Valid date |
| Proposal URL | Proposal onward | Private controlled link |
| Loss reason | Lost | Approved reason list |
| Delivery status | Won onward | Approved status list |

## Duplicate-control rules

1. Search exact work email before creating a contact.
2. Search normalised company domain and company name before creating a company.
3. Search open leads for the same contact, company and service before creating a lead.
4. Preserve human-curated records; automation may add evidence but must not overwrite conflicting identity or commercial fields.
5. Log duplicate decisions without copying raw personal data into automation logs.
6. Merge only after human review where records differ materially.

## Follow-up rules

- Active leads and open opportunities require an owner, next step and due date.
- Future dates are not overdue.
- Terminal records are excluded from active follow-up views.
- The daily digest may rank internal work but must not send an external message automatically.
- High commercial value does not override consent, legal or quality gates.
- Repeated failed contact follows the approved contact policy; no mass unsolicited email.

## Dashboard definitions

| KPI | Definition | Source | Reconciliation check |
|---|---|---|---|
| Leads added | Leads created in period | Leads | Count IDs |
| Qualified leads | Leads entering Qualified in period | Leads/Activities | Stage-change evidence |
| Open pipeline | Sum of values for open opportunities | Opportunities | Exclude terminal stages |
| Weighted pipeline | Sum of value × probability | Opportunities | Recalculate sample |
| Won revenue | Sum of won opportunity value | Opportunities | Match won dates |
| Collected cash | Confirmed payment records | Approved finance record | Do not infer from Won |
| Overdue actions | Active records with past due date | Leads/Opportunities | Exclude terminal/future |
| Delivery hours | Actual completed delivery time | Delivery jobs/Activities | Match handover records |

## Data-quality rules

- IDs are immutable.
- Dates use `YYYY-MM-DD` internally.
- Currency values are numeric; symbols belong in display formatting.
- Status and service values use controlled lists.
- Raw passwords, payment-card data and special-category personal data are prohibited.
- Notes record facts, decisions and next steps; they do not become an uncontrolled document store.
- Each automation run records outcome, count and error category without raw personal data.

## Daily operating routine

1. Review the overdue follow-up digest.
2. Resolve records with missing owner, next step or date.
3. Record completed activities on the same day.
4. Update stage only when the entry condition is evidenced.
5. Escalate duplicate, consent, privacy or payment ambiguity to the human owner.
6. Do not trigger external messages from the digest.

Target time: 10–15 minutes.

## Weekly management review

1. Reconcile open and weighted pipeline.
2. Review stage age and overdue actions.
3. Review lost/disqualified reasons for patterns.
4. Review delivery capacity, actual hours and revision counts.
5. Review failed automations and unresolved incidents.
6. Decide the next three commercial actions and assign owners/dates.

Target time: 20–30 minutes.

## Import procedure

1. Make a timestamped backup.
2. Preserve the source file unchanged.
3. Map source columns to the controlled contract.
4. Validate required fields and controlled values.
5. Run duplicate analysis before insertion.
6. Import into a disposable copy first.
7. Reconcile record counts and a sample of values.
8. Obtain human approval before production import.

## Backup and rollback

- Backup before schema, formula, validation, automation or bulk-data changes.
- Record backup timestamp, operator, reason and restoration instructions.
- Test restoration in a disposable copy.
- A failed automation must not leave partial row creation, duplicate logs or corrupted formulas.
- Rollback does not substitute for incident assessment where information was exposed externally.

## Handover exercise

The client operator must demonstrate:

- creating one test lead;
- progressing it through one valid stage change;
- recording an activity and next step;
- creating an opportunity;
- finding an overdue action;
- reconciling one dashboard KPI; and
- locating the backup and recovery instructions.

## Acceptance and open actions

| Item | Owner | Due date | Status |
|---|---|---:|---|
| [Action] | [Name] | [Date] | Open/Done/Blocked |

- [ ] Pipeline definitions approved.
- [ ] Required fields and controlled lists approved.
- [ ] Duplicate tests passed.
- [ ] Dashboard sample reconciled.
- [ ] Backup and restore procedure evidenced.
- [ ] Handover exercise completed.
- [ ] Client access reviewed.
- [ ] External automation remains disabled unless separately approved.
