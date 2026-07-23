# Greater Operator Manual — Apartment Discovery, Analysis, Zone Evidence and AutoPPTX

**Release:** Real-estate architecture RC2  
**Primary workbook:** `Maumer_Capital-Oportunidades_USANDO.xlsx`  
**Zone source:** La Vanguardia household-income interactive  
**Renderer:** recovered local AutoPPTX plus PowerPoint PDF export

## 1. Operating objective

Move a property from a listing link or confidential opportunity to a reviewed client dossier:

```text
Source → project code → evidence → USANDO workbook → profitability approval
→ La Vanguardia zone evidence → authorised media → AutoPPTX → PDF
→ report QA → client presentation → due diligence → final purchase instruction
```

The system prepares data, folders, plans, calculations and report inputs. A named human still decides source rights, confidential fields, assumptions, profitability, zone, report approval and purchase authority.

## 2. Core rules

1. Preserve the original source and original media.
2. Label facts as public-source, seller-declared, estimated, visit-verified or document-verified.
3. Never replace missing information with a silent default.
4. Keep exact addresses, cadastral references, contacts and confidential documents in restricted custody.
5. Use the `USANDO` workbook as the current calculation engine.
6. Force full Excel recalculation before using results.
7. Use La Vanguardia as the requested zone evidence source and display its data year.
8. Remove a watermark only from owned, licensed or explicitly authorised property media.
9. Never remove attribution or marks from La Vanguardia, news maps or Street View captures.
10. A report is decision support, not authority to buy.

## 3. Intake from a listing link

Create a source record containing:

- source portal or partner;
- restricted original URL;
- external listing reference;
- first-seen date;
- asking price;
- source organisation;
- source-rights status;
- media-rights status;
- off-market claim and verification status.

Extract only what the listing supports:

- city, province, neighbourhood and address precision;
- price;
- area;
- bedrooms and bathrooms;
- floor and lift;
- terrace, balcony, parking and storage;
- description;
- photographs and floor plan;
- agency or seller;
- publication and energy information.

A link normally does not prove IBI, community fees, garbage tax, ITE, habitability, occupancy, leases, legal rent limits, negotiated price, renovation scope or hidden defects. Mark those fields missing, declared or estimated until evidence exists.

## 4. Confidential or off-market intake

Enter manually:

- restricted source/contact token;
- confidentiality classification;
- exact or approximate location;
- price and negotiation range;
- property characteristics;
- known expenses;
- occupancy;
- documents and photographs;
- permission to use the information and media.

Do not place the seller identity, telephone, email, exact address or cadastral reference in GitHub.

## 5. Routing decision

Apply the current internal rules:

- Idealista-listed properties do not qualify for PSI+.
- Non-Idealista portal properties may qualify after review.
- Canal normally requires verified off-market status.
- Bank, fund and social-source exceptions require human review.
- An off-market claim is not proof.

Record the decision and reviewer. Do not allow a source label to trigger external distribution automatically.

## 6. Project code and workspace

Use:

```text
PROVINCE_MUNICIPALITY_NEIGHBOURHOOD##
```

Example:

```text
BA_BARCELONA_GRACIA01
```

Create the workspace:

```bash
python scripts/real_estate_rc2_cli.py create-workspace \
  "C:\\RealEstate\\Projects" BA_BARCELONA_GRACIA01
```

The result contains:

```text
01 Source
02 Property Data
03 Catastro and Legal
04 Financial Inputs
05 Comparables
06 Visit and Photos/Originals
06 Visit and Photos/Authorised Clean
07 Underwriting
08 Report Output
09 Approvals
AutoPPTX/Piso/PROJECT_CODE
AutoPPTX/Zona/PROJECT_CODE
AutoPPTX/Proyectos/PROJECT_CODE
```

## 7. Evidence statuses

Use:

- `PUBLIC-SOURCE`
- `SELLER-DECLARED`
- `SYSTEM-ESTIMATED`
- `VISIT-VERIFIED`
- `DOCUMENT-VERIFIED`
- `REVIEWED`
- `MISSING`
- `REJECTED`
- `EXPIRED`

An estimate may appear in pre-analysis, but it must remain visibly labelled.

## 8. Updating the USANDO workbook

Use the latest controlled workbook whose active name ends in `USANDO`. Close Excel before automated execution.

The RC2 adapter:

- searches the first configured rows for the `CODI` header;
- updates the existing project row or first empty row;
- writes values by header name;
- sets `#Pre-analisis!B3` to the project code;
- calls `CalculateFullRebuild`;
- saves and closes Excel;
- records before/after workbook hashes.

Important fields include:

- `CODI`
- `FINANCIACION`
- `PRECIO DE COMPRA`
- renovation estimates for traditional, room and temporary strategies;
- interest rate and loan years;
- downside/base/upside rents;
- room-rental units;
- agency and advisory fees;
- reference value;
- IBI, community, insurance and maintenance;
- city, province, CCAA, area, rooms, bathrooms, floor and lift;
- strategy switches;
- restricted listing and cadastral references;
- selected rent and profitability outputs.

Always provide an explicit reviewed transfer-tax rate.

Build the plan:

```bash
python scripts/real_estate_rc2_cli.py workbook-plan \
  BA_BARCELONA_GRACIA01 \
  "C:\\RealEstate\\Maumer_Capital-Oportunidades_USANDO.xlsx" \
  field-values.json \
  AUTHORISED_LINK_INTAKE \
  0.10 \
  --output workbook-plan.json
```

Validate:

```bash
python scripts/windows_usando_excel_adapter.py workbook-plan.json
```

Execute on Windows with Excel and `pywin32`:

```bash
python scripts/windows_usando_excel_adapter.py workbook-plan.json --execute
```

## 9. Profitability decision

Review each strategy independently.

### Traditional rental

Check market or regulated rent evidence, downside/base/upside logic, maintenance, vacancy, insurance and legal limits.

### Room rental

Check legal bedrooms, feasible conversion, room comparables, higher maintenance and local rules.

### Temporary rental

Check permitted use, duration, tenant profile, utilities, vacancy, management cost and medium-stay comparables.

Current minimum policy unless replaced by a signed revision:

- gross yield above 7%;
- net yield above 5%;
- ROE above 10%;
- cash-on-cash above 7%.

Classify each strategy:

- rejected;
- marginal;
- qualified;
- strong;
- exceptional.

Only approved strategies appear in the report.

## 10. La Vanguardia address-to-zone workflow

Use the configured La Vanguardia interactive, which presents household income by block/census section and is based on the INE household-income atlas. The referenced story uses 2020 data, so the report must show the source year and a stale-data warning.

Create a capture plan:

```bash
python scripts/real_estate_rc2_cli.py zone-plan \
  BA_BARCELONA_GRACIA01 \
  "Carrer Example 10, Barcelona" \
  restricted://operator/NIKITA \
  --output zone-capture-plan.json
```

Then manually:

1. Open the configured page in a normal browser.
2. Search the exact property address.
3. Confirm municipality, street and number.
4. Confirm the marker is inside the intended census-section polygon.
5. Record coordinates where available.
6. Record displayed household income.
7. Record the visible legend colour/range.
8. Select Zone 1, 2, 3, 4 or 5.
9. Capture the map with marker, polygon, income and legend visible.
10. Save at least two surroundings images with source and attribution.

### Critical zone rule

The article text does not document the exact five numeric cut points used by the report design. Do not hard-code remembered limits.

Use either:

- a reviewed visible legend bucket; or
- four reviewed and versioned numerical cut points.

When the legend cannot be verified, use:

```text
ZONE UNVERIFIED — MANUAL REVIEW REQUIRED
```

Never default to Zone 3.

Create `zone-capture-record.json` with matched address, coordinates, confidence, income, source year, selected zone, legend label/version, screenshot path, surroundings and manual confirmation.

Build evidence:

```bash
python scripts/real_estate_rc2_cli.py zone-evidence \
  zone-capture-plan.json zone-capture-record.json \
  --output zone-evidence.json
```

Reviewed numerical thresholds can be supplied with `--thresholds-json`. Example numbers in command documentation are syntax examples only, not approved La Vanguardia limits.

## 11. Zone photographs

PPT V3 requires a minimum of two surroundings photographs in addition to the rent map screenshot.

Prefer:

- your own photographs;
- licensed images;
- authorised agency or client media;
- permitted Street View captures with attribution;
- other public-source captures allowed for reporting.

Store source URL, attribution and rights status. Do not remove marks from map, news or Street View evidence.

## 12. Property photographs

Preserve originals and classify them as facade, street, portal, common area, living room, kitchen, bedroom, bathroom, balcony, view, parking, floor plan or defect.

Flag duplicates, blur, low resolution, faces, number plates, documents and unauthorised marks.

Use natural order so `2.jpg` appears before `10.jpg`.

## 13. Watermark handling hierarchy

1. Request the clean original from the owner or authorised source.
2. Locate a separately authorised clean copy.
3. Use the marked original with attribution when cleanup is not authorised.
4. Use AI cleanup only with explicit rights evidence.

The WatermarkRemover-AI adapter uses Florence-2 detection and LaMA inpainting.

Cleanup is allowed only for:

- owned media;
- licensed media;
- client-authorised media;
- explicitly portal-authorised media.

Cleanup is forbidden for:

- La Vanguardia captures;
- news maps;
- Street View captures;
- public map screenshots;
- unverified portal images.

The original must remain untouched and before/after hashes must be recorded.

Build a cleanup plan:

```bash
python scripts/real_estate_rc2_cli.py cleanup-plan \
  media.json \
  "C:\\RealEstate\\Projects\\...\\Authorised Clean" \
  restricted://reviewer/media-reviewer \
  "Client authorised cleanup for the investment report" \
  "C:\\WatermarkRemover-AI\\remwm.py" \
  --output cleanup-plan.json
```

Review the cleaned output before report use.

## 14. AutoPPTX preparation

Stage naturally ordered files in:

```text
AutoPPTX/Piso/PROJECT_CODE
AutoPPTX/Zona/PROJECT_CODE
```

`Zona` must contain the La Vanguardia map screenshot plus at least two surroundings images. `Piso` should contain one representative image for every available internal area.

Before execution:

- close Excel;
- close any PPTX with the same code;
- confirm `#Pre-analisis!B3`;
- confirm full recalculation and save;
- confirm approved strategies;
- confirm zone evidence and media rights;
- confirm four report reviewers.

Run AutoPPTX through the governed local command with `shell=False`, then export PDF using PowerPoint COM.

Expected outputs:

```text
PROJECT_CODE.pptx
PROJECT_CODE.pdf
PROJECT_CODE.report-job.json
generation receipt
verification receipt
```

## 15. Mandatory slide review

### Slide 6

Review and adjust nearby services and categories. Verify relevance and distance.

### Slide 8

Verify:

- exact-address map screenshot;
- correct census-section polygon;
- household income;
- Zone 1–5;
- source year;
- source attribution;
- stale-data warning.

### Photo slides

Verify order, labels, cropping, duplicates, sensitive content and rights.

### Strategy slides

Remove or hide any strategy that was not approved.

## 16. Report checklist

Review:

- project code;
- city and province;
- location marker;
- population and transport;
- area, bedrooms, bathrooms, floor and lift;
- extra room comments;
- IBI, community and garbage tax;
- insurance and maintenance;
- purchase price and renovation;
- fees and transfer tax;
- financing ratio, rate and term;
- gross yield, net yield, ROE, cash-on-cash and cash flow;
- every Excel/PPT value;
- visit evidence;
- rent comparables;
- zone evidence;
- image quality;
- legal and evidence warnings;
- PPTX/PDF equivalence.

## 17. Client process

### Presentation approval

The client authorises deeper investigation. This is not purchase approval.

### Investigation

Complete visit, building/community review, registry and charges, occupancy, habitability/ITE, renovation, negotiated price, financing and updated underwriting.

### Final acquisition approval

Require a signed instruction tied to the exact property, maximum price, financing, due diligence, current calculation snapshot, risks and reservation/offer terms.

Only then proceed to negotiation, reservation or purchase workflows.

## 18. Decision rules

### Continue to pre-analysis

Proceed when source, core property facts, unique code and rights status are understood.

### Continue to full report

Proceed when at least one strategy qualifies, assumptions are reviewed, zone evidence is verified, media is usable and four report reviewers approve.

### Hold

Hold for missing exact address, unclear occupancy, unverified rights, missing comparables, missing zone evidence, conflicting expenses or stale calculations.

### Reject

Reject for failed economics, prohibited use, unresolved legal/occupancy risk, fabricated information, invalid source, unauthorised media or serious technical defects.

## 19. Troubleshooting

- Wrong project: check `#Pre-analisis!B3`, save, close and rerun.
- Stale values: execute the Excel COM adapter and verify full rebuild.
- Zone unavailable: do not invent it; record manual review required.
- Map changed: version and reapprove the legend.
- Wrong photo order: restage with natural numeric sorting.
- Artificial cleanup: reject it and use the authorised original.
- PDF mismatch: re-export with PowerPoint COM and compare page by page.

## 20. Current boundary

RC2 does not scrape La Vanguardia, bypass portal controls, download unlicensed media, write to the real CRM automatically, send reports, contact clients, submit offers, request financing, sign contracts, issue invoices or execute payments.
