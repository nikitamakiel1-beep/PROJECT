export type AutonomyLevel = "L0" | "L1" | "L2" | "L3";
export type KaironDecision = "observe" | "recommend" | "operate" | "escalate" | "abstain";

export interface KaironWorkItem {
  id: string;
  actionClass: string;
  requestedAutonomy: AutonomyLevel;
  reversible: boolean;
  externalEffect: boolean;
  connectorReady: boolean;
  rightsPermitted: boolean;
  receiptCapable: boolean;
  estimatedExternalCostEur: number;
  expectedValue: number;
  confidence: number;
  strategicFit: number;
  risk: number;
  uncertainty: number;
  ownerOnly?: boolean;
}

export interface KaironBudgetState {
  remainingExternalCostEur: number;
  remainingAgentRuns: number;
  remainingExperiments: number;
  remainingEnrichments: number;
}

export interface KaironDecisionResult {
  decision: KaironDecision;
  score: number;
  reason: string;
  requiresOwner: boolean;
}

const OWNER_ONLY = new Set([
  "contracts_and_signatures",
  "bank_transfers_and_unrestricted_payments",
  "property_offers_or_purchases",
  "financing_commitments",
  "irreversible_governed_deletion",
  "rights_or_consent_bypass",
  "unreceipted_external_action",
]);

const RANK: Record<AutonomyLevel, number> = { L0: 0, L1: 1, L2: 2, L3: 3 };

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

export function economicPriority(item: KaironWorkItem): number {
  const value = Math.max(0, item.expectedValue);
  const confidence = clamp01(item.confidence);
  const fit = clamp01(item.strategicFit);
  const risk = Math.max(0.05, clamp01(item.risk));
  const uncertainty = Math.max(0.05, clamp01(item.uncertainty));
  return (value * confidence * fit) / (risk * uncertainty);
}

export function decideKaironAction(item: KaironWorkItem, budget: KaironBudgetState): KaironDecisionResult {
  const score = economicPriority(item);
  const explicitOwnerOnly = item.ownerOnly === true || OWNER_ONLY.has(item.actionClass);

  if (!item.rightsPermitted) {
    return { decision: "abstain", score, reason: "Rights or consent are not permitted.", requiresOwner: false };
  }
  if (!item.receiptCapable && (item.externalEffect || RANK[item.requestedAutonomy] >= RANK.L2)) {
    return { decision: "abstain", score, reason: "Execution cannot produce a durable receipt.", requiresOwner: false };
  }
  if (explicitOwnerOnly || item.requestedAutonomy === "L3") {
    return { decision: "escalate", score, reason: "Constitutionally non-delegable or L3 action.", requiresOwner: true };
  }
  if (item.externalEffect) {
    return { decision: "escalate", score, reason: "External effect requires an explicit versioned authorization envelope.", requiresOwner: true };
  }
  if (RANK[item.requestedAutonomy] <= RANK.L1) {
    return {
      decision: item.requestedAutonomy === "L0" ? "observe" : "recommend",
      score,
      reason: "Within observation/recommendation autonomy.",
      requiresOwner: false,
    };
  }
  if (!item.reversible) {
    return { decision: "escalate", score, reason: "L2 automatic operation requires reversibility.", requiresOwner: true };
  }
  if (!item.connectorReady) {
    return { decision: "recommend", score, reason: "Required runtime connector is not ready.", requiresOwner: false };
  }
  if (item.estimatedExternalCostEur > budget.remainingExternalCostEur) {
    return { decision: "recommend", score, reason: "External-cost budget would be exceeded.", requiresOwner: false };
  }
  if (budget.remainingAgentRuns <= 0) {
    return { decision: "recommend", score, reason: "Daily agent-run budget exhausted.", requiresOwner: false };
  }
  return { decision: "operate", score, reason: "Bounded, reversible, receipted L2 action is authorized for automatic operation.", requiresOwner: false };
}

export interface AttentionCandidate {
  id: string;
  lane: "exploit" | "adjacency" | "exploration";
  score: number;
}

export function allocateAttention(candidates: AttentionCandidate[], slots: number): AttentionCandidate[] {
  if (slots <= 0) return [];
  const targets = {
    exploit: Math.floor(slots * 0.70),
    adjacency: Math.floor(slots * 0.20),
    exploration: Math.floor(slots * 0.10),
  };
  let assigned = targets.exploit + targets.adjacency + targets.exploration;
  targets.exploit += slots - assigned;

  const byLane = (lane: AttentionCandidate["lane"]) => candidates
    .filter((candidate) => candidate.lane === lane)
    .sort((a, b) => b.score - a.score);

  const selected = [
    ...byLane("exploit").slice(0, targets.exploit),
    ...byLane("adjacency").slice(0, targets.adjacency),
    ...byLane("exploration").slice(0, targets.exploration),
  ];

  const selectedIds = new Set(selected.map((item) => item.id));
  const remainder = candidates
    .filter((item) => !selectedIds.has(item.id))
    .sort((a, b) => b.score - a.score)
    .slice(0, Math.max(0, slots - selected.length));

  return [...selected, ...remainder].slice(0, slots);
}

export interface RuntimeHealthSnapshot {
  staleHeartbeat: boolean;
  criticalDrift: number;
  criticalIncidents: number;
  openDeadLetters: number;
  openCircuits: number;
  connectorBlockers: number;
}

export type SelfHealAction =
  | "reap_expired_leases"
  | "retry_transient_failures"
  | "reconcile_runtime"
  | "triage_dead_letters"
  | "degrade_readiness"
  | "block_connector_jobs";

export function compileSelfHealPlan(health: RuntimeHealthSnapshot): SelfHealAction[] {
  const actions: SelfHealAction[] = ["reap_expired_leases", "reconcile_runtime"];
  if (health.staleHeartbeat) actions.push("degrade_readiness");
  if (health.openDeadLetters > 0) actions.push("triage_dead_letters", "retry_transient_failures");
  if (health.connectorBlockers > 0) actions.push("block_connector_jobs");
  return [...new Set(actions)];
}
