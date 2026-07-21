# Stage 003 instruction — provider runtime and activation gate

## Objective

Execute the synthetic A01 intake through an actual disposable Google Apps Script web-app deployment, reconcile provider behavior with the local contract, and produce a documented go/no-go decision for any later private endpoint integration. Do not enable public or real-data intake.

## Evidence from previous stage

- The pure intake engine passed nine synthetic cases and preserves deterministic idempotency, human-curated company/contact data and rollback behavior.
- The exact live CRM header contract was captured and a disposable Google Sheets copy accepted and returned correctly shaped synthetic rows.
- A malformed 21-column test row was rejected atomically before mutation, proving that provider geometry checks matter.
- The unresolved risk is Apps Script runtime behavior: deployment properties, locks, `doPost`, rollback and web-app responses have not been exercised on the provider.

## Read first

- `orchestration/reports/stage-002-synthetic-intake-crm-contract.md`
- `automations/google-apps-script/IntakeCore.gs`
- `automations/google-apps-script/Code.gs`
- `automations/google-apps-script/DEPLOYMENT.md`
- `automations/google-apps-script/SYNTHETIC_TEST.md`
- `schemas/crm/sheets-contract.json`
- `docs/workflows/INTAKE_TO_CRM_MAPPING.md`
- `docs/architecture/AUTOMATION_BOUNDARIES.md`
- `docs/architecture/DATA_CLASSIFICATION.md`

## Work

1. Use the clean disposable CRM copy stored under `05 Automation & Integrations`; do not use the production CRM.
2. Create a bound Apps Script project and install `IntakeCore.gs` and `Code.gs` exactly from source.
3. Configure `SPREADSHEET_ID`, `CONSENT_VERSION`, `ACTIVE_SERVICE_CODES`, `OWNER_NAME` and `SYNTHETIC_ONLY=true` outside source control.
4. Deploy the narrowest-access test web app that permits synthetic HTTP execution.
5. Execute every case in `SYNTHETIC_TEST.md`, including exact retry and an injected write failure. Record only submission IDs, correlation IDs, deterministic record IDs, row counts, result codes and rollback evidence.
6. Compare provider results with the nine local harness results. Fix source and tests for any divergence; do not explain away mismatches.
7. Verify the web app returns parseable JSON for accepted, duplicate, rejected and failed outcomes.
8. Confirm the production CRM remains unchanged and the public website remains `demoMode: true` with no endpoint.
9. Disable the test deployment after evidence capture and remove all synthetic rows, or archive/delete the disposable spreadsheet according to the rollback procedure.
10. Produce a go/no-go decision. A `go` means only that private synthetic integration may be prepared later; it does not authorise public or real-data activation.

## Acceptance criteria

- All documented provider-level synthetic cases have row-count and result evidence.
- Exact retry creates no duplicate company, contact, lead or activity.
- Invalid payloads create no operational rows and produce stable rejected codes.
- Injected write failure leaves no operational rows from that attempt and produces a failed log where possible.
- Provider output matches the local contract or all divergences are corrected and retested.
- No deployment URL, spreadsheet ID, secret or synthetic contact data is committed.
- Test deployment is disabled after evidence capture.
- Production CRM and public website remain untouched.
- Repository, website, intake and orchestration validations pass.

## Tests

Run at minimum:

```bash
python scripts/validate_repository.py
python scripts/test_web.py
python scripts/test_intake_contract.py
node --check apps/web/assets/app.js
python scripts/orchestrator.py validate
```

Also execute the full provider test table in `automations/google-apps-script/SYNTHETIC_TEST.md` and reconcile it to the local harness evidence.

## Exclusions

- No real prospect data.
- No production CRM writes.
- No public website endpoint.
- No anonymous production deployment approval.
- No external email or WhatsApp automation.
- No service-menu expansion.
- No migration away from Google Sheets.

## Human approvals

- A human must authorise the Apps Script deployment/access setting and execute or supervise the provider-level requests.
- A human must review the evidence and approve the go/no-go outcome.
- Privacy, retention, legal wording, invoicing and real-data activation remain separate future gates.

## Required handoff

Create:

1. `orchestration/reports/stage-003-provider-runtime-and-activation-gate.md`
2. `orchestration/instructions/stage-004-<evidence-based-slug>.md`
3. Updated `orchestration/state.json`
4. Updated `orchestration/CURRENT.md`
5. A rollback record confirming deployment disablement and synthetic-data cleanup
