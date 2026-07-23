# Heavy Runtime Candidate Federation

## Purpose

Stage 003l removes the operational gap between the dependency-free microcandidate smoke lane and the optional PyTorch, PEFT and Ultralytics implementations.

The federation trains three separate CPU-bounded candidates from the governed synthetic dataset bundle:

1. a PyTorch contrastive retrieval encoder;
2. a local GPT-style transformer with PEFT/LoRA adapters;
3. an Ultralytics YOLO model created from YAML with `pretrained=false`.

The candidates are evidence sources only. They are not connected to CRM decisions, client communication, pricing, contracts or production deployment.

## Execution topology

```text
Governed dataset generator
        |
        +--> PyTorch embedding runtime
        |
        +--> Transformers + PEFT runtime
        |
        +--> Ultralytics YOLO runtime
                    |
                    v
       CandidateEvidence packs
                    |
                    v
       Eight-axis review board
                    |
                    v
       Microcandidate reference frontier
```

Dataset generation occurs once. Candidate frameworks install in isolated parallel jobs with separate dependency locks. The final job downloads the available evidence artifacts, verifies pack digests, rejects any promotion flag and requires language, embedding and vision evidence before the workflow can pass.

## Why microcandidate values are not a direct leaderboard

The dependency-free microcandidates and heavy candidates use different model classes and task geometries. Their metrics are therefore recorded as an efficiency and evidence frontier, not treated as interchangeable benchmark values.

The federation records:

- primary metric and direction;
- framework;
- runtime duration;
- rollback artifact size;
- candidate baseline;
- microcandidate reference;
- explicit `directly_comparable=false` status.

A heavy candidate is reviewed against its own transparent untrained baseline and safety gates. It is not rejected merely because a deliberately simple micro-task achieved a stronger raw number.

## Fail-closed controls

The workflow requires:

- synthetic or explicitly approved governed data only;
- offline model mode;
- no pretrained weights;
- no production credentials;
- no external uploads beyond GitHub evidence artifacts;
- complete language, embedding and vision candidate set;
- valid pack digests;
- non-empty rollback artifacts;
- `promotion_permitted=false` at candidate, board and federation levels;
- human review before any later shadow-runtime connection.

A failed candidate job still uploads any material it produced. The final federation reports missing tasks, but the workflow remains red until the complete set exists.

## Outputs

The federated evidence artifact contains:

```text
DATASET_SUMMARY.json
datasets/
candidates/embedding/
candidates/lora/
candidates/yolo/
heavy-runtime-review.json
```

Artifacts are retained for 14 days.

## Remaining boundary

Successful completion establishes reproducible heavy candidate execution and evidence custody. It does not establish production accuracy, lawful real-client training data, model promotion, CRM activation or external autonomy.
