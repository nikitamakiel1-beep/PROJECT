# Neural Memory, Learning and Recursive Planning

## Objective

Extend the governed neural CRM from one inference cycle into a persistent operating intelligence without allowing uncontrolled self-modification.

The system may remember pseudonymous outcomes, replay balanced evidence, calculate calibration, detect drift, record incidents and generate the next bounded internal programme instruction. It may not rewrite active model weights, deploy itself, contact external people, change prices or promote a candidate model without human approval.

## Temporal outcome memory

Each outcome event stores:

- Stable pseudonymous entity ID.
- Model version.
- Prediction and binary observed outcome.
- Segment and decision type.
- Feature-package SHA-256 digest.
- Evidence-package SHA-256 digest.
- Event timestamp.

Raw names, email addresses, phone numbers and free text are prohibited.

The outcome ledger is append-only and duplicate-safe. Its own digest changes when and only when the ordered event set changes.

## Replay

The replay buffer selects recent evidence deterministically while preserving segment representation. Replay is used for offline candidate evaluation, regression testing and incident reproduction. It does not trigger online weight updates.

## Calibration

The monitor reports:

- Brier score.
- Expected calibration error.
- Log loss.
- Positive outcome rate.
- Per-bin prediction and observed outcome rates.

These metrics are evidence inputs, not automatic promotion commands.

## Drift

The initial drift monitor compares bounded numeric features between a baseline and a current window. It combines standardised mean shift and variance change. Material maximum or average drift opens a review condition.

Later versions may add population stability index, Jensen-Shannon divergence, graph-topology drift and temporal concept drift. Any new detector must be tested against stable and adversarial synthetic populations.

## Incident memory

Calibration failures, leakage, manipulation, drift, provider errors and unsafe proposed actions are stored in an append-only incident ledger. Resolution appends mitigation and closure evidence; it does not erase the original incident.

## Model promotion

The promotion gate is fail-closed. A candidate remains blocked unless all of the following are true:

1. It differs from the active model.
2. Minimum labelled-outcome count is met.
3. It beats the transparent baseline on Brier score.
4. Expected calibration error is no greater than 0.10.
5. No unresolved distribution drift exists.
6. Red-team tests pass.
7. Rollback is verified.
8. Temporal split is verified.
9. Segment-level review passes.
10. A human explicitly approves promotion.

The gate only declares eligibility for a reviewed promotion. It does not update files, weights, deployments or active configuration.

## Neural venture planner

The planner routes programme attention across nine domains:

- Provider runtime.
- Compliance.
- CRM data quality.
- Website conversion.
- Customer discovery.
- Sales pipeline.
- Service delivery.
- Partnerships and funding.
- Model evidence.

Sixteen normalised health metrics are processed by a small neural router and blended with transparent programme priorities. This prevents an untrained neural layer from overriding obvious blockers.

The selected domain produces:

- A deterministic plan ID.
- Domain probability distribution.
- Confidence.
- Blocker list.
- Three bounded internal tasks.
- Evidence digest.
- A complete n→n+1 instruction.

The instruction always requires the next executor to read current state and previous evidence, work inside bounded scope, run tests, produce a report and generate the instruction for n+2.

## Autonomy boundary

Autonomous:

- Internal scoring and ranking.
- Memory append validation.
- Calibration and drift calculation.
- Incident proposal.
- Counterfactual planning.
- Internal task and stage-instruction generation.

Human custody:

- External communication and publishing.
- Production deployment or trigger activation.
- CRM destructive changes.
- Pricing, contracts, invoices and payments.
- Legal and consent decisions.
- Model promotion.

## Current status

This layer is synthetic and repository-local. It has no provider connection and does not read production CRM data. It is ready for shadow evaluation once the provider-runtime gate supplies pseudonymised feature packages and evidence-safe outcome events.
