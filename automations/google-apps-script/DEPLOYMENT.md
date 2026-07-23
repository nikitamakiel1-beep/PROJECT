# Deploy Stage 003 provider workflows in synthetic-only mode

Do not connect this deployment to the public website or production CRM during Stage 003.

## 1. Create the disposable environment

1. Duplicate the venture CRM spreadsheet and name it `TEST — A01 Synthetic Intake — YYYY-MM-DD`.
2. Store it in `05 Automation & Integrations`.
3. Confirm the copy contains the exact headers in `schemas/crm/sheets-contract.json`.
4. Use only `.test` addresses and fictional names. Do not copy real CRM rows into the test file.
5. Ensure the copy contains `Services`, `Opportunities`, `Activities` and `Automation Log`.

## 2. Create Apps Script

Open the disposable spreadsheet and select **Extensions → Apps Script**.

Create these files and copy the repository contents exactly:

1. `IntakeCore.gs`
2. `Code.gs`
3. `ProviderTest.gs`
4. `FollowUpCore.gs`
5. `DailyFollowUp.gs`
6. `NeuralBridgeCore.gs`
7. `NeuralBridge.gs`

Replace the default manifest with `appsscript.json` only when required by the editor workflow.

## 3. Configure Script Properties

Required common properties:

- `SPREADSHEET_ID`: disposable spreadsheet ID.
- `CONSENT_VERSION`: `assessment-v1-2026-07`.
- `ACTIVE_SERVICE_CODES`: `IVA,CRM,IOP`.
- `OWNER_NAME`: optional synthetic-test owner.
- `SYNTHETIC_ONLY`: `true`.
- `NEURAL_PSEUDONYM_SALT`: a long random test-only secret stored only in Script Properties.

Optional deterministic test properties:

- `A02_TODAY_OVERRIDE`: ISO date for repeatable digest tests.
- `A06_TODAY_OVERRIDE`: ISO date for repeatable neural package tests.
- `A02_LIMIT`: maximum digest rows.

Bounded internal write properties remain disabled initially:

- `A03_AUTONOMY_MODE`: leave unset until neural import evidence passes.
- `A03_BOUNDED_WRITE_ENABLED`: leave unset or `false` until the explicit bounded-write test.

Never commit IDs, deployment URLs, salts or secrets.

## 4. Deploy and test A01 intake

1. Deploy as a **Web app** under the venture account.
2. Choose the narrowest access setting that permits the synthetic test.
3. Copy the deployment URL into a Script Property named `WEB_APP_URL`.
4. Run `runProviderHttpSuite()`.
5. Verify all request cases, row deltas, rollback and cleanup pass.
6. Keep the URL out of source control and website configuration.

## 5. Test A02 internal follow-up digest

1. Run `runDailyFollowUpDigest()`.
2. Confirm `Follow-up Digest` is created or rebuilt.
3. Confirm the function sends no email or WhatsApp message.
4. Run it again for the same date and confirm duplicate handling.
5. Verify only aggregate evidence appears in `Automation Log`.

## 6. Export A06 PII-free neural packages

1. Add at least one fictional Qualified Lead with:
   - Fit Score at least 60;
   - valid Company and Contact IDs;
   - active Service Interest;
   - no existing Opportunity link.
2. Add fictional Activities and matching Company, Contact and Service records.
3. Run `runNeuralShadowExport()`.
4. Confirm `Neural Shadow Queue` is created.
5. Inspect `Export JSON` and verify it contains no names, emails, phones, URLs or raw notes.
6. Copy one `Export JSON` value into a local `package.json` file.

## 7. Run repository neural shadow inference

From a checked-out repository branch, run:

```bash
python scripts/run_neural_shadow.py package.json --output decision.json
```

Verify:

- package ID and feature digest match;
- decision version is `neural-provider-decision-v1`;
- model is `neural-crm-shadow-v0.1`;
- `mutation_permitted` is `false`;
- `external_communication_permitted` is `false`;
- decision digest is present.

## 8. Import the neural decision

Copy the full contents of `decision.json` and run:

```javascript
importNeuralShadowDecision(decisionJson)
```

Confirm the queue row becomes `Decision Ready` and receives a decision digest. A result may be labelled `AUTO_ELIGIBLE`, but no write occurs yet.

## 9. Test bounded internal Opportunity write

Only after the export, inference and import evidence passes:

1. Set `A03_AUTONOMY_MODE=bounded_auto`.
2. Set `A03_BOUNDED_WRITE_ENABLED=true`.
3. Run `applyBoundedNeuralOpportunities()`.
4. Verify only decisions with confidence at least 0.72 and uncertainty no greater than 0.28 are applied.
5. Verify one deterministic internal Opportunity is created and the Lead is linked.
6. Verify no external message, proposal, invoice, contract or payment is produced.
7. Run again and confirm duplicate preservation.
8. Inject or simulate a later write failure and verify rollback.
9. Return `A03_BOUNDED_WRITE_ENABLED` to `false` or remove it.

## 10. Close the test

1. Confirm every A01 cleanup result is `passed: true`.
2. Remove `WEB_APP_URL` from Script Properties.
3. Disable or delete the test web-app deployment.
4. Remove `A03_BOUNDED_WRITE_ENABLED` and `A03_AUTONOMY_MODE`.
5. Remove or rotate `NEURAL_PSEUDONYM_SALT`.
6. Archive or delete the disposable spreadsheet according to the rollback decision.
7. Confirm the production CRM was unchanged.
8. Confirm `apps/web/config.js` still contains `demoMode: true` and a blank endpoint.

Anonymous production access, real personal-data processing, live model inference and external communication remain separate approval gates.
