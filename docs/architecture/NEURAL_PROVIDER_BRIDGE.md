# Neural Provider Bridge

## Objective

Connect the Google Sheets CRM to the repository neural engine without exporting raw personal data or allowing uncontrolled operational actions.

The bridge is deliberately split into three trust zones:

1. **CRM zone — Google Sheets / Apps Script**
   - Holds raw Lead, Company and Contact identifiers.
   - Converts records to bounded numerical features.
   - Replaces identifiers with salted pseudonyms.
   - Retains the pseudonym-to-record mapping only inside the spreadsheet.

2. **Inference zone — repository Python runtime**
   - Accepts only `neural-provider-package-v1` JSON.
   - Rejects personal-data field names, email markers, URLs and digest mismatches.
   - Runs the 1D CNN, graph neural encoder and neural fusion ensemble.
   - Returns `neural-provider-decision-v1` with shadow-only execution policy.

3. **Decision-custody zone — Google Sheets / Apps Script**
   - Imports the signed decision into `Neural Shadow Queue`.
   - Verifies package ID, feature digest, decision digest format and policy.
   - May prepare or apply a reversible internal Opportunity under explicit bounded-auto gates.
   - Cannot send external communication.

## CRM export

`runNeuralShadowExport()` reads:

- Leads.
- Companies.
- Contacts.
- Services.
- Activities.
- Opportunities.

Only Leads satisfying all of the following are exported:

- Status is `Qualified`.
- Fit Score is at least 60.
- Lead, Company and Contact IDs exist.
- Service is active and has a positive canonical price.
- No existing linked or equivalent Opportunity exists.

The export normalises the legacy CRM code `OSP` to canonical `IOP`.

## Pseudonymisation

Apps Script requires `NEURAL_PSEUDONYM_SALT` in Script Properties. It creates HMAC-SHA-256 pseudonyms separately for Lead, Company and Contact identities. The salt is never committed to GitHub.

The exported package contains no:

- Personal names.
- Company names.
- Email addresses.
- Phone numbers.
- URLs.
- LinkedIn references.
- Raw notes.
- Raw activity summaries.

Free text is transformed into an eight-dimensional hashed vector before export.

## Neural package

Each package contains:

- Pseudonymous Lead, Company and Contact references.
- Canonical Service Code and catalogue price.
- Twelve bounded tabular features.
- Eight hashed text features.
- Up to twenty six-dimensional activity vectors.
- Four graph nodes and an adjacency matrix.
- Lead focus index.
- Transparent conversion, relationship, urgency, churn and action priors.
- SHA-256 feature digest.

The JavaScript canonical JSON and Python canonical JSON are tested for identical feature digests.

## Inference

Run:

```bash
python scripts/run_neural_shadow.py package.json --output decision.json
```

The neural engine returns:

- Conversion probability.
- Relationship strength.
- Urgency probability.
- Churn risk.
- Ranked next-action distribution.
- Confidence and uncertainty.
- Deterministic Opportunity reference.
- Canonical price, probability and weighted value.
- Shadow execution policy.
- SHA-256 decision digest.

## Decision import

Copy the decision JSON into:

```javascript
importNeuralShadowDecision(decisionJson)
```

The importer verifies:

- Decision version.
- Package ID.
- Feature digest.
- Decision digest format.
- `mutation_permitted=false`.
- `external_communication_permitted=false`.

A valid decision becomes `Decision Ready`. It is labelled `AUTO_ELIGIBLE` only when the neural result satisfies the bounded confidence and uncertainty gate.

## Bounded internal Opportunity write

`applyBoundedNeuralOpportunities()` is disabled unless all of these Script Properties are present:

```text
SYNTHETIC_ONLY=true
A03_AUTONOMY_MODE=bounded_auto
A03_BOUNDED_WRITE_ENABLED=true
```

The spreadsheet name must begin with `TEST —`.

The write requires:

- Confidence at least 0.72.
- Uncertainty no greater than 0.28.
- No existing Opportunity ID.
- No existing Lead-to-Opportunity link.
- Deterministic Opportunity reference.
- Canonical service price from the package.

The function appends one internal Opportunity, links the Lead and records aggregate automation evidence. It rolls back the appended row and Lead link if a later operation fails.

It does not:

- Send email, WhatsApp, phone or social messages.
- Generate or send a proposal.
- Change a service price or discount.
- Issue an invoice or contract.
- Mark an Opportunity Won.
- Create a payment.
- Promote a neural model.

## Queue structure

`Neural Shadow Queue` stores:

- Package ID.
- Internal raw Lead, Company and Contact mapping.
- Canonical Service Code.
- Feature digest.
- PII-free export JSON.
- Decision digest.
- PII-free decision JSON.
- Status and review status.
- Applied timestamp and notes.

The raw mapping never leaves the spreadsheet.

## Current status

This implementation remains synthetic-only until the disposable Apps Script provider test is executed and evidence is recorded. Production activation requires a separate privacy review, provider-runtime evidence and a new explicit gate.
