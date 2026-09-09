export type DecisionMode = "USE" | "BUILD" | "BUY" | "COMBINE" | "ABSTAIN";
export type AutonomyLevel = "L0" | "L1" | "L2" | "L3";
export type TruthLevel =
  | "verified_external_outcome"
  | "executed_connector_receipt"
  | "governed_source_evidence"
  | "human_approved_decision"
  | "evidence_backed_model_inference"
  | "hypothesis"
  | "generated_narrative";

export type OpportunityStatus =
  | "detected"
  | "researching"
  | "qualified"
  | "testing"
  | "authorized"
  | "executing"
  | "won"
  | "lost"
  | "archived"
  | "expired"
  | "rejected";

export interface EvidenceRef {
  id: string;
  source: string;
  kind: string;
  observedAt: string;
  digest?: string;
  authority?: number;
  freshness?: number;
  truthLevel?: TruthLevel;
}

export interface OpportunitySignal {
  id: string;
  sourceType: string;
  sourceRef?: string;
  signalType: string;
  title: string;
  summary?: string;
  rightsStatus: "unknown" | "permitted" | "restricted" | "blocked";
  observedAt: string;
  freshnessAt?: string;
  evidence: EvidenceRef[];
  payload: Record<string, unknown>;
}

export interface OpportunityMetrics {
  expectedRevenueLow?: number;
  expectedRevenueHigh?: number;
  expectedContributionMarginPct?: number;
  paidDemandEvidence: number;
  qualifiedDemandEvidence: number;
  automationPotential: number;
  recurringPotential: number;
  strategicFit: number;
  reversibility: number;
  evidenceQuality: number;
  deliveryEffortHours: number;
  timeToCashDays: number;
  uncertainty: number;
  rightsLegalComplexity: number;
  downsideRisk: number;
}

export interface Opportunity {
  id: string;
  niche: string;
  productCode?: string;
  targetEntityRef?: string;
  title: string;
  problemEvidence?: string;
  evidence: EvidenceRef[];
  metrics: OpportunityMetrics;
  decisionMode?: DecisionMode;
  score?: number;
  nextTest?: string;
  blocker?: string;
  status: OpportunityStatus;
}

export interface GenomeGenes {
  productComposition?: string[];
  targetSegment?: string;
  geography?: string[];
  problemFrame?: string;
  channels?: string[];
  priceFloor?: number;
  priceCeiling?: number;
  slaDays?: number;
  cta?: string;
  reportVariant?: string;
  qualificationThreshold?: number;
  followUpDays?: number[];
  acquisitionWeight?: number;
  upsellWeight?: number;
  exploitWeight?: number;
  adjacencyWeight?: number;
  explorationWeight?: number;
  [key: string]: unknown;
}

export interface CommercialGenome {
  id: string;
  lineageId: string;
  niche: string;
  generation: number;
  variantName: string;
  parentIds: string[];
  genes: GenomeGenes;
  explorationBudget: number;
  telomere: number;
  fitness?: number;
  confidence?: number;
  verifiedObservations: number;
  verifiedSuccesses: number;
  paidSuccesses: number;
  status: "experimental" | "active" | "champion" | "senescent" | "archived" | "blocked";
}

export interface FitnessObservation {
  id: string;
  genomeId: string;
  verified: boolean;
  paid: boolean;
  revenue?: number;
  directCost?: number;
  contributionMargin?: number;
  outcomeScore?: number;
  kind: string;
}

export interface PolicyEnvelope {
  version: string;
  actionClass: string;
  maxAutonomy: AutonomyLevel;
  enabled: boolean;
  prerequisites?: string[];
  limits?: Record<string, number | string | boolean | string[]>;
  allowedAgents?: string[];
  allowedConnectors?: string[];
  expiresAt?: string;
}

export interface ProposedAction {
  id: string;
  actionClass: string;
  actorAgent: string;
  autonomyLevel: AutonomyLevel;
  connector?: string;
  reversible: boolean;
  hasReceiptAdapter: boolean;
  rightsSatisfied: boolean;
  consentSatisfied: boolean;
  payload: Record<string, unknown>;
  externalEffect?: "none" | "internal" | "external";
  estimatedExternalCostEur?: number;
  batchSize?: number;
  targetRef?: string;
  expiresAt?: string;
}

export interface PolicyDecision {
  allowed: boolean;
  requiresHumanApproval: boolean;
  reason: string;
  policyVersion?: string;
}

export interface ExecutionReceipt {
  correlationId: string;
  idempotencyKey: string;
  actorAgent: string;
  actionClass: string;
  policyVersion: string;
  policyDecision: string;
  inputDigest: string;
  outputDigest?: string;
  connectorReceipt?: Record<string, unknown>;
  status: "started" | "succeeded" | "failed" | "blocked" | "queued" | "cancelled";
  startedAt: string;
  completedAt?: string;
  verified?: boolean;
  retryable?: boolean;
  error?: Record<string, unknown>;
}

export interface OpportunityDecision {
  mode: DecisionMode;
  rationale: string[];
  score: number;
}

export interface MutationPlan {
  parentGenomeId: string;
  changedGenes: Partial<GenomeGenes>;
  reason: string;
}

export interface EvolutionConstitution {
  maxGenesChangedPerMutation: number;
  minVerifiedObservationsForCrossover: number;
  minVerifiedSuccessesForPromotion: number;
  telomereDecayOnFailure: number;
  telomereRestoreOnPaidSuccess: number;
  explorationBudgetFloor: number;
}

export interface OutcomeVerification {
  verified: boolean;
  reason: string;
  truthLevel: TruthLevel;
  evidenceRefs?: EvidenceRef[];
}

export interface JobDefinition {
  jobKey: string;
  name: string;
  triggerType: "cron" | "event" | "manual" | "condition";
  scheduleExpr?: string;
  timezone: string;
  eventTopic?: string;
  handlerKey: string;
  ownerAgent: string;
  autonomyLevel: AutonomyLevel;
  policyKey?: string;
  requiredConnectors: string[];
  enabled: boolean;
  maxRuntimeSeconds: number;
  maxAttempts: number;
  concurrencyLimit: number;
}
