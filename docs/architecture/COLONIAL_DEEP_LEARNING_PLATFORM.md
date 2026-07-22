# Colonial Deep-Learning Platform

## Status

Model family: `colonial-deep-platform-shadow-v0.1`.

This repository now contains executable dependency-free reference implementations, schemas, browser components and runtime-adapter plans for the requested deep-learning technologies. It does **not** contain trained production models, client-derived weights or an activated external inference provider. Real training requires versioned datasets, optional framework packages, compute, evaluation and reviewed promotion evidence.

## Colonial operating pattern

The architecture inherits the useful Colonial-AI mechanics:

- Specialist expert colonies rather than one opaque agent.
- Explicit information trade routes.
- Acknowledgement requirements and route debt.
- Safety and audit experts with veto authority.
- Feedback and feedforward loops.
- Evidence-bound model and dataset promotion.
- Reversible internal automation before external autonomy.

### Expert colonies

| Expert | Domain | Primary capabilities |
|---|---|---|
| Argus | Vision | YOLO decoding, visual quality, media-to-card assignment |
| Mnemosyne | Retrieval | Embeddings, vector retrieval, RAG, grounded generation |
| Hermes | CRM/B2B | Lead graph, opportunities, follow-up, company relationships |
| Hestia | B2C | Consumer intent, consent scope, bounded personalisation |
| Daedalus | Training | Backpropagation, LoRA, autotuning, quantisation |
| Janus | Reinforcement learning | DQN, policy gradients, reward governance |
| Atlas | Interface | Floating cards, latent layout, handoffs |
| Pallas | Safety | Privacy, overfitting, drift and promotion vetoes |

Every route can accumulate acknowledgement debt. Unresolved debt blocks release.

## Multiextradimensional neural fabric

The existing multidimensional CRM and website tensors remain the shared discriminative foundation. The new deep platform extends this with:

- Arbitrary-shaped tensor contracts.
- Multidimensional convolutional feature extractors.
- Latent-space representations.
- Token embeddings.
- Causal multi-head self-attention.
- Sparse top-k mixture-of-experts routing.
- Graph relationships and card relationships.
- Quantised tensor representations.

The platform deliberately avoids claiming that all data should use CNNs. Temporal and spatial arrays use convolution; relationships use graph structures; text uses embeddings and attention; policy selection uses reinforcement learning.

## Backpropagation, gradient descent and optimisation

`core.py` provides a reverse-mode autodiff scalar graph. `training.py` provides:

- Dense trainable layers.
- Frozen-base PEFT layers.
- LoRA low-rank adapters.
- AdamW gradient descent.
- Global gradient clipping.
- Dropout.
- Weight decay.
- Deterministic train/validation separation.
- Early stopping.
- Hyperparameter search.
- Model-card generation.

The reference trainer restores the best validation checkpoint instead of the final epoch.

## Avoiding overfitting

The platform requires a combination of:

1. Temporal and source-level train/validation/test separation.
2. Segment-level holdouts for B2B, B2C and industry groups.
3. Early stopping.
4. Dropout and weight decay.
5. Gradient clipping.
6. Data augmentation audits for vision.
7. Perplexity or task-specific holdout metrics.
8. Calibration and drift analysis.
9. Baseline comparisons.
10. Red-team tests for leakage, memorisation and proxy optimisation.

A lower training loss alone is never promotion evidence.

## PEFT and LoRA

The repository contains a functional low-rank adapter that leaves the base matrix frozen and trains only A/B adapter matrices. The optional Transformers adapter defines a later Hugging Face/PEFT pipeline with:

- Reviewed target modules.
- LoRA rank, alpha and dropout.
- Gradient accumulation.
- Quantisation candidate.
- Evaluation and checkpoint policy.
- No automatic Hub publishing.

Adapter merge and model promotion remain manual reviewed operations.

## Retrieval-Augmented Generation

The RAG subsystem contains:

- Deterministic hashed embeddings.
- A metadata-filtered vector index.
- Similarity retrieval.
- Citation-bearing prompt packs.
- A fail-closed answer when evidence is absent.
- A causal autoregressive reference decoder.
- Perplexity measurement.

The current generator is template-bound and evidence-first. A real language model can be attached later only through the reviewed runtime adapter.

## Embeddings, self-attention and autoregressive decoding

The reference decoder uses:

- Token embeddings.
- Causal self-attention.
- Sparse mixture-of-experts output routing.
- Temperature-controlled greedy decoding.
- Sequence perplexity.

It validates architecture and contracts; it is not a commercially useful language model.

## Mixture of experts

The sparse MoE activates only the top-k experts and returns routing weights. The platform also uses expert colonies at the orchestration level. Model evaluation must monitor:

- Expert usage distribution.
- Route confidence.
- Expert collapse.
- Segment performance.
- Safety-veto frequency.

## Contrastive learning

A cosine-margin contrastive objective is provided for:

- Service and need embeddings.
- Card similarity.
- Document retrieval.
- B2B/B2C segment representation.
- Multimedia-to-card matching.

Real contrastive fine-tuning requires labelled or weakly supervised positive/negative pairs and a temporal holdout.

## Quantisation

The reference tensor layer supports symmetric int8 quantisation and dequantisation. Optional runtime plans cover:

- 4-bit transformer loading candidates.
- FP16 candidates.
- Int8 ONNX vision export.
- Calibration datasets.
- Accuracy-regression limits.

A smaller model is not accepted when performance, calibration or safety degrades beyond the configured limit.

## Reinforcement learning

### DQN

The DQN reference contains:

- Online and target Q networks.
- Epsilon-greedy exploration.
- Replay memory.
- Bootstrapped targets.
- Target synchronisation.
- Clipped TD error.

### Policy gradient

The policy-gradient implementation contains:

- Masked softmax policy.
- Discounted returns.
- Advantage normalisation.
- Entropy regularisation.
- Gradient clipping.

Both agents mask external communication. They optimise only internal reversible actions.

### Reward governance

The reward model rejects proxy objectives such as message volume, click volume, lead pressure or automatic discounts. Privacy violations, unapproved external actions and rollback failures receive severe negative rewards.

## YOLO and multimedia

The YOLO-style reference layer provides:

- Grid prediction decoding.
- Class confidence calculation.
- Normalised bounding boxes.
- Intersection-over-union.
- Non-maximum suppression.
- Multimedia-to-card assignment.

The optional Ultralytics plan defines dataset, fine-tuning, augmentation, mAP, export and quantisation requirements. No trained detector is claimed until a labelled multimedia dataset and framework runtime exist.

## Floating layers and cards

Cards are the primary human interface for the intelligence network. Lead, company, service, opportunity, activity, document, media, insight, task and risk cards receive:

- Stable IDs.
- Latent embeddings.
- Deterministic floating layers and positions.
- Related-card links.
- Confidence.
- Source references.
- Reviewable actions.

The browser card fabric renders seven layers and relationship lines. Actions are disabled by default and never write to CRM automatically.

## B2B, B2C, CRM and database network

The governed feature store supports pseudonymous bounded features for:

- B2B companies and contacts.
- B2C people.
- Leads and opportunities.
- Services and activities.
- Documents and media.

Raw names, email addresses, phone numbers, addresses, tokens and secrets are rejected. The entity graph expresses typed evidence-backed relations. The dataset registry records consent scope, digests, splits and whether training is permitted.

## Optional production runtimes

The repository includes lazy, non-executing plans for:

- PyTorch.
- Hugging Face Transformers.
- PEFT.
- Ultralytics YOLO.
- ONNX Runtime.
- Sentence Transformers.

The plan reports missing packages and governance blockers. It does not install dependencies, download models, send data or begin training.

## Promotion gates

Any trained model requires:

- Dataset and schema digests.
- Dataset card and model card.
- Licence and provenance review.
- Temporal and segment holdouts.
- Baseline comparison.
- Calibration and drift evidence.
- Overfitting gap review.
- Privacy and memorisation tests.
- Red-team results.
- Quantisation regression results when applicable.
- Rollback evidence.
- Pull request and explicit human approval.

No runtime can promote itself.
