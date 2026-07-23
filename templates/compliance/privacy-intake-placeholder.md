# Assessment-request privacy notice — controlled approval template

> **Not approved legal text.** This document is an implementation checklist and drafting scaffold. It must be completed and reviewed for the actual controller identity, jurisdiction, business model and processing before any real public intake is activated.

## Control record

| Field | Value |
|---|---|
| Notice version | assessment-v1-2026-07 |
| Status | DRAFT — ACTIVATION BLOCKED |
| Controller identity | [Not yet verified] |
| Reviewer | [Name / professional role] |
| Approval date | [YYYY-MM-DD] |
| Effective date | [YYYY-MM-DD] |
| Superseded version | [None / version] |
| Evidence location | [Private controlled location] |

## Required published information

The approved notice must state, in clear language:

1. the controller's verified legal identity and contact route;
2. the specific purposes for collecting an assessment request;
3. the lawful basis relied upon for each purpose;
4. which fields are required and which are optional;
5. recipients and processors, including hosting, email, CRM and automation providers;
6. whether data leaves the EEA and the applicable transfer safeguard;
7. the retention period or objective retention criteria;
8. the rights available to the person and how to exercise them;
9. the right to complain to the competent supervisory authority;
10. whether automated decision-making or profiling occurs and its practical effect; and
11. the effective notice version captured with each submission.

## Current intended processing boundary

This boundary is a technical design constraint, not a completed legal assessment.

- Purpose: receive and respond to a voluntarily submitted business assessment request.
- Data minimisation: business contact name, work email, company, website, selected service, brief business need, language, consent version and submission timestamp.
- Prohibited through public intake: passwords, credentials, payment-card data, government identifiers, health data, political/religious data, biometric data, criminal data or other special-category information.
- Initial automation: validate fields, create or update controlled CRM records with duplicate safety, log aggregate execution evidence and route the request for human review.
- No automatic sale, rejection, price change, external message or binding decision.
- No model output may be presented as a legal, credit, employment or similarly significant decision.

## Field-level register

| Field | Required | Purpose | Retention trigger | Public-safe log |
|---|---|---|---|---|
| Contact name | Yes | Respond to request | [Approved schedule] | No |
| Work email | Yes | Respond to request | [Approved schedule] | No |
| Company | Yes | Identify business context | [Approved schedule] | No |
| Website | Optional | Perform requested review | [Approved schedule] | Domain only if approved |
| Service code | Yes | Route request | [Approved schedule] | Aggregate only |
| Business need | Yes | Understand request | [Approved schedule] | No raw text |
| Language | Yes | Respond appropriately | [Approved schedule] | Aggregate only |
| Consent version | Yes | Evidence notice shown | Same as submission | Version only |
| Timestamp | Yes | Operational record | Same as submission | Aggregate only |

## Consent and acknowledgement wording control

The form must not use a pre-ticked checkbox. The approved acknowledgement must:

- link to the effective privacy notice;
- state that the user is requesting contact about the submitted business need;
- avoid bundling unrelated marketing permission;
- identify optional marketing consent separately, if introduced later; and
- capture the exact notice/consent version in the submission record.

**Controlled placeholder:**

> I have read the privacy notice and request contact regarding this assessment. I understand that my information will be used to evaluate and respond to this request.

This wording remains blocked until reviewed and approved.

## Processor and transfer register

| Service | Role | Data categories | Region/transfer | Contract/DPA status | Approved |
|---|---|---|---|---|---|
| Website host | [Processor] | [Fields] | [Region] | [Status] | [No] |
| Google Workspace | [Processor] | [Fields] | [Region] | [Status] | [No] |
| CRM/automation | [Processor] | [Fields] | [Region] | [Status] | [No] |
| Email provider | [Processor] | [Fields] | [Region] | [Status] | [No] |

## Retention and deletion decisions

Activation requires an approved schedule covering at least:

- unqualified or abandoned assessment requests;
- active opportunities;
- unsuccessful proposals;
- clients and delivery records;
- invoices and records subject to statutory retention;
- automation logs and security evidence;
- backups; and
- rights requests and deletion evidence.

Deletion must remove or irreversibly anonymise data from active systems while respecting legally required records and documented backup cycles.

## Rights-request procedure

1. Verify the requester's identity proportionately.
2. Record request type and received date in a private register.
3. Search the CRM, Drive, email and approved processors.
4. Apply legal exceptions only after appropriate review.
5. Respond through a verified channel.
6. Record completion, systems affected and residual backup treatment.
7. Never place the requester's identity or request contents in the public repository.

## Incident escalation

Any suspected unauthorised access, misdirected delivery, leaked credential, exposed spreadsheet ID, public provider URL or personal-data commit must:

1. stop the affected workflow;
2. preserve minimum necessary evidence;
3. revoke or rotate access where applicable;
4. notify the designated privacy/security owner;
5. assess notification obligations; and
6. document remediation outside the public repository.

## Activation gate

Real submissions remain disabled until every item below is complete:

- [ ] Controller identity verified.
- [ ] Purpose and lawful basis reviewed.
- [ ] Effective privacy wording approved.
- [ ] Processor/DPA and transfer register approved.
- [ ] Retention schedule approved.
- [ ] Rights and incident procedures assigned.
- [ ] Cookie/analytics decision approved.
- [ ] Form captures the effective version.
- [ ] Public website displays the approved notice.
- [ ] Provider runtime passes synthetic testing and cleanup.
- [ ] A named human signs the activation record.
