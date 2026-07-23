# Daily Operator Runbook — Apartment Analysis and Report Production RC3

Use this document when operating the system. The longer RC2 manual remains the reference for detailed evidence, legal and reporting rules.

## 1. Check the release status

From the repository root:

```powershell
python scripts/real_estate_operator_control.py release-status `
  --output-json release-status.json `
  --output-markdown RELEASE_STATUS.md
```

The current evidence baseline reports:

- Architecture package: **98.8% — ready for release review**.
- Controlled operator use: **81.5% — controlled use ready**.
- Live client production: **47.0% — not ready**.

Interpretation:

- You can use the local controlled workflow with manual review.
- Do not enable unattended live collection, client delivery or purchase actions.
- The score is not permission to release. Critical blockers and named approvals still control the decision.

## 2. Start a new apartment

Choose the code using the existing convention:

```text
PROVINCE_MUNICIPALITY_NEIGHBOURHOOD##
```

Example:

```text
BA_BARCELONA_GRACIA01
```

Initialise the complete workspace and case control:

```powershell
python scripts/real_estate_operator_control.py init-case `
  "C:\RealEstate\Projects" `
  BA_BARCELONA_GRACIA01 `
  "Carrer Example 10 — investment analysis" `
  listing_link `
  --date 2026-07-23
```

For a private opportunity, use `confidential` or `off_market` instead of `listing_link`.

This creates:

- the project folder structure;
- `case-control.json`;
- `CASE_STATUS.md`;
- AutoPPTX Piso, Zona and Proyectos folders.

The initial case percentage is 0% because no evidence has been approved yet.

## 3. Understand the case percentage

| Component | Weight |
|---|---:|
| Source intake and rights | 10% |
| Property facts and evidence | 10% |
| USANDO underwriting | 20% |
| La Vanguardia zone evidence | 10% |
| Media | 10% |
| PPTX/PDF generation | 15% |
| Four-role report approvals | 10% |
| Due diligence | 10% |
| Client decision | 5% |

Statuses contribute:

- `not_started`: 0%;
- `in_progress`: 40%;
- `ready_for_review`: 75%;
- `approved`: 100%;
- `blocked`: 0%;
- `not_applicable`: removed from the denominator.

A 75% case can still be blocked from presentation or purchase. Use the gates, not only the number.

## 4. Source intake

### You do manually

1. Paste the listing link or enter the confidential opportunity.
2. Confirm the source type.
3. Confirm whether the property is genuinely off-market.
4. Record whether the property and photographs may be used.
5. Keep the real URL, contact and exact address in restricted custody.
6. Check whether a supposedly off-market property appears on a portal.

### The automation prepares

- project code and folders;
- source record structure;
- restricted-pointer fields;
- missing-field list;
- next actions.

Mark the component in progress:

```powershell
python scripts/real_estate_operator_control.py mark `
  "C:\RealEstate\Projects\BA_BARCELONA_GRACIA01\case-control.json" `
  source_intake in_progress `
  --date 2026-07-23 `
  --actor restricted://operator/NIKITA `
  --note "Listing saved and rights review started"
```

Approve it only when the source and rights are understood:

```powershell
python scripts/real_estate_operator_control.py mark `
  "C:\RealEstate\Projects\BA_BARCELONA_GRACIA01\case-control.json" `
  source_intake approved `
  --date 2026-07-23 `
  --actor restricted://reviewer/source `
  --evidence restricted://evidence/source-record
```

## 5. Property facts and evidence

### Automation can prepare

- price;
- municipality and province;
- approximate location;
- m²;
- rooms and bathrooms;
- floor and lift;
- terrace, balcony, parking and storage;
- description;
- available photos and floor plan.

### You must confirm or enter

- exact address;
- occupancy;
- current lease;
- IBI;
- community fees;
- garbage tax;
- cadastral reference;
- ITE and habitability information;
- special assessments;
- building/community condition;
- negotiated price;
- renovation scope;
- seller or agency declarations.

Use evidence labels:

- PUBLIC-SOURCE;
- SELLER-DECLARED;
- SYSTEM-ESTIMATED;
- VISIT-VERIFIED;
- DOCUMENT-VERIFIED;
- MISSING.

Approve only when the important contradictions are resolved or clearly recorded as risks.

## 6. USANDO financial analysis

Prepare a JSON object whose keys match confirmed workbook headers.

Example `field-values.json`:

```json
{
  "PRECIO DE COMPRA": 220000,
  "M2": 78,
  "Habitaciones": 3,
  "Baños": 1,
  "FINANCIACION": 0.70,
  "Tipo interes": 0.0325,
  "Años prestamo": 25
}
```

Build the plan:

```powershell
python scripts/real_estate_rc2_cli.py workbook-plan `
  BA_BARCELONA_GRACIA01 `
  "C:\RealEstate\Maumer_Capital-Oportunidades_USANDO.xlsx" `
  field-values.json `
  AUTHORISED_LINK_INTAKE `
  0.10 `
  --output workbook-plan.json
```

Do not invent a transfer-tax header. Until the exact USANDO header is verified, the rate remains reviewed metadata and the adapter reports:

```text
manual_transfer_tax_binding_required = true
```

When the real header is confirmed, use:

```powershell
--transfer-tax-header "CONFIRMED EXACT HEADER"
```

Validate the plan without modifying Excel:

```powershell
python scripts/windows_usando_excel_adapter.py workbook-plan.json
```

Before execution:

- use a copy of the workbook during validation;
- close Excel;
- close any application holding the file;
- confirm that every JSON key exists as a unique header;
- confirm the transfer-tax assumption;
- confirm financing, rents, renovation and expenses.

Execute on Windows with Microsoft Excel and `pywin32`:

```powershell
python scripts/windows_usando_excel_adapter.py workbook-plan.json --execute
```

Review the receipt:

- target row;
- written headers;
- B3 selection;
- full recalculation;
- before/after hashes;
- transfer-tax binding status;
- financial review readiness.

Review traditional, room and temporary strategies independently. Approve only the strategies that should appear in the report.

## 7. La Vanguardia zone evidence

Generate the plan:

```powershell
python scripts/real_estate_rc2_cli.py zone-plan `
  BA_BARCELONA_GRACIA01 `
  "Carrer Example 10, Barcelona" `
  restricted://operator/NIKITA `
  --output zone-capture-plan.json
```

You then do this manually:

1. Open the configured La Vanguardia map.
2. Search the exact address.
3. Confirm street, number and municipality.
4. Confirm that the marker falls in the intended census section.
5. Record the displayed household-income value.
6. Record the source data year.
7. Record the visible legend bucket or reviewed numerical range.
8. Select Zone 1–5.
9. Capture a screenshot containing marker, polygon, value and legend.
10. Save at least two surroundings images with rights and attribution.

Do not default to Zone 3. When the map or legend is uncertain, mark the component `blocked` and record:

```text
ZONE UNVERIFIED — MANUAL REVIEW REQUIRED
```

Generate the evidence bundle:

```powershell
python scripts/real_estate_rc2_cli.py zone-evidence `
  zone-capture-plan.json `
  zone-capture-record.json `
  --output zone-evidence.json
```

## 8. Property and surroundings media

### Automation now does

- SHA-256 hashing;
- duplicate removal;
- natural ordering;
- removal of stale managed AutoPPTX images;
- target-copy hash verification;
- separation of Piso and Zona media.

### You do manually

- confirm rights;
- reject blurred or misleading images;
- detect faces, plates, documents or confidential details;
- select the strongest image of each room or area;
- review any AI-cleaned output.

### Watermark cleanup

Use this order:

1. Request a clean original.
2. Find a separately authorised clean copy.
3. Use the marked original with attribution.
4. Use AI cleanup only when rights evidence exists.

Build the cleanup plan:

```powershell
python scripts/real_estate_rc2_cli.py cleanup-plan `
  media.json `
  "C:\RealEstate\Projects\BA_BARCELONA_GRACIA01\06 Visit and Photos\Authorised Clean" `
  restricted://reviewer/media `
  "Client authorised cleanup for the investment report" `
  "C:\WatermarkRemover-AI\remwm.py" `
  --output cleanup-plan.json
```

RC3 stages exactly one source file in an isolated input directory. It rejects unexpected extra outputs. It cannot overwrite the original.

Never clean La Vanguardia, news-map, Street View or public map captures.

## 9. Generate AutoPPTX and PDF

Before generation:

- the workbook row is updated and recalculated;
- approved strategies are recorded;
- the zone evidence is approved;
- at least one authorised property image exists;
- the map screenshot and at least two surroundings images exist;
- financial, evidence, legal and commercial reviewers are distinct;
- Excel is closed;
- the target PowerPoint is closed.

The staging operation is idempotent. Rerunning it removes only previously managed `NN_piso.*` and `NN_zona.*` files, not unrelated files.

Generate locally through the configured AutoPPTX entry point. Export PDF through PowerPoint COM. Verify the output hashes.

## 10. Report review

Review every output against Excel and the source evidence.

Minimum checks:

- project code;
- address and location marker;
- municipality and province;
- m², rooms, bathrooms, floor and lift;
- additional-room assumptions;
- IBI, community and garbage tax;
- insurance and maintenance;
- purchase, renovation, fees and transfer tax;
- financing rate, term and payment;
- rents and comparables;
- gross yield, net yield, ROE and cash-on-cash;
- slide 6 services;
- slide 8 zone map, value, zone, year and attribution;
- property and surroundings images;
- strategy slides;
- PPTX/PDF visual parity.

Then obtain four distinct approvals and mark `report_approvals` approved.

## 11. Check the case status

```powershell
python scripts/real_estate_operator_control.py status `
  "C:\RealEstate\Projects\BA_BARCELONA_GRACIA01\case-control.json" `
  --markdown "C:\RealEstate\Projects\BA_BARCELONA_GRACIA01\CASE_STATUS.md"
```

The output reports:

- the percentage;
- each component status;
- the pre-analysis gate;
- the report gate;
- the client-presentation gate;
- the acquisition gate;
- blocked components;
- the next five manual actions;
- automation available for those actions.

## 12. Client presentation and acquisition

A generated report does not authorise purchase.

For client presentation, the following must be approved:

- source intake;
- property facts;
- financial underwriting;
- zone evidence;
- media;
- report generation;
- report approvals.

After the client expresses interest, complete:

- physical visit;
- registry and charges;
- occupancy and lease review;
- ITE and habitability;
- building and community review;
- renovation confirmation;
- negotiated price;
- financing confirmation;
- updated underwriting.

Mark `due_diligence` approved only after this is complete.

Mark `client_decision` approved only with an explicit written instruction tied to the exact property, maximum price, financing and reservation terms.

RC3 still does not submit offers, reservations, contracts, invoices, payments or purchases.

## 13. Current blockers to live production

The live score is 47.0%. The main blockers are:

1. written source/API permission for each live portal;
2. approved controller, processor, retention and service-identity package;
3. one authorised live source adapter;
4. three real La Vanguardia address validations and approved legend;
5. one copied-USANDO execution test;
6. authorised WatermarkRemover sample validation;
7. traditional, room and temporary golden reports;
8. Excel/PPTX/PDF parity receipts;
9. named live reviewers and operating rehearsal.

Until these are closed, use the workflow in controlled manual mode only.
