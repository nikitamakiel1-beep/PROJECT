# Deploy A01 in synthetic-only mode

Do not connect this deployment to the public website during Stage 003.

## 1. Create the disposable environment

1. Duplicate the venture CRM spreadsheet and name it `TEST — A01 Synthetic Intake — YYYY-MM-DD`.
2. Store it in `05 Automation & Integrations`.
3. Confirm the copy contains the exact headers in `schemas/crm/sheets-contract.json`.
4. Use only `.test` addresses and fictional names. Do not copy real CRM rows into the test file.

## 2. Create Apps Script

1. Open the disposable spreadsheet.
2. Select **Extensions → Apps Script**.
3. Create three server files and copy the repository contents exactly:
   - `IntakeCore.gs`
   - `Code.gs`
   - `ProviderTest.gs`
4. Replace the default manifest with `appsscript.json` only when required by the editor workflow.

## 3. Configure Script Properties

- `SPREADSHEET_ID`: disposable spreadsheet ID.
- `CONSENT_VERSION`: `assessment-v1-2026-07`.
- `ACTIVE_SERVICE_CODES`: `IVA,CRM,IOP`, generated from active entries in `schemas/services.json`.
- `OWNER_NAME`: optional synthetic-test owner.
- `SYNTHETIC_ONLY`: `true`.

Never commit IDs, deployment URLs or secrets.

## 4. Deploy the synthetic web app

1. Deploy as a **Web app** under the venture account.
2. Choose the narrowest access setting that permits the synthetic test.
3. Copy the deployment URL into a Script Property named `WEB_APP_URL`.
4. Do not put that URL into source control or the public website configuration.

## 5. Execute the provider suite

1. In Apps Script, select `runProviderHttpSuite`.
2. Run the function and approve only the permissions required by the disposable test.
3. The suite will execute:
   - new submission;
   - exact retry;
   - existing company with new contact;
   - existing contact;
   - malformed email;
   - missing company;
   - invalid service;
   - injected write failure and rollback.
4. It compares expected and actual row deltas across Companies, Contacts, Leads, Activities and Automation Log.
5. It removes all rows added after the initial snapshot in a `finally` cleanup step.
6. Copy the returned evidence object or execution-log JSON into the controlled Stage 003 evidence record. Do not copy request bodies or synthetic names/emails.

## 6. Close the test

1. Confirm every cleanup sheet result is `passed: true`.
2. Remove `WEB_APP_URL` from Script Properties.
3. Disable or delete the test web-app deployment.
4. Archive or delete the disposable spreadsheet according to the rollback decision.
5. Confirm the production CRM was unchanged.
6. Confirm `apps/web/config.js` still contains `demoMode: true` and a blank endpoint.

Anonymous production access is not approved by this stage. Privacy wording, abuse controls, retention and a human activation decision remain separate gates.
