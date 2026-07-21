# Governed Neural CRM Intelligence

## Purpose

The venture CRM is being upgraded from deterministic workflow rules into a governed cognitive system. The system may autonomously analyse records, rank work, construct relationship graphs, produce counterfactual plans, detect anomalies and prepare reversible internal actions. It may not autonomously contact a person, change prices, issue proposals, make payments, delete records, promote a model or execute an irreversible decision.

The design reuses patterns proven in the Colonial-AI programme: predictive world models, active inference, counterfactual planning, typed knowledge graphs, calibration, temporal memory, evidence ledgers, shadow evaluation, drift detection, red-team gates and rollback.

## Cognitive colony

| Agent | Responsibility |
|---|---|
| Scout | Extract market, service, company and lead signals. |
| Cartographer | Build the company-contact-lead-service relationship graph. |
| Analyst | Run 1D CNN, graph message passing and neural feature fusion. |
| Strategist | Rank next-best actions and compare counterfactual outcomes. |
| Auditor | Inspect uncertainty, calibration, drift, provenance and conflicts. |
| Custodian | Enforce autonomy limits and human approval custody. |

Every cycle produces an append-only evidence ledger with record references, claims, confidence, warnings, model version and a SHA-256 digest. Personal names and email addresses are excluded from the ledger.

## Neural architecture

### Activity CNN

A one-dimensional convolutional encoder processes the ordered activity sequence. Each activity contains six bounded signals:

1. Recency.
2. Positive outcome.
3. Reply or response.
4. Meeting or call.
5. Direct communication channel.
6. Normalised duration.

Multiple learned convolution channels, ReLU activation and global max pooling create a compact temporal representation.

### Relationship graph neural network

The initial graph contains Company, Contact, Lead and Service nodes. Edges represent direct CRM relationships. Two message-passing layers aggregate neighbouring evidence with self-loops before producing a lead-focused graph embedding.

The next graph expansion may add Opportunities, Partners, Markets, Institutions, Campaigns, Deliverables and Referrals. Edge types must be explicit and provenance-bearing.

### Text representation

Notes, sector, next action and service context are converted to a deterministic hashed text vector. This avoids external model calls during the current synthetic stage. A later provider may replace it with a multilingual embedding model after privacy and data-processing approval.

### Neural fusion ensemble

Five deterministic neural members combine:

- twelve tabular CRM features;
- eight text features;
- the activity CNN embedding;
- the graph neural embedding.

Each member uses two dense hidden layers. The ensemble produces:

- conversion probability;
- relationship strength;
- urgency probability;
- churn risk;
- probabilities for research, request review, prepare discovery, create opportunity and nurture.

Ensemble variance is converted into uncertainty and confidence. Transparent business priors are blended with the synthetic neural output until enough real labelled outcomes exist.

## A03 opportunity intelligence

A03 evaluates a lead for a reversible internal Opportunity plan.

Eligibility requires:

- Lead status `Qualified`.
- Fit Score of at least 60.
- Active canonical service.
- Lead, Company and Contact IDs.
- No existing linked or matching Opportunity.

Opportunity value is derived from the canonical service catalogue. Arbitrary model-generated pricing is prohibited. The live CRM alias `OSP` is normalised to repository code `IOP` and recorded as a provenance warning.

The deterministic Opportunity ID is derived from Lead ID plus canonical Service Code. Existing human-curated Opportunities are preserved.

## Autonomy modes

### Shadow

Default. Produce predictions, plans, counterfactuals and evidence only. No CRM mutation.

### Assist

Produce ranked recommendations for human execution. No CRM mutation.

### Bounded auto

Permit only reversible internal actions when confidence is at least 0.72 and uncertainty is no greater than 0.28. Every action requires an audit record and rollback path.

Material internal changes require confidence of at least 0.84, uncertainty no greater than 0.16 and human approval.

The following always remain under explicit human custody:

- External email, phone, WhatsApp or social messaging.
- Proposal sending.
- Pricing and discount changes.
- Payments, invoices and contracts.
- Record deletion or destructive migration.
- Model promotion or self-modification.
- Legal, privacy or consent decisions.

## Model maturity

Current model: `neural-crm-shadow-v0.1`.

Status: synthetic shadow model. It is executable but not trained on real customer outcomes and must not be represented as predictive evidence of commercial performance.

Promotion requires:

1. A versioned labelled dataset with consent and minimisation controls.
2. Temporal train-validation-test separation.
3. Baseline comparison against transparent rules and logistic regression.
4. Calibration metrics and confidence intervals.
5. Segment-level error and fairness analysis.
6. Drift and missing-data tests.
7. Counterfactual stability tests.
8. Red-team cases for manipulation, leakage and spurious correlation.
9. Shadow deployment with no automatic actions.
10. Human approval of a signed model card and rollback plan.

## Continuous learning

Outcomes may be appended to an immutable training ledger. Training is batch-based and offline. No production inference process may rewrite its own weights. Candidate models are evaluated in shadow, compared with the active model and promoted only through a reviewed pull request and signed evidence package.

## Privacy and compliance

Raw emails, phone numbers and free-text personal data must not enter model artefacts, GitHub logs or evidence ledgers. Feature extraction should occur inside the approved data boundary. Persistent model inputs use stable pseudonymous IDs and bounded numeric features. External model providers require a separate data-processing review.
