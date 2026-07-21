from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
import random
from typing import Any, Mapping, Sequence


DOMAINS = (
    "provider_runtime",
    "compliance",
    "crm_data_quality",
    "website_conversion",
    "customer_discovery",
    "sales_pipeline",
    "service_delivery",
    "partnerships_funding",
    "model_evidence",
)

METRICS = (
    "provider_gate",
    "compliance_ready",
    "crm_data_quality",
    "website_quality",
    "interviews_progress",
    "demonstrations_progress",
    "pipeline_health",
    "delivery_capacity",
    "automation_reliability",
    "labelled_outcomes_progress",
    "drift_health",
    "incident_health",
    "partner_network_progress",
    "funding_radar_progress",
    "conversion_validation",
    "revenue_validation",
)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _softmax(values: Sequence[float]) -> list[float]:
    maximum = max(values)
    exp = [math.exp(max(-40.0, min(40.0, value - maximum))) for value in values]
    total = sum(exp) or 1.0
    return [value / total for value in exp]


def _weights(seed: int, inputs: int, hidden: int, outputs: int) -> tuple[list[list[float]], list[float], list[list[float]], list[float]]:
    rng = random.Random(seed)
    first = [[rng.uniform(-0.30, 0.30) for _ in range(hidden)] for _ in range(inputs)]
    first_bias = [rng.uniform(-0.05, 0.05) for _ in range(hidden)]
    second = [[rng.uniform(-0.32, 0.32) for _ in range(outputs)] for _ in range(hidden)]
    second_bias = [rng.uniform(-0.05, 0.05) for _ in range(outputs)]
    return first, first_bias, second, second_bias


def _matvec(vector: Sequence[float], matrix: Sequence[Sequence[float]], bias: Sequence[float]) -> list[float]:
    result = list(map(float, bias))
    for input_index, value in enumerate(vector):
        for output_index, weight in enumerate(matrix[input_index]):
            result[output_index] += float(value) * float(weight)
    return result


def _relu(value: float) -> float:
    return max(0.0, value)


@dataclass(frozen=True)
class PlannerDecision:
    plan_id: str
    current_stage: int
    next_stage: int
    selected_domain: str
    domain_probabilities: dict[str, float]
    confidence: float
    blocked: bool
    blocker_reasons: tuple[str, ...]
    tasks: tuple[dict[str, Any], ...]
    instruction_markdown: str
    evidence_digest: str


class NeuralTaskRouter:
    """Small neural router blended with transparent programme priorities."""

    def __init__(self, seed: int = 312, hidden: int = 12) -> None:
        self.first, self.first_bias, self.second, self.second_bias = _weights(seed, len(METRICS), hidden, len(DOMAINS))

    def _neural(self, vector: Sequence[float]) -> list[float]:
        hidden = [_relu(value) for value in _matvec(vector, self.first, self.first_bias)]
        return _softmax(_matvec(hidden, self.second, self.second_bias))

    @staticmethod
    def _programme_priors(metrics: Mapping[str, float]) -> list[float]:
        m = {key: _clip(metrics.get(key, 0.0)) for key in METRICS}
        deficits = {key: 1.0 - value for key, value in m.items()}
        raw = [
            deficits["provider_gate"] * 1.50 + deficits["automation_reliability"] * 0.25,
            deficits["compliance_ready"] * 1.35 + deficits["provider_gate"] * 0.20,
            deficits["crm_data_quality"] * 1.20 + deficits["labelled_outcomes_progress"] * 0.25,
            deficits["website_quality"] * 1.05 + deficits["conversion_validation"] * 0.35,
            deficits["interviews_progress"] * 1.05 + deficits["demonstrations_progress"] * 0.35,
            deficits["pipeline_health"] * 1.10 + deficits["revenue_validation"] * 0.40,
            deficits["delivery_capacity"] * 1.05 + deficits["demonstrations_progress"] * 0.25,
            deficits["partner_network_progress"] * 0.80 + deficits["funding_radar_progress"] * 0.80,
            deficits["labelled_outcomes_progress"] * 1.00 + deficits["drift_health"] * 0.60 + deficits["incident_health"] * 0.70,
        ]
        return _softmax(raw)

    def route(self, metrics: Mapping[str, float]) -> tuple[dict[str, float], float]:
        vector = [_clip(metrics.get(key, 0.0)) for key in METRICS]
        neural = self._neural(vector)
        priors = self._programme_priors(metrics)
        blended = [0.30 * neural[index] + 0.70 * priors[index] for index in range(len(DOMAINS))]
        probabilities = _softmax([math.log(max(value, 1e-12)) for value in blended])
        ordered = sorted(probabilities, reverse=True)
        margin = ordered[0] - ordered[1] if len(ordered) > 1 else ordered[0]
        confidence = _clip(0.55 + margin * 2.5)
        return {domain: probabilities[index] for index, domain in enumerate(DOMAINS)}, confidence


class AutonomousVenturePlanner:
    """Evidence-driven planner for the recursive n→n+1 programme.

    The planner generates bounded internal work instructions only. It never
    deploys, sends communications, changes prices, handles payments or promotes
    models. Those operations remain explicit human gates.
    """

    DOMAIN_TASKS: Mapping[str, tuple[tuple[str, str], ...]] = {
        "provider_runtime": (
            ("Run disposable provider suite", "Execute A01/A02 and neural shadow inference against the disposable CRM."),
            ("Compile evidence-safe results", "Record only row deltas, result codes, confidence, uncertainty and cleanup proof."),
            ("Close provider deployment", "Remove deployment properties and verify cleanup and rollback."),
        ),
        "compliance": (
            ("Complete launch compliance matrix", "Resolve privacy, consent, invoicing, legal-page and data-processing ownership."),
            ("Verify data boundaries", "Confirm personal data never enters GitHub artefacts or neural evidence ledgers."),
            ("Approve communication gates", "Document which outreach channels require permission and human approval."),
        ),
        "crm_data_quality": (
            ("Reconcile canonical codes", "Align service codes, aliases, statuses and prices across repository and CRM."),
            ("Audit missing identifiers", "Find Leads, Contacts and Companies lacking stable IDs or links."),
            ("Create reversible repair plan", "Generate proposed updates with before/after evidence and rollback."),
        ),
        "website_conversion": (
            ("Analyse conversion friction", "Use website and service evidence to rank clarity, trust and form blockers."),
            ("Generate controlled experiment", "Define one measurable copy, layout or intake experiment."),
            ("Validate bilingual parity", "Retest English/Spanish, mobile, accessibility and dark/light modes."),
        ),
        "customer_discovery": (
            ("Select interview candidates", "Rank permission-safe interview targets and evidence gaps."),
            ("Generate interview briefs", "Prepare role-specific questions without automatic sending."),
            ("Consolidate findings", "Store pseudonymised themes, objections and service-fit evidence."),
        ),
        "sales_pipeline": (
            ("Run neural pipeline review", "Score qualified leads, churn risk and next-best internal actions."),
            ("Prepare opportunity proposals", "Create reviewable Opportunity plans from canonical services and prices."),
            ("Generate follow-up queue", "Produce an internal ranked queue; communication remains human-approved."),
        ),
        "service_delivery": (
            ("Assess delivery capacity", "Compare expected workload with templates, automation and available hours."),
            ("Generate delivery plan", "Create task sequence, QA gates and client-input dependencies."),
            ("Prepare evidence template", "Define completion evidence, revision limits and handover criteria."),
        ),
        "partnerships_funding": (
            ("Map relationship graph", "Rank referral partners, institutions and funding sources by evidence and fit."),
            ("Prepare contact dossiers", "Generate research briefs and permission-safe contact routes."),
            ("Define partnership experiment", "Select one bounded referral or funding-validation test."),
        ),
        "model_evidence": (
            ("Append outcome memory", "Record pseudonymous predictions, outcomes and evidence digests."),
            ("Run calibration and drift", "Evaluate Brier score, ECE, log loss, feature drift and incidents."),
            ("Evaluate candidate model", "Compare against transparent baselines; no automatic promotion."),
        ),
    }

    def __init__(self, router: NeuralTaskRouter | None = None) -> None:
        self.router = router or NeuralTaskRouter()

    @staticmethod
    def _digest(metrics: Mapping[str, float], evidence: Mapping[str, Any]) -> str:
        import json

        payload = {"metrics": dict(sorted(metrics.items())), "evidence": evidence}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()

    @staticmethod
    def _blockers(metrics: Mapping[str, float], domain: str) -> list[str]:
        blockers: list[str] = []
        if domain != "provider_runtime" and _clip(metrics.get("provider_gate", 0.0)) < 0.35:
            blockers.append("provider_runtime_gate_is_primary_programme_blocker")
        if domain in {"sales_pipeline", "customer_discovery", "partnerships_funding"} and _clip(metrics.get("compliance_ready", 0.0)) < 0.50:
            blockers.append("communication_compliance_not_ready")
        if domain == "model_evidence" and _clip(metrics.get("labelled_outcomes_progress", 0.0)) < 0.05:
            blockers.append("no_labelled_outcomes_available")
        return blockers

    @staticmethod
    def _instruction(stage: int, domain: str, tasks: Sequence[dict[str, Any]], evidence_digest: str, blockers: Sequence[str]) -> str:
        task_lines = "\n".join(f"{index}. **{task['title']}** — {task['description']}" for index, task in enumerate(tasks, start=1))
        blocker_lines = "\n".join(f"- {item}" for item in blockers) or "- None."
        return f"""# Stage {stage + 1:03d} — {domain.replace('_', ' ').title()}

## Read first

- `orchestration/CURRENT.md`
- the previous stage report
- relevant architecture, schema and automation contracts
- evidence digest `{evidence_digest}`

## Objective

Resolve the highest-evidence programme bottleneck in **{domain.replace('_', ' ')}** using bounded, reversible and testable changes.

## Work package

{task_lines}

## Current blockers

{blocker_lines}

## Allowed

- Internal analysis, code, schemas, tests, templates and reversible planning.
- Synthetic or pseudonymised evidence.
- Shadow inference and counterfactual evaluation.

## Prohibited without explicit human approval

- External communication or publishing.
- Production deployment, CRM activation or destructive data changes.
- Pricing, invoicing, payments, contracts or legal decisions.
- Model self-modification or automatic promotion.

## Required validation

1. Run all repository tests.
2. Add domain-specific synthetic and adversarial cases.
3. Verify privacy, provenance, uncertainty and rollback controls.
4. Produce a complete stage report.
5. Generate the instruction for Stage {stage + 2:03d} from actual evidence.
"""

    def plan(self, current_stage: int, metrics: Mapping[str, float], evidence: Mapping[str, Any]) -> PlannerDecision:
        if current_stage < 0:
            raise ValueError("current_stage must be non-negative")
        probabilities, confidence = self.router.route(metrics)
        selected = max(probabilities, key=probabilities.get)
        blockers = self._blockers(metrics, selected)
        tasks = tuple({"title": title, "description": description, "execution": "internal_only"} for title, description in self.DOMAIN_TASKS[selected])
        digest = self._digest(metrics, evidence)
        plan_id = "NPLAN-" + hashlib.sha256(f"{current_stage}|{selected}|{digest}".encode("utf-8")).hexdigest()[:12].upper()
        instruction = self._instruction(current_stage, selected, tasks, digest, blockers)
        return PlannerDecision(
            plan_id=plan_id,
            current_stage=current_stage,
            next_stage=current_stage + 1,
            selected_domain=selected,
            domain_probabilities=probabilities,
            confidence=confidence,
            blocked=bool(blockers),
            blocker_reasons=tuple(blockers),
            tasks=tasks,
            instruction_markdown=instruction,
            evidence_digest=digest,
        )

    @staticmethod
    def as_dict(decision: PlannerDecision) -> dict[str, Any]:
        return asdict(decision)
