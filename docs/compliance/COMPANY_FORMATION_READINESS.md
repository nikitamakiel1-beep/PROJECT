# Company-Formation Readiness and Incorporation Custody

**Control:** NIK-134  
**Stage:** 004s  
**Jurisdiction:** Spain and Catalonia  
**Status:** Source-ready; no company has been incorporated.

## Decision recorded

The owner selected the company route. The planning architecture is a Spanish
single-member limited company (`Sociedad Limitada Unipersonal`, S.L.U.) with one
shareholder and a provisional sole-administrator model.

This decision is architectural only. It does not establish legal personality,
reserve a corporate name, appoint an administrator, contribute capital, request
a NIF, execute a deed, register a company or authorise trading.

## Capital planning boundary

Spanish limited companies may be incorporated with capital from EUR 1. While
capital plus legal reserve remains below EUR 3,000, the statutory safeguards
include allocating at least 20% of profit to the legal reserve until that
threshold is reached and a liquidation shortfall rule referenced to EUR 3,000.

The programme records EUR 3,000 as the recommended planning amount. It records
no contribution, deposit, company asset or available company funds.

Official reference: consolidated Spanish Companies Act, article 4
(`Real Decreto Legislativo 1/2010`).

## Formation sequence

1. Record the company-route decision.
2. Select candidate names and obtain the negative name certificate.
3. Confirm the registered office and actual activity location.
4. Run the address-specific Catalonia FUE or municipal classification.
5. Approve a bounded corporate purpose.
6. Confirm CNAE and IAE classifications.
7. Confirm governance, powers and administrator remuneration.
8. Confirm and document the capital contribution.
9. Select CIRCE/DUE or the alternative notarial route.
10. Execute the public formation deed.
11. Obtain a provisional NIF through Modelo 036.
12. Register in the Provincial Mercantile Registry.
13. Obtain the definitive NIF.
14. Confirm and complete the administrator's Social Security route.
15. Configure the compliant company invoicing system.
16. Approve website identity, contracting, privacy and AI controls.

CIRCE and the Documento Único Electrónico may coordinate company-formation
procedures, but the system does not make any filing or appointment.

## Corporate-purpose boundary

The bounded draft covers website construction, digital implementation,
international market-readiness, CRM configuration, workflow automation,
commercial communications, non-certified localisation, human-supervised
software and AI implementation, commercial research and related training.

It excludes legal, tax, labour and regulated financial advice; statutory
accounts auditing; certified or sworn translation; regulated employment,
real-estate, insurance, investment or credit intermediation; and autonomous
high-impact employment, credit, biometric, emotion or sensitive-data decisions.

The final object clause remains subject to legal review, notarial acceptance and
alignment with the confirmed activity classifications.

## Administrator and Social Security boundary

A sole shareholder exercising management functions has effective control of the
company. The source pack therefore records `autonomo societario` as the
provisional route requiring external confirmation. It does not represent a
Social Security decision or registration as completed.

Official reference: Tesorería General de la Seguridad Social guidance on
effective control for company shareholders and directors.

## Address and municipal boundary

The municipal path cannot be completed without the actual municipality,
address, use of the premises, public access, works and other operational facts.
The Catalonia FUE consultation must use the real location. No address is stored
in this source pack.

Official reference: Generalitat de Catalunya, Canal Empresa, prior activity
classification consultation.

## Tax and identity boundary

Modelo 036 must be handled before the relevant economic activity or operations.
The company NIF, filing receipts and tax classifications are official evidence,
not source-code values. No provisional or definitive NIF is requested here.

Official reference: Agencia Tributaria Modelo 036 and entity-NIF guidance
current for 2026.

## Restricted custody

The following stay in restricted Drive storage and never enter public source
control, pull-request comments, public artifacts or the staged website:

- identity and address evidence;
- corporate-name and capital certificates;
- shareholder and beneficial-owner data;
- notarial drafts and signed deeds;
- provisional and definitive NIF evidence;
- Modelo 036 and other tax filings;
- Mercantile Registry and Social Security records;
- electronic certificates, signatures and credentials;
- bank accounts, mandates and payment credentials;
- signed legal, tax, privacy and invoicing opinions.

GitHub stores only public-safe control identifiers, statuses, reviewer roles and
restricted receipt pointers without personal or financial identifiers.

## Gate state

| Capability | State |
|---|---|
| Company route selected | Permitted and recorded |
| Provisional S.L.U. architecture | Permitted |
| Synthetic readiness pack | Permitted |
| Corporate-name application | Blocked |
| Registered-office confirmation | Blocked |
| Municipal/FUE classification | Blocked |
| Capital contribution | Blocked |
| Notarial deed | Blocked |
| Modelo 036 and NIF request | Blocked |
| Mercantile Registry filing | Blocked |
| Social Security registration | Blocked |
| Live publication | Blocked |
| Live intake and personal data | Blocked |
| Contract, invoice and payment | Blocked |
| Paid delivery | Blocked |

“Frozen” means unresolved and cannot be translated into approval.

## Validation

Run:

```bash
python scripts/test_company_formation_readiness.py
python scripts/audit_company_formation_readiness.py
```

The 16-case suite rejects false legal-entity claims, unsupported official
statuses, invalid capital assumptions, missing regulated-activity exclusions,
public custody leaks and any attempt to activate invoicing or trading.
