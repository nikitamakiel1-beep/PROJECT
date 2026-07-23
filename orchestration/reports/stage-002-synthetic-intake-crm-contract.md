# Stage 002 report — synthetic intake-to-CRM contract

## Outcome

Stage 002 established a deterministic, synthetic-only website-intake contract aligned with the live Google Sheets CRM structure. The public website remains in demonstration mode with no endpoint. Operational records are idempotent by `submission_id`, existing company and contact rows are never overwritten, and an injected write failure produces no partial operational records in the local transaction harness.

The Drive CRM headers were read directly on 21 July 2026 and captured in `schemas/crm/sheets-contract.json`. A disposable copy named `TEST — A01 Synthetic Intake — 2026-07-21` was created under `05 Automation & Integrations`. One synthetic geometry row was written to Companies, Contacts, Leads, Activities and Automation Log, read back successfully, and then deleted. The production CRM was not mutated.

The Apps Script web-app itself was not deployed from the original execution environment because no Apps Script deployment action was available. That provider-runtime test is the explicit Stage 003 gate.

## Files changed

- Added `schemas/crm/sheets-contract.json` with exact headers and deterministic matching rules.
- Added `automations/google-apps-script/IntakeCore.gs`, a pure validation, matching, planning and logging engine.
- Replaced `automations/google-apps-script/Code.gs` with a synthetic-only adapter using script locking, exact header checks, precomputed writes and reverse-row rollback.
- Expanded `schemas/crm/lead.schema.json` with optional role and phone fields.
- Added `scripts/intake_contract_harness.js` and `scripts/test_intake_contract.py`.
- Added `docs/workflows/INTAKE_TO_CRM_MAPPING.md`.
- Reworked `automations/google-apps-script/DEPLOYMENT.md` and added `SYNTHETIC_TEST.md`.
- Reworked `automations/specs/A01-intake-to-crm.yaml`.
- Updated CI, repository validation, README and manifest in the complete Stage 003-ready package.

## Tests and evidence

Local automated checks passed:

```bash
node scripts/intake_contract_harness.js
python scripts/test_intake_contract.py
python scripts/validate_repository.py
python scripts/test_web.py
node --check apps/web/assets/app.js
python scripts/orchestrator.py validate
```

The synthetic harness passed nine cases:

| Case | Expected operational effect | Actual result |
|---|---|---|
| New submission | +1 company, contact, lead and activity | Passed |
| Exact retry | No new operational rows; duplicate log | Passed |
| Existing company/new contact | Reuse company; create contact, lead and activity | Passed |
| Existing contact | Preserve contact/company; create lead and activity | Passed |
| Malformed email | No operational rows; rejected log | Passed |
| Missing required field | No operational rows; rejected log | Passed |
| Invalid service code | No operational rows; rejected log | Passed |
| Injected Leads write failure | All operational writes rolled back; failed log | Passed |
| Partial historical rows | Reuse deterministic rows; create missing lead/activity | Passed |

Disposable Google Sheets geometry evidence:

| Sheet | Synthetic ID | Columns written/read | Result |
|---|---|---:|---|
| Companies | `COM-C017CF09` | 20 | Passed |
| Contacts | `CON-A83F5682` | 16 | Passed |
| Leads | `LEAD-1CE1449B` | 22 | Passed |
| Activities | `ACT-1CE1449B` | 16 | Passed |
| Automation Log | `LOG-252A56E4` | 12 | Passed |

The first Drive batch was rejected atomically before mutation because the generated Companies row had 21 values for a 20-column contract. The row generator was corrected, the second batch passed, and all five smoke-test rows were subsequently deleted. This was useful evidence that the provider enforces row geometry and that no partial writes occurred from the rejected multi-request batch.

## Business or operational effect

The venture now has a reproducible intake architecture rather than an ad hoc form-to-sheet append. Retry behavior, matching precedence, data preservation, error codes, logging fields and rollback are documented and executable without real personal data.

The same company or contact can be recognised deterministically. Existing human-curated company and contact fields are preserved because intake is create-only for those tables. A conflicting submitted company attached to an existing contact email creates a warning and uses the existing relationship rather than silently moving the contact.

## Risks and unresolved items

- The Apps Script provider runtime has not yet been executed. Stage 003 must execute the exact HTTP cases against the clean disposable spreadsheet.
- Google Sheets does not provide true multi-sheet transactions. Script locking, deterministic IDs, append tracking and reverse deletion are compensating controls, not a database transaction.
- Anonymous/public endpoint access, abuse controls, retention, privacy wording and production consent remain unapproved.
- `ACTIVE_SERVICE_CODES` is a deployment property generated from the canonical service catalogue. Stage 003 must verify the configured value.
- The dedicated repository now exists as `nikitamakiel1-beep/PROJECT`; Stage 003 source is isolated on `venture/stage-003-provider-runtime`. The repository is currently public, so no IDs, URLs, credentials, CRM exports or personal data may be committed.

## Rollback

Keep the public website in demonstration mode with a blank endpoint. Disable or delete any disposable Apps Script deployment. Delete synthetic rows or delete/archive the disposable spreadsheet. Revert `IntakeCore.gs`, `Code.gs`, contract/schema files and tests if the new contract is rejected. Do not point the website at any endpoint during rollback.

## Next instruction

`orchestration/instructions/stage-003-provider-runtime-and-activation-gate.md`
