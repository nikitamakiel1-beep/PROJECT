# Launch control pack architecture

## Purpose

The launch control pack converts launch-readiness from an informal checklist into a source-controlled, regression-tested contract. It connects the canonical service catalogue to commercial proposals, delivery templates, demonstrations, privacy controls and the Stage 003 provider evidence gate.

It does not provide approved legal wording and does not activate any real workflow.

## Control layers

### 1. Canonical service truth

`schemas/services.json` remains the source for service codes, active status, prices, target delivery days and revision limits. Service templates and demonstrations must reproduce those values exactly.

### 2. Commercial custody

`templates/commercial/proposal.md` records scope, exclusions, inputs, timing, acceptance, payment, revisions, data boundary, cancellation and approvals.

`templates/commercial/commercial-terms-control.md` identifies the jurisdiction-specific decisions that remain blocked before paid work.

No proposal is valid merely because a Markdown template exists. The actual business identity, invoice route and contractual wording require human verification.

### 3. Delivery custody

The IVA, CRM and IOP templates define reproducible delivery methods and objective acceptance checks. `templates/commercial/quality-checklist.md` blocks final delivery when critical or high defects remain.

### 4. Demonstration custody

The demonstration register and three service examples provide proof of method without representing real clients. Each artifact is fictional, synthetic and repeatedly labelled. Public derivatives must preserve that label.

### 5. Privacy and activation custody

The privacy template and launch-control register keep unresolved controller identity, lawful basis, processors, transfers, retention, rights, incident and cookie decisions visible.

Real intake remains disabled until every blocking control has approved evidence.

### 6. Provider custody

`docs/setup/STAGE_003_PROVIDER_ACTIVATION_RUNBOOK.md` defines installation, property configuration, A01/A02 execution, neural-shadow evidence, evidence compilation, cleanup and advancement criteria.

Source-level tests cannot advance the stage. Actual disposable-provider evidence and verified cleanup are required.

## Public-repository boundary

While GitHub reports the repository as public, the following must never be committed:

- personal or client data;
- live spreadsheet IDs;
- Apps Script deployment URLs;
- Script Property values;
- business registration or tax identifiers;
- bank or payment details;
- credentials or tokens;
- private evidence links;
- real provider submissions/responses;
- unapproved client names, logos, testimonials or results.

The pack therefore uses placeholders, aggregate evidence and reserved `.example` domains.

## Validation

`python scripts/test_launch_control_pack.py` enforces:

1. service-template price, delivery and revision consistency;
2. human-gated proposal and QA controls;
3. privacy/commercial activation blocking;
4. complete fictional demonstration labelling and public safety; and
5. Stage 003 provider evidence and cleanup requirements.

The test is additive to the repository safety scanner and existing A01/A02/provider tests.

## Systems of record

| Information | System of record |
|---|---|
| Service codes, prices and source templates | GitHub |
| Client identity, accepted inputs and completed checklists | Private Drive/client folder |
| Lead, opportunity and delivery state | CRM |
| Work, blockers and evidence links | Linear |
| Invoice, tax and payment records | Approved finance route outside source control |
| Provider properties and deployment configuration | Bound Apps Script environment |

## Human gates

A named human remains responsible for:

- legal/privacy/commercial approval;
- proposal issue;
- price exceptions;
- external communication;
- client/publication permissions;
- final delivery;
- provider activation evidence acceptance;
- model promotion; and
- stage advancement.

## Completion semantics

This pack can be `source_complete` while the venture remains `activation_blocked`. Completing a template or demonstration is not equivalent to legal approval, provider execution, customer discovery, sale, payment or delivery proof.
