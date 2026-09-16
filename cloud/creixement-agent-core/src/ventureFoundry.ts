export type VentureTruthLevel =
  | "verified_external_outcome"
  | "executed_connector_receipt"
  | "governed_source_evidence"
  | "human_approved_business_decision"
  | "evidence_backed_inference"
  | "hypothesis"
  | "generated_narrative";

export type VentureStage =
  | "hypothesis"
  | "discovery"
  | "experiment"
  | "incubating"
  | "operating"
  | "scaling"
  | "paused"
  | "archived";

export type VentureDecision = "ignore" | "recommend" | "experiment" | "incubate" | "escalate";

export interface VentureOpportunity {
  id: string;
  title: string;
  niche: string;
  productCode?: string | null;
  status: string;
  truthLevel: VentureTruthLevel;
  evidenceRefs: string[];
  evidenceQuality: number;
  confidence: number;
  strategicFit: number;
  automationPotential: number;
  recurringPotential: number;
  reversibility: number;
  rightsLegalComplexity: number;
  downsideRisk: number;
  uncertainty: number;
  expectedRevenueLowEur?: number | null;
  expectedRevenueHighEur?: number | null;
  deliveryEffortHours?: number | null;
  timeToCashDays?: number | null;
  blocker?: string | null;
  expiresAt?: string | null;
}

export interface VentureFoundryContext {
  economicL2Open: boolean;
  experimentSlotsRemaining: number;
  projectSlotsRemaining: number;
  now?: string;
}

export interface VentureCandidate {
  candidateKey: string;
  projectKey: string;
  title: string;
  niche: string;
  productCode: string | null;
  stage: VentureStage;
  decision: VentureDecision;
  score: number;
  sourceOpportunityId: string;
  truthLevel: VentureTruthLevel;
  evidenceRefs: string[];
  autonomy: "L1" | "L2" | "L3";
  requiresOwner: boolean;
  reasons: string[];
  gates: {
    sourceUsable: boolean;
    evidencePresent: boolean;
    evidenceGoverned: boolean;
    evidenceQuality: boolean;
    confidence: boolean;
    strategicFit: boolean;
    reversible: boolean;
    riskBounded: boolean;
    rightsBounded: boolean;
    experimentCapacity: boolean;
    incubationCapacity: boolean;
    economicL2Open: boolean;
  };
}

export const VENTURE_TRUTH_STRENGTH: Record<VentureTruthLevel, number> = {
  verified_external_outcome: 7,
  executed_connector_receipt: 6,
  governed_source_evidence: 5,
  human_approved_business_decision: 4,
  evidence_backed_inference: 3,
  hypothesis: 2,
  generated_narrative: 1,
};

const ACTIONABLE_STATUSES = new Set(["qualified", "actionable", "testing", "exploring"]);

function clamp01(value: number): number {
  return Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
}

function finite(value: number | null | undefined, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function slug(input: string): string {
  const value = input
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return value || "venture";
}

function isExpired(expiresAt: string | null | undefined, now: string): boolean {
  if (!expiresAt) return false;
  const expiry = Date.parse(expiresAt);
  const current = Date.parse(now);
  if (!Number.isFinite(expiry) || !Number.isFinite(current)) return true;
  return expiry <= current;
}

export function ventureOpportunityScore(opportunity: VentureOpportunity): number {
  const revenueMid = Math.max(
    0,
    (finite(opportunity.expectedRevenueLowEur) + finite(opportunity.expectedRevenueHighEur)) / 2,
  );
  const revenueSignal = revenueMid > 0 ? Math.min(1, Math.log1p(revenueMid) / Math.log1p(50_000)) : 0;
  const timeSignal = 1 - Math.min(1, Math.max(0, finite(opportunity.timeToCashDays, 120)) / 180);
  const effortSignal = 1 - Math.min(1, Math.max(0, finite(opportunity.deliveryEffortHours, 80)) / 160);
  const evidence = clamp01(opportunity.evidenceQuality);
  const confidence = clamp01(opportunity.confidence);
  const fit = clamp01(opportunity.strategicFit);
  const automation = clamp01(opportunity.automationPotential);
  const recurring = clamp01(opportunity.recurringPotential);
  const reversibility = clamp01(opportunity.reversibility);
  const risk = clamp01(opportunity.downsideRisk);
  const uncertainty = clamp01(opportunity.uncertainty);
  const rights = clamp01(opportunity.rightsLegalComplexity);

  const upside =
    evidence * 0.19
    + confidence * 0.15
    + fit * 0.18
    + automation * 0.10
    + recurring * 0.09
    + reversibility * 0.08
    + revenueSignal * 0.09
    + timeSignal * 0.06
    + effortSignal * 0.06;
  const penalty = risk * 0.10 + uncertainty * 0.08 + rights * 0.08;
  return Number(Math.max(0, Math.min(1, upside - penalty)).toFixed(6));
}

export function compileVentureCandidate(
  opportunity: VentureOpportunity,
  context: VentureFoundryContext,
): VentureCandidate {
  const now = context.now ?? new Date().toISOString();
  const evidenceRefs = [...new Set(opportunity.evidenceRefs.filter((ref) => ref.trim().length > 0))].sort();
  const evidenceStrength = VENTURE_TRUTH_STRENGTH[opportunity.truthLevel];
  const sourceUsable = ACTIONABLE_STATUSES.has(opportunity.status.toLowerCase())
    && !opportunity.blocker
    && !isExpired(opportunity.expiresAt, now);
  const evidencePresent = evidenceRefs.length > 0;
  const evidenceGoverned = evidenceStrength >= VENTURE_TRUTH_STRENGTH.governed_source_evidence;
  const evidenceQuality = clamp01(opportunity.evidenceQuality) >= 0.65;
  const confidence = clamp01(opportunity.confidence) >= 0.60;
  const strategicFit = clamp01(opportunity.strategicFit) >= 0.55;
  const reversible = clamp01(opportunity.reversibility) >= 0.80;
  const riskBounded = clamp01(opportunity.downsideRisk) <= 0.45;
  const rightsBounded = clamp01(opportunity.rightsLegalComplexity) <= 0.50;
  const experimentCapacity = context.experimentSlotsRemaining > 0;
  const incubationCapacity = context.projectSlotsRemaining > 0;
  const economicL2Open = context.economicL2Open;
  const score = ventureOpportunityScore(opportunity);

  const gates = {
    sourceUsable,
    evidencePresent,
    evidenceGoverned,
    evidenceQuality,
    confidence,
    strategicFit,
    reversible,
    riskBounded,
    rightsBounded,
    experimentCapacity,
    incubationCapacity,
    economicL2Open,
  };

  const reasons: string[] = [];
  if (!sourceUsable) reasons.push("source opportunity is blocked, expired, or not actionable");
  if (!evidencePresent) reasons.push("no evidence references are attached");
  if (!rightsBounded) reasons.push("rights/legal complexity exceeds automatic foundry bounds");
  if (!riskBounded) reasons.push("downside risk exceeds automatic foundry bounds");

  let decision: VentureDecision = "ignore";
  let stage: VentureStage = "hypothesis";
  let autonomy: VentureCandidate["autonomy"] = "L1";
  let requiresOwner = false;

  if (sourceUsable && evidencePresent) {
    decision = "recommend";
    stage = "discovery";
    reasons.push("Kairon may retain an evidence-linked project hypothesis at L1");

    const experimentReady = evidenceStrength >= VENTURE_TRUTH_STRENGTH.evidence_backed_inference
      && clamp01(opportunity.evidenceQuality) >= 0.45
      && clamp01(opportunity.confidence) >= 0.45
      && strategicFit
      && rightsBounded
      && riskBounded
      && experimentCapacity
      && economicL2Open;

    if (experimentReady) {
      decision = "experiment";
      stage = "experiment";
      autonomy = "L2";
      reasons.push("bounded internal experiment satisfies the L2 exploration floor and supervised economic gate");
    } else if (!economicL2Open) {
      reasons.push("economic L2 is closed, so Kairon retains the project as an L1 recommendation only");
    }

    const incubationReady = evidenceGoverned
      && evidenceQuality
      && confidence
      && strategicFit
      && reversible
      && riskBounded
      && rightsBounded
      && experimentCapacity
      && incubationCapacity
      && economicL2Open;

    if (incubationReady) {
      decision = "incubate";
      stage = "incubating";
      autonomy = "L2";
      reasons.push("governed evidence and the supervised economic L2 gate permit reversible incubation");
    }
  }

  // The foundry never auto-promotes a project into operating/scaling state and never
  // crosses an external/consequential boundary. Such transitions require verified
  // outcomes and the normal Kairon authority membrane; L3 remains owner-controlled.
  if (opportunity.status.toLowerCase() === "owner_required") {
    decision = "escalate";
    stage = "discovery";
    autonomy = "L3";
    requiresOwner = true;
    reasons.push("source explicitly requires owner authority");
  }

  const candidateKey = `venture:${opportunity.id}`;
  const projectKey = `venture-${slug(opportunity.niche)}-${slug(opportunity.title)}-${opportunity.id.slice(0, 8).toLowerCase()}`;

  return {
    candidateKey,
    projectKey,
    title: opportunity.title,
    niche: opportunity.niche,
    productCode: opportunity.productCode ?? null,
    stage,
    decision,
    score,
    sourceOpportunityId: opportunity.id,
    truthLevel: opportunity.truthLevel,
    evidenceRefs,
    autonomy,
    requiresOwner,
    reasons,
    gates,
  };
}

export function selectVentureCandidates(
  opportunities: VentureOpportunity[],
  context: VentureFoundryContext,
  limit = 12,
): VentureCandidate[] {
  if (limit <= 0) return [];
  return opportunities
    .map((opportunity) => compileVentureCandidate(opportunity, context))
    .filter((candidate) => candidate.decision !== "ignore")
    .sort((a, b) => {
      const order: Record<VentureDecision, number> = { incubate: 5, experiment: 4, recommend: 3, escalate: 2, ignore: 1 };
      return order[b.decision] - order[a.decision] || b.score - a.score || a.candidateKey.localeCompare(b.candidateKey);
    })
    .slice(0, limit);
}

export function mayAutoPromoteToOperating(input: {
  verifiedExternalOutcomes: number;
  executedReceipts: number;
  ownerApproved?: boolean;
}): boolean {
  // Operating status is materially stronger than an incubation record. The foundry
  // intentionally cannot establish it from forecasts or hypotheses alone.
  return input.verifiedExternalOutcomes > 0 && input.executedReceipts > 0 && input.ownerApproved === true;
}
