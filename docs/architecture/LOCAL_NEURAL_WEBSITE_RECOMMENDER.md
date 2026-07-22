# Local Neural Website Recommender

## Purpose

A07 gives a visitor a directional service recommendation before any personal or company details are requested. The entire inference cycle runs in the browser and does not call the CRM, Apps Script or an external model provider.

## Architecture

1. Seven bounded questionnaire answers are encoded into ten features.
2. The features are arranged as a three-step need sequence.
3. A four-channel one-dimensional CNN extracts temporal/interaction signals from that sequence.
4. Direct compatibility is calculated against canonical service profiles.
5. A service relationship graph propagates adjacent value between IVA, CRM, IOP, WAB and ISS.
6. Five deterministic ensemble members produce service probability distributions.
7. Ensemble variance produces confidence and uncertainty.
8. The three strongest feature/profile interactions become bounded explanation reasons.

Only services with `status: active` enter the primary ranking. Add-ons and hidden bundles cannot be recommended as the first purchase.

## Privacy boundary

The recommender asks for no name, email, phone number, company, website or free-text notes. It stores nothing and transmits nothing. Selecting a recommendation merely changes the service dropdown in the separate assessment form after an explicit click.

## Model status

`web-neural-recommender-shadow-v0.1` is a deterministic synthetic model. Fit percentages are ranking outputs, not empirical probabilities of commercial success. Scope and suitability require human review.

## Prohibited behaviour

- Automatic assessment submission.
- Automatic email or messaging.
- Automatic purchase or payment.
- Price modification.
- Activation of hidden services.
- Online training or self-modification.
- Representing the recommendation as guaranteed business advice.

## Promotion path

A later candidate may learn from aggregate, consented recommendation outcomes only after a privacy review. Promotion requires an anonymised event contract, calibration against observed selections and completed engagements, segment review, drift monitoring, rollback and explicit human approval.
