# Deploy A01 in synthetic-only mode

Do not connect this deployment to the public website during Stage 002.

## 1. Create the disposable environment

1. Duplicate the venture CRM spreadsheet and name it `TEST — A01 Synthetic Intake — YYYY-MM-DD`.
2. Store it in `05 Automation & Integrations`.
3. Confirm the copy contains the exact headers in `schemas/crm/sheets-contract.json`.
4. Use only `.test` addresses and fictional names. Do not copy real CRM rows into the test file.

## 2. Create Apps Script

1. Open the disposable spreadsheet.
2. Extensions → Apps Script.
3. Create two server files and copy the repository contents:
   - `IntakeCore.gs`
   - `Code.gs`
4. Replace the default manifest with `appsscript.json` only when required by the editor workflow.

## 3. Configure Script Properties

- `SPREADSHEET_ID`: disposable spreadsheet ID.
- `CONSENT_VERSION`: `assessment-v1-2026-07`.
- `ACTIVE_SERVICE_CODES`: `IVA,CRM,IOP` generated from active entries in `schemas/services.json`.
- `OWNER_NAME`: optional synthetic-test owner.
- `SYNTHETIC_ONLY`: `true`.

Never commit IDs, deployment URLs or secrets.

## 4. Deploy and test

1. Deploy as Web app under the venture account.
2. Access: only the narrowest setting that permits the synthetic test.
3. Execute the cases in `SYNTHETIC_TEST.md`.
4. Record counts and IDs, not names or email values, in the stage evidence.
5. Redeploy only after code changes; keep the deployment URL outside source control.

## 5. Close the test

1. Remove any deployment URL from local browser configuration.
2. Disable or delete the test web-app deployment.
3. Delete synthetic rows or archive/delete the disposable spreadsheet.
4. Confirm `apps/web/config.js` still contains `demoMode: true` and a blank endpoint.

Anonymous production access is not approved by this stage. Privacy wording, abuse controls, retention and a human activation decision remain separate gates.
