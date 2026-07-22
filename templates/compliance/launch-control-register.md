# Launch compliance and commercial control register

> This is a governance register, not legal advice. It makes unresolved decisions visible and blocks activation until named evidence exists.

## Control status

| Control | Owner | Evidence required | Status | Activation effect |
|---|---|---|---|---|
| Verified business/controller identity | [Name] | Official registration and contact route | BLOCKED | Blocks intake, proposals and invoicing |
| Invoice and tax route | [Name/professional] | Written process and numbering rule | BLOCKED | Blocks paid work |
| Privacy notice | [Name/reviewer] | Approved notice and version | BLOCKED | Blocks real intake |
| Lawful basis and purpose register | [Name/reviewer] | Reviewed processing record | BLOCKED | Blocks real intake |
| Processor/DPA register | [Name] | Contracts and transfer assessment | BLOCKED | Blocks real intake |
| Retention/deletion schedule | [Name] | Approved schedule | BLOCKED | Blocks real intake |
| Rights-request process | [Name] | Procedure and private register location | BLOCKED | Blocks real intake |
| Incident response ownership | [Name] | Escalation route and evidence location | BLOCKED | Blocks real intake |
| Cookie/analytics decision | [Name] | Approved configuration and wording | BLOCKED | Blocks non-essential tracking |
| Proposal terms | [Name/reviewer] | Approved controlled template | DRAFT | Blocks proposal issue |
| Payment/cancellation terms | [Name/reviewer] | Approved wording | BLOCKED | Blocks proposal issue |
| Demonstration labelling | [Name] | Demonstration register and QA | READY | Required for public examples |
| Provider runtime evidence | [Name] | Passing synthetic suite and cleanup | BLOCKED | Blocks public form activation |
| Human activation approval | [Name] | Signed activation record | BLOCKED | Final activation gate |

Allowed status values: `BLOCKED`, `DRAFT`, `READY`, `APPROVED`, `RETIRED`.

## Identity and invoice decision record

| Decision | Value | Evidence location | Reviewer | Date |
|---|---|---|---|---:|
| Trading/legal name | [ ] | [Private] | [ ] | [ ] |
| Legal form | [ ] | [Private] | [ ] | [ ] |
| Registered address | [ ] | [Private] | [ ] | [ ] |
| Public contact address | [ ] | [Private] | [ ] | [ ] |
| Tax/VAT treatment | [ ] | [Private] | [Professional] | [ ] |
| Invoice numbering | [ ] | [Private] | [Professional] | [ ] |
| Payment route | [ ] | [Private] | [ ] | [ ] |
| Refund/cancellation rule | [ ] | [Private] | [Reviewer] | [ ] |

Do not place registration numbers, tax identifiers, bank details or personal addresses in the public repository.

## Website publication matrix

| Surface | Required content | Current source | Reviewer | Publish status |
|---|---|---|---|---|
| Footer | Verified identity and contact route | [ ] | [ ] | BLOCKED |
| Privacy | Approved notice/version | [ ] | [ ] | BLOCKED |
| Cookies | Approved decision and controls | [ ] | [ ] | BLOCKED |
| Legal notice | Jurisdiction-specific wording | [ ] | [ ] | BLOCKED |
| Assessment form | Notice link and version capture | [ ] | [ ] | BLOCKED |
| Service pages | Scope, exclusions, price and revision limit | `schemas/services.json` | Human | DRAFT |
| Demonstrations | Visible fictional/public-example label | Demonstration register | Human | READY |

## Processing register

| Process | Purpose | Data | Lawful basis | Systems | Retention | Human owner | Approved |
|---|---|---|---|---|---|---|---|
| Assessment request | Evaluate and respond | Business contact and request | [Reviewed basis] | Website, CRM, email | [Schedule] | [Name] | No |
| Opportunity management | Manage requested commercial discussion | Contact, company, activities | [Reviewed basis] | CRM, Drive, email | [Schedule] | [Name] | No |
| Service delivery | Produce contracted deliverable | Client inputs and work product | [Reviewed basis] | Drive, approved tools | [Schedule] | [Name] | No |
| Invoicing | Meet contract/statutory obligations | Identity, invoice, payment status | [Reviewed basis] | Approved finance system | [Schedule] | [Name] | No |
| Aggregate operations | Measure workflow reliability | Counts, timings, error categories | [Reviewed basis] | Automation Log | [Schedule] | [Name] | No |

## Processor register

| Provider | Service | Data | Region/transfer | DPA/SCC status | Subprocessors reviewed | Approved |
|---|---|---|---|---|---|---|
| [Provider] | [Service] | [Categories] | [ ] | [ ] | [ ] | No |

## Retention schedule

| Record | Trigger | Active retention | Backup treatment | Deletion/anonymisation owner | Approved |
|---|---|---|---|---|---|
| Unqualified request | Closed/disqualified | [ ] | [ ] | [ ] | No |
| Unsuccessful opportunity | Lost/expired | [ ] | [ ] | [ ] | No |
| Client delivery record | Final delivery | [ ] | [ ] | [ ] | No |
| Invoice/tax record | Invoice date | [Professional decision] | [ ] | [ ] | No |
| Automation evidence | Run date | [ ] | Aggregate only | [ ] | No |
| Security/privacy incident | Incident closure | [Reviewed requirement] | Restricted | [ ] | No |

## Cookie and analytics decision

Until approved, the website may use only strictly necessary local functionality. Non-essential analytics, advertising pixels, behavioural tracking and cross-site identifiers remain disabled.

| Technology | Purpose | Essential | Consent required | Current state | Reviewer |
|---|---|---|---|---|---|
| Theme preference | Remember display choice | [Assess] | [Assess] | Local only | [ ] |
| Language preference | Remember language | [Assess] | [Assess] | Local only | [ ] |
| Analytics | Aggregate usage measurement | No | [Review] | Disabled | [ ] |
| Advertising/retargeting | Marketing | No | Yes | Prohibited | [ ] |

## Human-gated actions

The following actions cannot be performed solely by automation or model output:

- activating real public intake;
- issuing a proposal;
- changing price or commercial terms;
- sending an external commercial message;
- accepting a client or rejecting a request on a significant basis;
- publishing a client name, logo, testimonial or result;
- issuing an invoice or confirming tax treatment;
- making a payment/refund decision;
- final client delivery;
- deleting records subject to unresolved legal retention; and
- promoting a model into production decision-making.

## Activation decision

Activation requires every blocking control to be `APPROVED`, a passing provider-runtime evidence pack, verified cleanup and a named human signature.

| Field | Value |
|---|---|
| Environment | [Website / provider runtime / CRM] |
| Release identifier | [ ] |
| Evidence digest | [ ] |
| Blocking controls remaining | [ ] |
| Approved by | [ ] |
| Approval date | [ ] |
| Rollback owner | [ ] |
| Decision | BLOCKED |
