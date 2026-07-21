# Disposable-sheet synthetic test procedure

Use the fictional domain `example.test`. Never enter real names, addresses or telephone numbers.

## A01 intake matrix

| Case | Expected Companies | Contacts | Leads | Activities | Log result |
|---|---:|---:|---:|---:|---|
| New submission | +1 | +1 | +1 | +1 | accepted |
| Exact retry | +0 | +0 | +0 | +0 | duplicate |
| Existing company / new contact | +0 | +1 | +1 | +1 | accepted |
| Existing contact | +0 | +0 | +1 | +1 | accepted |
| Malformed email | +0 | +0 | +0 | +0 | rejected |
| Missing company | +0 | +0 | +0 | +0 | rejected |
| Invalid service | +0 | +0 | +0 | +0 | rejected |
| Injected write failure | +0 after rollback | +0 | +0 | +0 | failed |

For each request, record only:

- submission ID;
- correlation ID;
- result;
- deterministic company/contact/lead/activity IDs;
- before and after row counts;
- retry count;
- rollback outcome.

Do not copy the request body or synthetic contact fields into the stage report.

## A02 internal digest matrix

| Case | Expected result |
|---|---|
| Overdue Leads and Opportunities | Ranked internal digest created |
| Future action date | Excluded |
| Terminal status or stage | Excluded |
| Same-day rerun | Duplicate, no second accepted run |
| Automation Log failure | Prior digest restored |
| External messaging | Always zero |

Record only aggregate counts, owners, priorities, duplicate status and rollback outcome.

## A06 neural provider bridge matrix

| Case | Expected result |
|---|---|
| Qualified Lead, Fit Score ≥60, active service | One PII-free package |
| Legacy `OSP` service code | Canonical package code `IOP` |
| Name, email, phone, URL and notes | Absent from Export JSON |
| Same Lead, service and date | Same Package ID and feature digest |
| Low-fit or non-qualified Lead | No package |
| Existing matching Opportunity | No package |
| Modified feature after export | Python rejects feature digest mismatch |
| Added personal-data field | Python rejects package |
| `synthetic_only=false` | Python rejects package |
| Valid package | Deterministic shadow decision |
| Imported decision with mutation allowed | Apps Script rejects decision |
| Imported decision with communication allowed | Apps Script rejects decision |

Record only:

- Package ID;
- pseudonymous Lead/Company/Contact references;
- canonical Service Code;
- feature digest;
- model version;
- decision digest;
- confidence and uncertainty;
- bounded-auto eligibility;
- row counts and status transitions.

Do not record raw queue mappings outside the disposable spreadsheet.

## A03 bounded internal Opportunity matrix

Run only after the A06 export/inference/import chain passes.

| Case | Expected Opportunities | Lead link | Queue status |
|---|---:|---|---|
| Gate disabled | +0 | unchanged | Decision Ready |
| Confidence <0.72 | +0 | unchanged | Review required |
| Uncertainty >0.28 | +0 | unchanged | Review required |
| Eligible bounded decision | +1 | deterministic Opportunity ID | AUTO_APPLIED |
| Same decision rerun | +0 | unchanged | Duplicate preserved |
| Existing Lead link | +0 | preserved | Existing link preserved |
| Injected later write failure | +0 after rollback | previous value restored | Not applied |
| External messages | 0 | n/a | n/a |

After testing, remove `A03_BOUNDED_WRITE_ENABLED`, disable the web app and confirm the production CRM remained unchanged.
