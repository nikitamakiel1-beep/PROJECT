# Real-Estate CRM Vertical

**Control:** NIK-136  
**Stage:** 006r  
**Status:** Schemas and mapping controls prepared; no real source row has been imported.

## Integration decision

The Maumer Capital operating information is merged with the existing CRM as an additive vertical. The generic CRM remains responsible for companies, contacts, leads, commercial opportunities, activities, services and automation logs. The real-estate extension adds property, deal, counterparty, investor, financing, underwriting, due-diligence, fee and source-evidence records linked through the existing `Company ID`, `Contact ID` and `Opportunity ID` keys.

This is an information-architecture merge. It is not a merger of legal entities, licences, client mandates, investment activities or ownership of the source workbooks.

## Why the lead sheet is not enough

The source workbooks contain multiple independent domains:

- property and opportunity sourcing;
- purchase prices, total investment and valuation inputs;
- project costs and durations;
- rental income and operating-expense scenarios;
- financing assumptions and lender information;
- investors, commitments and ownership percentages;
- agencies, contacts, providers and fee agreements;
- due-diligence and presentation evidence;
- offer results, realized outcomes, profit, returns and IRR.

Putting all fields into one lead or opportunity row would create duplication, overwrite risk, weak custody and an unusable audit trail. The extension therefore uses normalized entities and restricted pointers.

## Generic CRM bridge

The existing tables remain unchanged:

- Companies
- Contacts
- Leads
- Opportunities
- Activities
- Services
- Automation Log

The public website intake continues to accept the original bounded service-lead payload. It cannot create a property, investor, financing or transaction record.

Extension relationships:

| Extension record | Generic bridge |
|---|---|
| Counterparty | Company ID and/or Contact ID |
| Investor relationship | Company ID and/or Contact ID |
| Real-estate deal | Opportunity ID |
| Activities | Generic Opportunity ID, with restricted Deal ID linkage |
| Agency | Company plus Counterparty role |

## Extension entities

### Property

Stores a stable property identifier, source reference, location hash, asset type, status and restricted evidence pointers. Full addresses and cadastral references are not public schema values.

### Deal

Stores the property strategy and transaction stage while separating internal planning from external execution. Offers, reservations and closings require a named client or authorised agent and restricted evidence.

### Counterparty

Represents agencies, owners, sellers, providers, valuers, contractors, lenders and advisers. Contact authority and any real-estate-agent registration evidence are explicit states rather than assumptions.

### Investor relationship

Tracks relationship and mandate state without automated investment recommendations, solicitation or suitability decisions. Identifiable financial profiles and commitments remain restricted.

### Underwriting and financing

Preserve formula version, input provenance and human review. Source formulas and cached values are inputs, not certified valuations, guarantees or financial advice.

### Due diligence

Stores checklist state and restricted evidence links. The platform cannot clear legal, technical, tax, title, planning, occupancy or financing due diligence.

### Fees

Separates agency, project-management, legal, technical, valuation, financing and property-management fees. Agreement and invoice evidence remain restricted.

## Source mapping

The source workbooks remain in restricted Drive custody. GitHub contains only source column names, target mappings, hash rules and synthetic fixtures.

Examples:

| Source field | Target |
|---|---|
| Oportunidad | Deal source reference |
| Resultado Oferta | Human-reviewed deal-stage mapping |
| Precio de compra | Underwriting purchase-price input |
| Inversión Total | Underwriting total investment |
| Valor de tasación | Property valuation input with provenance |
| Rentabilidad Bruta / Neta / TIR | Versioned scenario metrics |
| Agency / Web | Generic company and agency counterparty |
| Contact / Email / Phone | Restricted generic-contact import candidate |
| Contacted / Newsletter / Survey | Historical activities after authority review |

## Deduplication and quarantine

Agency matching uses, in order, existing company identifiers, domain hashes, business-email hashes, phone hashes and normalized name plus municipality. Property matching uses source record identifiers, restricted cadastral hashes when available, and location hashes with characteristics.

No weak single key can overwrite a curated record. Multiple matches, missing authority, missing evidence, unsupported states, unparseable values and formulas without usable values enter `Import Quarantine`.

## Regulatory and authority boundary

Creixement may implement CRM, data normalization, dashboards, scenario calculations, restricted evidence linking and human-reviewed draft materials. It does not thereby become a real-estate agent, property valuer, investment adviser, mortgage broker or transaction decision-maker.

In Catalonia, habitual and remunerated mediation, advice or management in property transactions belongs within the applicable registered real-estate-agent regime. External contact, negotiation, offer, financing, reservation, contract and closing actions remain with the client business, an authorised registered agent or another named professional.

## Current state

| Capability | State |
|---|---|
| Generic CRM preserved | Yes |
| Real-estate schemas | Ready |
| Source structures profiled | Yes |
| Source rows copied to GitHub | No |
| Source rows imported | 0 |
| Synthetic fixtures | Permitted |
| Dry-run real import | Blocked |
| Real import | Blocked |
| Autonomous outreach | Blocked |
| Automated investor matching | Blocked |
| Valuation or offer approval | Blocked |
| Transaction mediation | Blocked |
| Live publication and paid delivery | Blocked |

## Validation

```bash
python scripts/test_real_estate_crm_vertical.py
python scripts/audit_real_estate_crm_vertical.py
```

The suite rejects generic-CRM mutation, real-record import claims, missing entity bridges, raw identifier custody, weak-key overwrite, autonomous outreach, investor selection, unreviewed formulas, platform due-diligence clearance and transaction-action bypasses.
