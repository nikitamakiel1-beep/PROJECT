# Heavy Candidate Quality Rework

## Evidence basis

The first heavy-runtime federation produced three valid trained artifacts but only the LoRA candidate beat its transparent baseline. The embedding candidate tied its baseline at MRR 0.50. The bounded YOLO smoke run produced zero mAP50, precision and recall. The rework preserves that first-run evidence and introduces version-two candidates rather than rewriting it.

## Embedding v2

The retrieval objective now masks the diagonal before optimisation, so an item cannot use itself as the easiest match. All same-service records in the batch contribute to a supervised contrastive objective. Token IDs use SHA-256 rather than process-dependent Python hashing.

Evaluation reports overall and IVA/CRM/IOP holdout MRR, centroid classification accuracy, validation-fitted temperature, expected calibration error and Brier score. The dense projection is exported to ONNX and dynamically quantised to int8 for latency, size and relative-error evidence.

## LoRA v2

The adapter trains for up to eight epochs with validation early stopping and best-adapter restoration. Validation logits select a calibration temperature. Test evidence contains expected calibration error, Brier score and comparable top-1 token accuracy for IVA, CRM and IOP.

Synthetic shadow disagreement now uses relative perplexity improvement. Raw inverse-perplexity differences are unsuitable because they compress materially different language models into nearly identical values.

## YOLO v2

The original scenes differed mainly by colour, which was insufficient for a tiny detector trained for three epochs. Version two creates class-distinct geometric structures for documents, charts, logos, products, landscapes and people. Four deterministic train variants are produced per source record. Training remains CPU-bounded, deterministic and starts from `yolo11n.yaml` with `pretrained=False`.

Evaluation reports overall mAP50, precision, recall, per-class AP, confidence ECE and Brier score. No quality threshold is reduced.

## Custody

All candidates remain synthetic shadow candidates. Promotion, production deployment, CRM decision use, external communication and automatic model activation remain false. Rollback artifacts and evidence digests are mandatory.
