import {
  compileSelfHealPlan,
  decideKaironAction,
  economicPriority,
  type KaironBudgetState,
  type KaironDecision,
  type KaironWorkItem,
  type RuntimeHealthSnapshot,
} from "./kairon.js";
import {
  homeostasisAdjustment,
  immuneDecision,
  metabolicBudget,
  redQueenPressure,
  slimeMoldAllocate,
  swarmQuorum,
  woundHealingPriority,
  type EcologicalRoute,
  type EnvironmentState,
  type ImmunePattern,
  type OrganismState,
  type QuorumSignal,
} from "./bioecology.js";
import {
  canaryPromotion,
  conwayStableDigest,
  deterministicAuthorityTraversal,
  hardVetoSelection,
  updateHysteresis,
  type AuthorityNode,
  type CanaryObservation,
  type HysteresisState,
} from "./conwayEcology.js";

/**
 * Kairon supervisory composition layer.
 *
 * Conway-inspired mechanisms influence ranking, recovery, experimentation and
 * promotion confidence. They NEVER expand Kairon's constitutional authority.
 * L3 boundaries, rights/consent, durable receipts and the L2 ceiling remain
 * hard constraints outside fitness/evolution.
 */

export type KaironTruthLevel =
  | "verified_external_outcome"
  | "executed_connector_receipt"
  | "governed_source_evidence"
  | "human_approved_business_decision"
  | "evidence_backed_inference"
  | "hypothesis"
  | "generated_narrative";

export type KaironLane = "exploit" | "adjacency" | "exploration";
export type KaironDomain = "maintenance" | "economic" | "research";

export interface KaironEvidenceSignal {
  key: string;
  source: string;
  truthLevel: KaironTruthLevel;
  confidence: number;
  support: number;
  independent: boolean;
}

export interface KaironSupervisoryCandidate {
  workItem: KaironWorkItem;
  domain: KaironDomain;
  lane: KaironLane;
  authorityNodeKey: string;
  routeKey: string;
  evidence: KaironEvidenceSignal[];
  quorumRequired: boolean;
  immuneSignature: string | null;
}

export interface KaironResourceDemand {
  available: number;
  maintenanceDemand: number;
  executionDemand: number;
  explorationDemand: number;
}

export interface KaironSupervisorInput {
  candidates: KaironSupervisoryCandidate[];
  budget: KaironBudgetState;
  authorityGraph: AuthorityNode[];
  routes: EcologicalRoute[];
  organism: OrganismState;
  environment: EnvironmentState;
  immunePatterns: ImmunePattern[];
  runtimeHealth: RuntimeHealthSnapshot & { failedJobs: number };
  resourceDemand: KaironResourceDemand;
  canaries: CanaryObservation[];
  priorEconomicL2State: HysteresisState;
  economicEvidenceReady: boolean;
}

export interface KaironCandidateDecision {
  candidateId: string;
  decision: KaironDecision;
  requiresOwner: boolean;
  score: number;
  truthLevel: KaironTruthLevel;
  truthStrength: number;
  quorumReached: boolean;
  independentSources: number;
  immuneDisposition: "allow" | "challenge" | "block";
  authoritySafe: boolean;
  authorityDigest: string;
  routeAllocation: number;
  reasons: string[];
}

export interface KaironSupervisorResult {
  mode: "supervisory";
  autonomyCeiling: "L2";
  economicL2: {
    state: HysteresisState["state"];
    score: number;
    enabled: boolean;
    canaryPromotable: boolean;
    canaryPassRate: number;
    reason: string;
  };
  ecology: {
    redQueenPressure: number;
    woundHealingPriority: number;
    explorationMultiplier: number;
    executionMultiplier: number;
    resourceAllocation: ReturnType<typeof metabolicBudget>;
    routeAllocation: Array<{ key: string; allocation: number; desirability: number }>;
  };
  recoveryPlan: ReturnType<typeof compileSelfHealPlan>;
  decisions: KaironCandidateDecision[];
  nextBestCandidateId: string | null;
  hardVetoedCandidateIds: string[];
  proofDigest: string;
}

export const KAIRON_TRUTH_STRENGTH: Record<KaironTruthLevel, number> = {
  verified_external_outcome: 7,
  executed_connector_receipt: 6,
  governed_source_evidence: 5,
  human_approved_business_decision: 4,
  evidence_backed_inference: 3,
  hypothesis: 2,
  generated_narrative: 1,
};

const TRUTH_LEVELS_DESC = (Object.keys(KAIRON_TRUTH_STRENGTH) as KaironTruthLevel[])
  .sort((a, b) => KAIRON_TRUTH_STRENGTH[b] - KAIRON_TRUTH_STRENGTH[a]);

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function strongestTruth(evidence: KaironEvidenceSignal[]): KaironTruthLevel {
  for (const level of TRUTH_LEVELS_DESC) {
    if (evidence.some((signal) => signal.truthLevel === level)) return level;
  }
  return "generated_narrative";
}

function evidenceQuorum(evidence: KaironEvidenceSignal[]): ReturnType<typeof swarmQuorum> {
  const signals: QuorumSignal[] = evidence.map((signal) => ({
    source: signal.source,
    support: clamp01(signal.support),
    confidence: clamp01(signal.confidence),
    independentEvidence: signal.independent,
  }));
  return swarmQuorum(signals, 0.67, 2);
}

function routeAllocationMap(routes: EcologicalRoute[]): Map<string, { allocation: number; desirability: number }> {
  return new Map(slimeMoldAllocate(routes).map((route) => [route.key, {
    allocation: route.allocation,
    desirability: route.desirability,
  }]));
}

function immuneFor(signature: string | null, patterns: ImmunePattern[]) {
  if (!signature) return { action: "allow" as const, confidence: 1, reason: "no immune signature attached" };
  const pattern = patterns.find((entry) => entry.signature === signature);
  if (!pattern) return { action: "challenge" as const, confidence: 0, reason: "unknown signature requires evidence" };
  return immuneDecision(pattern);
}

function laneMultiplier(lane: KaironLane, redQueen: number, explorationMultiplier: number): number {
  if (lane === "exploit") return 1.15 - 0.15 * redQueen;
  if (lane === "adjacency") return 0.9 + 0.2 * redQueen;
  return (0.72 + 0.48 * redQueen) * explorationMultiplier;
}

function truthAllowsAutomaticL2(level: KaironTruthLevel): boolean {
  return KAIRON_TRUTH_STRENGTH[level] >= KAIRON_TRUTH_STRENGTH.governed_source_evidence;
}

function compileEconomicGate(input: KaironSupervisorInput, woundPriority: number, executionMultiplier: number) {
  const canary = canaryPromotion(input.canaries, { minRuns: 5, minPassRate: 1 });
  const runtimeHealthScore = clamp01(1 - woundPriority);
  const executionHealth = clamp01(executionMultiplier / 1.2);
  const score = clamp01(
    (canary.promotable ? 0.45 : 0)
      + (input.economicEvidenceReady ? 0.25 : 0)
      + 0.20 * runtimeHealthScore
      + 0.10 * executionHealth,
  );
  const hysteresis = updateHysteresis(input.priorEconomicL2State, score, {
    enterThreshold: 0.78,
    exitThreshold: 0.52,
    dwellEnter: 2,
    dwellExit: 2,
  });
  const enabled = hysteresis.state === "on"
    && canary.promotable
    && input.economicEvidenceReady
    && woundPriority < 0.8;
  const reason = enabled
    ? "Sustained evidence, deterministic receipted canaries and runtime health satisfy the L2 economic gate."
    : canary.reason;
  return { hysteresis, score, enabled, canary, reason };
}

export function compileKaironSupervisorCycle(input: KaironSupervisorInput): KaironSupervisorResult {
  const homeostasis = homeostasisAdjustment(input.organism, input.environment);
  const redQueen = redQueenPressure(input.organism, input.environment);
  const woundPriority = woundHealingPriority({
    failedJobs: input.runtimeHealth.failedJobs,
    deadLetters: input.runtimeHealth.openDeadLetters,
    openCircuits: input.runtimeHealth.openCircuits,
    criticalDrift: input.runtimeHealth.criticalDrift,
    staleHeartbeat: input.runtimeHealth.staleHeartbeat,
  });
  const resources = metabolicBudget(input.resourceDemand);
  const economicGate = compileEconomicGate(input, woundPriority, homeostasis.executionMultiplier);
  const routeMap = routeAllocationMap(input.routes);

  const decisions = input.candidates.map((candidate): KaironCandidateDecision => {
    const base = decideKaironAction(candidate.workItem, input.budget);
    const truthLevel = strongestTruth(candidate.evidence);
    const quorum = evidenceQuorum(candidate.evidence);
    const immune = immuneFor(candidate.immuneSignature, input.immunePatterns);
    const authority = deterministicAuthorityTraversal(input.authorityGraph, candidate.authorityNodeKey, {
      maxDepth: 12,
      maxPaths: 200000,
    });
    const authoritySafe = authority.forbiddenPaths.length === 0;
    const route = routeMap.get(candidate.routeKey) ?? { allocation: 0, desirability: 0 };
    const reasons = [base.reason];
    let decision = base.decision;
    let requiresOwner = base.requiresOwner;

    if (!authoritySafe) {
      decision = candidate.workItem.externalEffect ? "escalate" : "abstain";
      requiresOwner = candidate.workItem.externalEffect;
      reasons.push("Deterministic authority traversal reaches a forbidden/L3 path.");
    }
    if (immune.action === "block") {
      decision = "abstain";
      requiresOwner = false;
      reasons.push(`Immune memory blocks this signature: ${immune.reason}`);
    } else if (immune.action === "challenge" && decision === "operate") {
      decision = "recommend";
      reasons.push(`Immune memory requires sandbox/challenge before automatic execution: ${immune.reason}`);
    }
    if (candidate.quorumRequired && !quorum.reached && decision === "operate") {
      decision = "recommend";
      reasons.push("Independent-evidence swarm quorum is not satisfied.");
    }
    if (decision === "operate" && !truthAllowsAutomaticL2(truthLevel)) {
      decision = "recommend";
      reasons.push("Truth floor for automatic L2 is not met; governed evidence or stronger proof is required.");
    }
    if (candidate.domain === "economic" && decision === "operate" && !economicGate.enabled) {
      decision = "recommend";
      reasons.push("Economic L2 hysteresis/canary gate is closed.");
    }
    if (candidate.domain === "research" && decision === "operate") {
      decision = "recommend";
      reasons.push("Research remains recommendation/experiment-scoped; it does not auto-cross into consequential execution.");
    }

    const baseScore = economicPriority(candidate.workItem);
    const evidenceWeight = 0.55 + 0.45 * (KAIRON_TRUTH_STRENGTH[truthLevel] / 7);
    const ecologicalWeight = laneMultiplier(candidate.lane, redQueen, homeostasis.explorationMultiplier);
    const routeWeight = 0.65 + route.allocation;
    const healthWeight = candidate.domain === "maintenance"
      ? 0.85 + 0.65 * woundPriority
      : 0.75 + 0.25 * clamp01(homeostasis.executionMultiplier);
    const score = baseScore * evidenceWeight * ecologicalWeight * routeWeight * healthWeight;

    return {
      candidateId: candidate.workItem.id,
      decision,
      requiresOwner,
      score,
      truthLevel,
      truthStrength: KAIRON_TRUTH_STRENGTH[truthLevel],
      quorumReached: quorum.reached,
      independentSources: quorum.independentSources,
      immuneDisposition: immune.action,
      authoritySafe,
      authorityDigest: authority.digest,
      routeAllocation: route.allocation,
      reasons,
    };
  }).sort((a, b) => b.score - a.score || a.candidateId.localeCompare(b.candidateId));

  const selection = hardVetoSelection(decisions.map((decision) => ({
    key: decision.candidateId,
    expectedValue: Math.max(0, decision.score),
    confidence: decision.truthStrength / 7,
    strategicFit: decision.quorumReached ? 1 : 0.72,
    risk: decision.authoritySafe ? 0.15 : 1,
    hardVeto: decision.decision === "abstain",
    vetoReasons: decision.decision === "abstain" ? decision.reasons : [],
  })));

  const recoveryPlan = compileSelfHealPlan(input.runtimeHealth);
  const routeAllocation = [...routeMap.entries()]
    .map(([key, value]) => ({ key, ...value }))
    .sort((a, b) => b.allocation - a.allocation || a.key.localeCompare(b.key));

  const stableProof = {
    autonomyCeiling: "L2",
    economicL2: {
      state: economicGate.hysteresis.state,
      score: economicGate.score,
      enabled: economicGate.enabled,
      canaryPromotable: economicGate.canary.promotable,
      canaryPassRate: economicGate.canary.passRate,
    },
    ecology: {
      redQueenPressure: redQueen,
      woundHealingPriority: woundPriority,
      explorationMultiplier: homeostasis.explorationMultiplier,
      executionMultiplier: homeostasis.executionMultiplier,
      resourceAllocation: resources,
      routeAllocation,
    },
    recoveryPlan,
    decisions,
    nextBestCandidateId: selection.selected?.key ?? null,
    hardVetoedCandidateIds: selection.vetoed.map((item) => item.key).sort(),
  };

  return {
    mode: "supervisory",
    autonomyCeiling: "L2",
    economicL2: {
      state: economicGate.hysteresis.state,
      score: economicGate.score,
      enabled: economicGate.enabled,
      canaryPromotable: economicGate.canary.promotable,
      canaryPassRate: economicGate.canary.passRate,
      reason: economicGate.reason,
    },
    ecology: {
      redQueenPressure: redQueen,
      woundHealingPriority: woundPriority,
      explorationMultiplier: homeostasis.explorationMultiplier,
      executionMultiplier: homeostasis.executionMultiplier,
      resourceAllocation: resources,
      routeAllocation,
    },
    recoveryPlan,
    decisions,
    nextBestCandidateId: selection.selected?.key ?? null,
    hardVetoedCandidateIds: selection.vetoed.map((item) => item.key).sort(),
    proofDigest: conwayStableDigest(stableProof),
  };
}
