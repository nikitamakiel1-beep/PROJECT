# Stage 003 provider activation runbook

> Purpose: execute the disposable Google Apps Script provider tests, collect evidence-safe output, verify cleanup and decide whether Stage 003 may advance. This runbook does not authorise production activation.

## Preconditions

- Repository visibility reviewed. While the repository is public, no spreadsheet ID, deployment URL, credential, contact data or provider output containing raw submissions may be committed.
- Disposable CRM copy exists and its title begins with `TEST — A01 Synthetic Intake —`.
- A bound Apps Script project is created from the disposable spreadsheet.
- The current generated Apps Script bundle is used without ad-hoc source edits.
- The operator can disable the deployment and remove Script Properties after the test.
- The privacy and commercial launch controls remain blocked for real intake.

## Required bundle files

Install in the order stated by `INSTALL_ORDER.txt`:

- `IntakeCore.gs`
- `Code.gs`
- `ProviderTest.gs`
- `FollowUpCore.gs`
- `DailyFollowUp.gs`
- `NeuralBridgeCore.gs`
- `NeuralBridge.gs`
- `appsscript.json`

Use the generated artifact. Do not copy files from an older local ZIP.

## Script Properties

Configure outside source control:

| Property | Required value or rule |
|---|---|
| `SPREADSHEET_ID` | Disposable spreadsheet ID |
| `CONSENT_VERSION` | `assessment-v1-2026-07` |
| `ACTIVE_SERVICE_CODES` | `IVA,CRM,IOP` |
| `OWNER_NAME` | Named test owner |
| `SYNTHETIC_ONLY` | `true` |
| `A02_LIMIT` | Optional positive integer |
| `WEB_APP_URL` | Temporary deployed test URL; remove after A01 suite |

Never paste property values into GitHub, Linear comments, public screenshots or the evidence report.

## Snapshot before execution

Record privately:

- spreadsheet title and owner;
- sheet names and row counts;
- formula/validation presence for affected sheets;
- existing `Follow-up Digest` state;
- Automation Log row count;
- deployment identifier;
- Script Properties key names, not values;
- operator and timestamp.

## A01 HTTP provider suite

1. Deploy the bound script as the narrow synthetic test web app.
2. Set `WEB_APP_URL` in Script Properties.
3. Run `runProviderHttpSuite()` from the bound project.
4. Require all nine cases to pass.
5. Verify expected row deltas for Companies, Contacts, Leads, Activities and Automation Log.
6. Verify duplicate cases do not create duplicate business records.
7. Verify invalid/unsupported cases do not leave partial rows.
8. Verify pre-existing rows and formulas remain unchanged.
9. Retain only the sanitised aggregate test result.

A failed case blocks Stage 003. Do not edit the expected result to force qualification.

## A02 daily follow-up digest

1. Confirm `SYNTHETIC_ONLY=true` and disposable title prefix.
2. Run `runDailyFollowUpDigest()`.
3. Verify the digest includes due/overdue active Leads and Opportunities.
4. Verify terminal and future-dated records are excluded.
5. Verify stable priority ordering and owner counts.
6. Run it again on the same date.
7. Verify idempotency: no duplicate accepted log and no uncontrolled rewrite.
8. Introduce a controlled failure only in a disposable copy if rollback evidence is required.
9. Verify the previous digest is restored after failure.

The digest is internal. It must not send email, WhatsApp or mutate pipeline stages.

## Neural shadow package

1. Use only synthetic/disposable CRM records.
2. Generate the provider package through the bound bridge.
3. Verify raw Lead, Company and Contact IDs do not leave the spreadsheet.
4. Verify pseudonyms use the configured HMAC boundary.
5. Verify canonical service normalisation and feature digest.
6. Run shadow inference outside the spreadsheet where intended.
7. Store only aggregate/evidence-safe decision output.
8. Confirm no CRM stage, price, external message or delivery decision is applied automatically.

## Evidence compilation

Use `scripts/generate_provider_evidence.py` only with the sanitised passing provider output. The compiler must reject:

- fewer than nine A01 cases;
- failed cases;
- missing cleanup evidence;
- missing rollback evidence where required;
- raw submissions or responses;
- spreadsheet/deployment identifiers;
- personal data;
- unsupported evidence structure.

Required evidence summary:

| Area | Required result |
|---|---|
| A01 cases | 9/9 passed |
| Duplicate safety | Passed |
| Row-delta reconciliation | Passed |
| Existing-record preservation | Passed |
| A02 logic | 6/6 contract cases and provider run passed |
| A02 idempotency | Passed |
| Rollback | Passed where exercised |
| Neural package | PII-free and digest verified |
| Cleanup | Complete |
| Human reviewer | Named approval or rejection |

## Cleanup

Immediately after evidence capture:

1. Disable the web-app deployment.
2. Remove `WEB_APP_URL`.
3. Remove or rotate any temporary secret used for provider testing.
4. Confirm the endpoint no longer responds as an active test deployment.
5. Confirm the disposable spreadsheet contains no uncontrolled test residues beyond the intended synthetic records.
6. Confirm no personal data or identifiers entered source control, artifacts or logs.
7. Record cleanup timestamp and operator.

Cleanup failure blocks Stage 003 even if all functional cases passed.

## Advancement decision

Stage 003 may advance only when:

- provider evidence is complete and sanitised;
- all required cases pass;
- rollback and idempotency are evidenced;
- cleanup is verified;
- no secret or personal-data exposure occurred;
- repository safety validation passes;
- a named human accepts the evidence; and
- the Stage 003 report and evidence-based Stage 004 instruction are written.

The stage pointer must not move on the basis of source tests alone.

## Failure disposition

| Failure | Required response |
|---|---|
| Functional case failure | Preserve aggregate error, fix source, rerun complete suite |
| Partial write | Restore snapshot, investigate rollback, block stage |
| Duplicate creation | Preserve evidence, repair idempotency, rerun |
| Identifier/secret exposure | Disable/revoke, assess incident, purge where possible, block stage |
| Cleanup failure | Disable deployment and verify before any further run |
| Evidence compiler rejection | Correct source evidence; never weaken compiler contract |
| Human rejection | Record rationale and create bounded remediation issue |
