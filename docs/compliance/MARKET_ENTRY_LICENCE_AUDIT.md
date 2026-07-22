# Market-entry licence and registration audit

## Scope

This audit covers the permissions and registrations needed to sell the current fixed-scope services in Spain and Catalonia:

- International Visibility Audit (IVA)
- CRM & Lead Tracker Setup (CRM)
- International Sales One-Pager (IOP)
- WhatsApp Business Setup (WAB)
- International Starter System (ISS)
- bounded AI-assisted internal recommendations and workflow preparation

It is an operational compliance map, not a legal opinion. Professional privacy, legal, invoicing, exact IAE and address-specific municipal review are frozen by owner instruction.

## Main conclusion

No sector-specific professional licence has been identified for the current commercial, website, content and CRM implementation scope. The services must not be presented as legal, tax, regulated financial, medical or other reserved professional advice.

The actual pre-trading requirements are business registrations and operating controls rather than a special CRM, web-design or AI-consultant licence.

## Required before trading

### 1. AEAT census registration

Register the chosen operating form using Modelo 036 before starting economic activity, carrying out operations or becoming subject to withholding obligations. Modelo 037 was removed from 3 February 2025; simplified processing now sits within Modelo 036.

### 2. IAE activity classification

Select the correct activity heading or headings for the services. Natural persons are exempt from paying IAE, and qualifying entities below EUR 1,000,000 turnover are generally exempt, but the activity still requires correct census classification.

The exact heading is deliberately unresolved while professional invoicing and tax review is frozen.

### 3. Social Security registration

If operating as an autónomo, complete RETA registration before the activity begins. A company structure would require its own formation, tax and Social Security analysis.

### 4. Municipality-specific activity check

Use the Catalonia FUE guided procedure for the actual operating address. The answer depends on whether there is a dedicated office, home-office activity, public access, signage, building works, employees or a client-facing establishment.

This is not marked approved because no final operating address and municipal classification have been reviewed.

## Required before live website intake

### LSSI provider information

The live commercial site must expose permanent, direct and free access to the operator identity, address, effective contact information and applicable registration and contracting information.

The staging build remains noindex and uses a reserved non-resolving `.invalid` endpoint. It is not a public contracting channel.

### Data protection

There is no prior AEPD licence or file-registration requirement. The obligation is demonstrable compliance:

- lawful basis and purpose;
- layered information at collection;
- record of processing activities;
- retention and deletion;
- rights handling;
- risk and security measures;
- breach handling;
- processor and subprocessor controls.

When configuring a client's CRM under the client's instructions, an Article 28 processor agreement is required before accessing personal data.

## Conditional requirements

### B2C consumer sales

If services are sold to consumers rather than businesses, consumer rules apply. The launch system must then include pre-contract information, prices, written budgets where required, payment and cancellation terms, withdrawal information and complaint handling.

In Catalonia, businesses providing services directly or through intermediaries to consumers must maintain the official complaint process and applicable notice.

### EU cross-border services

Before relevant intra-EU transactions, confirm place-of-supply, VAT treatment and whether ROI/VIES registration is required through Modelo 036.

### AI-enabled functionality

The current recommendation and neural systems remain bounded and human-controlled. AI literacy duties already apply. From 2 August 2026, Article 50 transparency duties apply to in-scope interactive and generative AI systems. Before enabling a live AI interaction, classify whether the venture is a provider or deployer and add any required interaction or generated-content disclosure.

No high-risk use is authorised. Employment, credit, biometric, medical, eligibility and legal-effect decision uses remain excluded.

## Recommended but not identified as mandatory

Professional indemnity and cyber insurance should be evaluated before material client data or operational integrations are handled. This is a risk-transfer decision, not an identified licence for the current service scope.

## Frozen decisions

The following remain explicitly frozen and unapproved:

- professional privacy review;
- professional legal review;
- professional invoicing review;
- exact IAE heading selection;
- address-specific municipal procedure;
- live contractual wording;
- live publication and real data collection.

## Current release decision

```text
staging artifact              permitted
synthetic-only                required
noindex                       required
reserved .invalid endpoint    required
public intake                 prohibited
client personal data          prohibited
paid contracting              prohibited
live publication              prohibited
```

Run:

```bash
python scripts/audit_market_entry_licensing.py
python scripts/test_market_entry_licensing.py
python scripts/build_web_release.py --profile staging \
  --endpoint https://synthetic-provider.invalid/exec \
  --output dist/web-staging
```

## Official reference set

- Agencia Tributaria: Modelo 036 and IAE guidance
- Tesorería General de la Seguridad Social: autonomous-worker registration
- Generalitat de Catalunya: FUE and Canal Empresa activity procedures
- BOE: Ley 34/2002 on information-society services and electronic commerce
- AEPD: controller, processor and record-of-processing guidance
- Agència Catalana del Consum: consumer obligations and official complaint forms
- European Commission: AI Act and Article 50 transparency guidance
