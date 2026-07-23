# Corporate Identity and Formation Handoff Dossier

**Control:** NIK-135  
**Stage:** 005s  
**Status:** Decision materials prepared; no name, address or activity classification has been officially selected.

## Corporate-name shortlist

The dossier contains five ordered candidates:

1. Creixement International Systems, S.L.U.
2. Creixement Market Operations, S.L.U.
3. Creixement Digital Expansion, S.L.U.
4. Creixement Venture Services, S.L.U.
5. Creixement Global Enablement, S.L.U.

These are planning candidates only. No availability query or certification request has been made. The Registro Mercantil Central allows up to five ordered names in one application, requires the social form, and states that the name in the deed must coincide exactly with the favourable certificate. A favourable name is reserved for six months, while the certificate is valid for three months for execution of the deed. A preliminary availability consultation is informative and does not bind the registrar.

Trademark, domain and social-handle screening are separate controls. None replaces the Registro Mercantil Central certificate.

## Registered-office strategy

Spanish company law requires the registered office to be in Spain at the centre of effective administration and direction or at the principal establishment or operation. A nominal address that does not correspond to either creates a mismatch risk.

The dossier scores four options:

| Option | Planning result |
|---|---|
| Founder home office | Lowest cost, but high public-address and residential-use risk |
| Coworking with physical access and domiciliation rights | Provisional planning preference |
| Mail-only virtual office | Not recommended without substance, bank, notary and professional review |
| Dedicated leased office | Strongest operational substance, but excessive early fixed cost |

The preferred early-stage profile is a coworking or serviced office that provides genuine physical workspace, contractual permission for registered-office use, reliable official-mail handling and address-specific municipal compatibility. No provider, contract or real address has been selected.

## FUE input pack

The municipal questionnaire requires the exact municipality and address, premises type, activity description, public access, client visits, employees, works, signage, storage, equipment, hazards, surface, opening hours, accessibility, fire controls and owner/lease/community constraints.

The Generalitat procedure classifies the activity and identifies the applicable municipal route. The description must be sufficiently complete, and the municipality must be specified. No query has been submitted.

## Candidate activity classifications

The dossier uses CNAE-2025, introduced by Real Decreto 10/2025. Candidate classes include:

- 70.20 — other management-consultancy activities;
- 62.20 — IT consultancy and computer-facilities management;
- 62.10 — computer programming;
- 62.90 — other IT and computer services;
- 73.11 — advertising agencies;
- 73.20 — market research and opinion polling;
- 73.30 — public relations and communication;
- 74.12 — graphic design and visual communication;
- 74.30 — translation and interpretation, bounded to non-certified localisation;
- 85.59 — other education n.e.c.

The provisional primary CNAE candidate is 70.20 because the venture is centred on international market readiness, commercial systems and business-development implementation. This is not a final classification.

IAE and CNAE are different systems. Candidate IAE families are recorded only as hypotheses: 849.9, 845, 844 and 933.9. The final heading or headings must be confirmed against the actual activity description through the AEAT activity search, Modelo 036 preparation and professional review.

## Notary/PAE handoff

The public-safe handoff template contains only:

- planned S.L.U. form;
- ordered candidate-name labels;
- registered-office option identifier;
- bounded corporate-purpose version;
- candidate CNAE and IAE references;
- €3,000 capital plan;
- provisional sole-administrator model;
- review statuses;
- restricted-document checklist.

Identity, beneficial ownership, full address, name certificate, bank and capital evidence, administrator identity, tax identifiers and electronic credentials remain restricted.

## Gate state

| Capability | State |
|---|---|
| Five-name shortlist | Prepared |
| Availability query | Not performed |
| Name certificate | Not requested |
| Trademark/domain action | Not performed |
| Registered-office option matrix | Prepared |
| Real address | Not present |
| Office selected or contracted | No |
| FUE questionnaire | Prepared |
| FUE submission | No |
| CNAE candidates | Prepared, unconfirmed |
| IAE candidates | Prepared, unconfirmed |
| Notary/PAE handoff template | Prepared |
| Notary/PAE instructed | No |
| Incorporation and commercial activation | Blocked |

## Validation

```bash
python scripts/test_corporate_identity_dossier.py
python scripts/audit_corporate_identity_dossier.py
```

The suite rejects excess or missing name candidates, missing S.L.U. suffixes, false availability or certificate claims, real-address leakage, virtual-office overapproval, CNAE/IAE conflation, unsupported classification confirmation, notary instruction and commercial activation.
