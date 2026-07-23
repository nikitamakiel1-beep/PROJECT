# Autonomous Microcandidate Evidence Lane

## Purpose

Remove the operational dependency on manually dispatched heavy workflows while preserving the separate optional PyTorch, PEFT and Ultralytics laboratory.

Every pull request now trains three small dependency-free models and passes their evidence through the same fail-closed candidate review board used by the optional runtime. These models prove that training, evidence custody, rollback and adjudication remain executable. They do not replace the heavier optional candidates.

## Candidates

### Low-rank autoregressive adapter

A frozen uniform transition base is adapted through trainable low-rank A/B matrices. Training uses cross-entropy, reverse-mode analytical gradients, weight decay and global gradient clipping. Evaluation reports train, validation and test loss, perplexity, calibration, Brier score and segment quality.

This is a real low-rank parameter-efficient model, but it is a transition micro-model rather than a transformer or production language model.

### Service latent embedding

A trainable six-to-three latent projection learns synthetic IVA, CRM and IOP service structure through supervised gradient descent. Evaluation reports retrieval mean reciprocal rank, classification accuracy, calibration, Brier score and B2B/B2C segment quality.

This validates embedding training and retrieval evidence without using client text.

### Convolutional card-vision proxy

Three trainable 3×3 convolution filters classify synthetic horizontal, vertical and diagonal card patterns. Backpropagation flows through convolution, ReLU and global average pooling. Evaluation reports a classification-derived proxy mAP50, macro precision, macro recall, calibration and per-class quality.

This candidate is explicitly labelled `not YOLO`. It is only a fast convolutional smoke candidate. Full YOLO evidence still requires the optional Ultralytics workflow.

## Automatic workflow

`Autonomous microcandidate evidence` runs on every pull request and may also be dispatched manually. It:

1. Trains all three microcandidates with a fixed seed.
2. Writes rollback weight artifacts.
3. Creates CandidateEvidence packs.
4. Applies the original fail-closed evidence gate.
5. Runs the eight-axis CandidateReviewBoard.
6. Simulates 240 shadow decisions per candidate.
7. Verifies that promotion remains false.
8. Uploads the complete evidence directory for 14 days.

No optional package installation, model download, external dataset, production credential or CRM connection is required.

## Relationship to the heavy laboratory

The microcandidate lane is a continuous smoke and governance lane. The optional laboratory remains necessary for:

- actual GPT-style LoRA/PEFT execution;
- actual PyTorch contrastive encoders;
- actual Ultralytics YOLO training;
- ONNX export and int8 runtime benchmarking;
- larger datasets and hardware-dependent evaluation.

A passing microcandidate does not imply that the corresponding heavy candidate will pass.

## Safety boundary

- Synthetic data only.
- No personal data.
- No external communication.
- No production model or CRM action.
- No model download.
- No automatic promotion.
- Rollback artifact required.
- Human review always required.
- Vision proxy must remain labelled as not YOLO.
