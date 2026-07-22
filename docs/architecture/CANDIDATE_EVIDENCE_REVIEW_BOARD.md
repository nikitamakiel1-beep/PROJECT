# Candidate Evidence Review Board

## Purpose

The candidate laboratory can create evidence packs, but a raw metric file is not a release decision. A11 converts each pack into a multi-axis review card, assigns unresolved evidence to the responsible Colonial expert route, runs a deterministic synthetic shadow rollout and verifies rollback custody.

The board is not a model registry that deploys winners. Its maximum state is `eligible_for_extended_shadow`.

## Inputs

A candidate pack must identify:

- Candidate, task and framework.
- Dataset and code digests.
- Random seed.
- Candidate and baseline metrics.
- Segment-level metrics.
- Quantisation metrics when applicable.
- Privacy and adversarial results.
- Rollback artifact.
- Limitations.

Unsigned synthetic evidence may be reviewed, but signed evidence is required before any later provider or deployment gate.

## Review dimensions

| Axis | Weight | Responsible route |
|---|---:|---|
| Performance | 20% | Daedalus → Pallas |
| Generalisation | 13% | Daedalus → Pallas |
| Calibration | 10% | Hermes → Pallas |
| Privacy | 15% | Hestia → Pallas |
| Robustness | 14% | Janus → Pallas |
| Efficiency | 8% | Daedalus → Atlas |
| Rollback | 10% | Pallas → Atlas |
| Reproducibility | 10% | Daedalus → Pallas |

Declared limitations remain visible but do not automatically reject a candidate. Missing evidence, failed safety tests, baseline regression, excessive overfit, unstable rollout or absent rollback do.

## Task-specific performance gates

### Language model

- Test perplexity must beat the baseline.
- Validation loss minus training loss must not exceed 0.35.

### Retrieval embedding

- Retrieval MRR must beat the random or transparent baseline.

### Vision

- mAP50 must beat baseline.
- Precision and recall must each be at least 0.50.

### Quantisation

- Relative quality loss must not exceed 5%.
- A quantised runtime that is slower than the original remains a review finding.

## Shadow rollout

The simulator creates six deterministic synthetic cohorts with forty decisions per cohort by default. No client record or production action is used.

It measures:

- Candidate/baseline disagreement.
- Abstention.
- Synthetic incident rate.
- Rollback recovery.

A rollout is stable only when the candidate beats baseline, disagreement is no greater than 0.28, incident rate is no greater than 0.05 and rollback recovery is at least 0.95.

## Route debt

Every non-passing axis creates route debt. Route debt is a release blocker and identifies which expert pair must produce new evidence. The candidate must be repackaged and rerun after the debt is addressed.

## Decisions

`reject_or_rework`
: One or more evidence or rollout blockers exist.

`human_review_required`
: No hard blocker exists, but evidence strength is insufficient for extended shadow.

`eligible_for_extended_shadow`
: The board score is at least 0.85, the rollout is stable and no blockers remain.

No decision permits production deployment or automatic model promotion.

## Client-facing cards

The website contains a clearly labelled synthetic demonstration board. It visualises review axes, route debt, rollback and shadow-rollout state as floating cards. It contains no trained production results, private datasets, weights or enabled actions.

## CLI

```bash
python scripts/review_candidate_packs.py candidate-artifacts/ \
  --output candidate-review-board.json
```

The output is suitable for a GitHub artifact, internal Drive archive or later Linear attachment. It is not a deployment configuration.
