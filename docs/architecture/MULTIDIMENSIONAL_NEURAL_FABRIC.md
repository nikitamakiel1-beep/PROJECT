# Multidimensional Neural Fabric

## Objective

Replace isolated one-dimensional activity convolution with a shared, dependency-free neural fabric that can represent multiple evidence axes at once while preserving privacy, determinism and human custody.

The fabric is used by:

- the local website service recommender;
- CRM conversion and next-action inference;
- delivery-capacity and execution planning;
- later provider and Linear integration.

It does not merge personal data between systems. Website inference remains anonymous and local. CRM inference uses approved pseudonymous or in-boundary evidence.

## Website tensor

Shape: `3 × 3 × 4`.

Axes:

1. Context plane:
   - visitor need progression;
   - canonical service compatibility;
   - need–service interactions.
2. Progression rows:
   - primary problem;
   - international/implementation state;
   - urgency/economic state.
3. Feature groups:
   - visibility/contact;
   - follow-up/automation;
   - sales/multilingual;
   - speed/affordability.

A true 3D kernel of `2 × 2 × 2` moves across all axes. Eight channels use max, mean and standard-deviation pooling. Seven deterministic ensemble members are combined before two graph-attention layers propagate compatibility across IVA, CRM, IOP, WAB and ISS.

Only active launch services enter the initial ranking. Add-ons and hidden bundles remain excluded.

## CRM tensor

Shape: `4 × 4 × 4`.

Modality planes:

1. Static commercial evidence.
2. Semantic and cross-feature evidence.
3. Temporally binned activity evidence.
4. Company–Contact–Lead–Service graph-node evidence.

Two kernel scales are applied:

- `2 × 2 × 2`;
- `3 × 2 × 2`.

Each scale uses four channels. Max, mean and standard-deviation pooling plus depth, row and column summaries produce a 36-dimensional latent representation.

A separate two-layer GNN remains active. This creates two independent relational pathways:

- graph evidence inside the convolutional tensor;
- direct graph message passing.

The dense fusion layer combines raw tabular evidence, semantic evidence, the 36-dimensional convolutional latent state and the GNN embedding.

## Connected execution planner

The same fabric converts a selected service into a reviewable delivery plan using:

- model confidence and uncertainty;
- urgency and conversion evidence;
- canonical price, hours, delivery days and automation target;
- available capacity and active workload;
- due-date pressure;
- input dependency health;
- owner, rollback and external-action governance.

Outputs:

- deterministic plan ID;
- risk score;
- capacity utilisation;
- blocker reasons;
- dependency-ordered service steps;
- connected-service handoff;
- Linear-ready issue drafts;
- evidence digest.

Linear drafts are never created automatically. They are data structures for later reviewed integration.

## Improved next-step chain

### IVA

1. Protect urgent scope when required.
2. Define one priority market and visitor profile.
3. Audit priority pages and trust signals.
4. Approve the 30-day action set.
5. Evaluate connected IOP work.

### CRM

1. Protect urgent scope when required.
2. Consolidate existing lead sources.
3. Define stages, ownership and next-action rules.
4. Approve the operating follow-up rhythm.
5. Evaluate the connected commercial-document path.

### IOP

1. Protect urgent scope when required.
2. Select the audience and use case.
3. Collect commercial proof and objection evidence.
4. Approve the bilingual one-pager.
5. Evaluate connected CRM work.

## Autonomy boundary

Allowed autonomously:

- local anonymous recommendation;
- internal tensor construction;
- shadow CRM inference;
- capacity and risk calculation;
- dependency ordering;
- internal issue-draft generation;
- counterfactual and connected-service planning.

Human-controlled:

- submitting personal details;
- external communication;
- production CRM writes;
- creating Linear issues from drafts;
- prices and discounts;
- proposals, invoices, contracts and payments;
- deployment;
- model training and promotion.

## Model status

The website model is `web-multidimensional-neural-fabric-shadow-v0.2`.

The CRM provider contract retains its existing shadow model identity until fresh provider evidence is generated. The underlying architecture is upgraded, but no claim of empirical predictive improvement is made without labelled outcomes, temporal validation, calibration and reviewed promotion evidence.
