# Stage 002 instruction — synthetic intake-to-CRM contract

## Objective

Prove the complete assessment-to-CRM data path using synthetic records only, with deterministic duplicate protection, explicit logging and a human approval gate before any real public endpoint is enabled.

## Evidence from previous stage

- Stage 001 established a stable assessment payload and one canonical `service_code` catalogue.
- The website now has explicit local success and failure states, HTTPS endpoint enforcement and a configurable request timeout.
- Real collection remains disabled in `apps/web/config.js`.
- The principal unresolved risk is not website presentation; it is proving that the Apps Script and CRM mapping are idempotent, recoverable and aligned with the current Google Sheets structure.

## Read first

- `orchestration/reports/stage-001-website-foundation.md`
- `apps/web/assets/app.js`
- `apps/web/config.js`
- `schemas/crm/lead.schema.json`
- `schemas/services.json`
- `automations/google-apps-script/Code.gs`
- `automations/google-apps-script/DEPLOYMENT.md`
- `automations/specs/A01-intake-to-crm.yaml`
- `docs/architecture/AUTOMATION_BOUNDARIES.md`
- `docs/architecture/DATA_CLASSIFICATION.md`

## Work

1. Compare the website payload, lead JSON schema, Apps Script field mapping and current Drive CRM column contract; remove or document every mismatch.
2. Refactor the Apps Script intake handler so retries with the same `submission_id` cannot create duplicate lead, activity, company or contact records.
3. Preserve higher-quality human-entered CRM data when a synthetic retry contains blank or lower-quality values.
4. Log each accepted, duplicate, rejected and failed synthetic request in the Automation Log contract, including a correlation identifier and recoverable error description.
5. Add a local test harness that exercises valid new submission, exact retry, existing company/new contact, existing contact, malformed email, missing field, invalid service code and spreadsheet-write failure.
6. Add a synthetic-only deployment configuration and document the exact manual Apps Script/Sheets steps required to test against a disposable spreadsheet or dedicated test tabs.
7. Keep the public website in demonstration mode. Do not add a production endpoint to source control.
8. Produce an evidence table mapping every test case to expected CRM effects and actual result.

## Acceptance criteria

- Website payload fields and CRM columns have a documented one-to-one mapping.
- The same `submission_id` produces no duplicate operational records on retry.
- Matching rules for company and contact are deterministic and documented.
- Invalid or unsupported submissions are rejected without partial writes.
- Every attempt creates or updates a traceable synthetic automation-log record.
- The local synthetic test harness passes without requiring real personal data.
- No secret, spreadsheet ID or live endpoint is committed.
- `apps/web/config.js` remains in demonstration mode.
- Repository, website and orchestration validation all pass.

## Tests

Run at minimum:

```bash
python scripts/validate_repository.py
python scripts/test_web.py
python scripts/test_intake_contract.py
node --check apps/web/assets/app.js
python scripts/orchestrator.py validate
```

Also execute the documented synthetic Apps Script test procedure against a disposable spreadsheet or dedicated test tabs and record row-level evidence without including personal data in GitHub.

## Exclusions

- No real prospect collection.
- No public endpoint activation.
- No automatic external email or WhatsApp message.
- No production spreadsheet mutation.
- No migration away from Google Sheets.
- No expansion of the service menu.

## Human approvals

- A human must create or designate the disposable Google Sheets test environment and deploy the Apps Script test web app.
- A human must review synthetic test evidence before any endpoint is inserted into website configuration.
- Privacy wording, invoicing readiness and the first real-data activation remain separate compliance gates.

## Required handoff

Create:

1. `orchestration/reports/stage-002-synthetic-intake-crm-contract.md`
2. `orchestration/instructions/stage-003-<evidence-based-slug>.md`
3. Updated `orchestration/state.json`
4. Updated `orchestration/CURRENT.md`
5. A rollback note that disables the endpoint and identifies any synthetic rows or test tabs to remove
