export type BioMechanism =
  | "slime_mold_routing"
  | "pheromone_foraging"
  | "swarm_quorum"
  | "sexual_recombination"
  | "asexual_budding"
  | "mutation"
  | "epigenetic_adaptation"
  | "telomere_senescence"
  | "red_queen_pressure"
  | "niche_speciation"
  | "homeostasis"
  | "hormesis"
  | "immune_memory"
  | "apoptosis_archive"
  | "hibernation"
  | "migration"
  | "symbiosis"
  | "competition"
  | "predator_prejudice_check"
  | "wound_healing"
  | "resource_metabolism";

export interface EcologicalRoute {
  key: string;
  nutrient: number;
  pheromone: number;
  friction: number;
  risk: number;
  capacity: number;
}

export interface RouteAllocation extends EcologicalRoute {
  desirability: number;
  allocation: number;
}

export interface QuorumSignal {
  source: string;
  support: number;
  confidence: number;
  independentEvidence: boolean;
}

export interface QuorumDecision {
  reached: boolean;
  weightedSupport: number;
  independentSources: number;
  reason: string;
}

export interface OrganismState {
  id: string;
  niche: string;
  generation: number;
  telomere: number;
  energy: number;
  fitness: number;
  confidence: number;
  novelty: number;
  stress: number;
  dormancy: number;
  traits: Record<string, number | string | boolean>;
  parentIds: string[];
  status: "experimental" | "active" | "champion" | "senescent" | "hibernating" | "archived" | "blocked";
}

export interface EnvironmentState {
  demand: number;
  competition: number;
  volatility: number;
  evidenceScarcity: number;
  resourceScarcity: number;
  failurePressure: number;
}

export interface ImmunePattern {
  signature: string;
  observations: number;
  failures: number;
  severity: number;
  lastSeenAt?: string;
}

export interface HomeostasisTargets {
  energy: number;
  stress: number;
  exploration: number;
}

export interface HomeostasisAdjustment {
  explorationMultiplier: number;
  executionMultiplier: number;
  recoveryPriority: number;
  reason: string[];
}

export interface RecombinationPlan {
  parentA: OrganismState;
  parentB: OrganismState;
  traitKeysFromB: string[];
  childId: string;
}

const clamp = (value: number, min = 0, max = 1): number => Math.max(min, Math.min(max, value));
const safe = (value: number): number => Number.isFinite(value) ? value : 0;

export function slimeMoldAllocate(routes: EcologicalRoute[]): RouteAllocation[] {
  if (routes.length === 0) return [];
  const scored = routes.map((route) => {
    const nutrient = Math.max(0.0001, safe(route.nutrient));
    const pheromone = Math.max(0.0001, safe(route.pheromone));
    const friction = 1 + Math.max(0, safe(route.friction));
    const risk = 1 + 2 * clamp(route.risk);
    const capacity = Math.max(0.0001, safe(route.capacity));
    const desirability = (Math.pow(nutrient, 1.35) * Math.pow(pheromone, 0.8) * Math.sqrt(capacity)) / (friction * risk);
    return { ...route, desirability };
  });
  const total = scored.reduce((sum, route) => sum + route.desirability, 0);
  if (total <= 0) return scored.map((route) => ({ ...route, allocation: 1 / scored.length }));
  return scored.map((route) => ({ ...route, allocation: route.desirability / total }));
}

export function reinforcePheromone(current: number, outcome: { verified: boolean; success: boolean; paid?: boolean; value?: number }, evaporation = 0.12): number {
  const evaporated = clamp(current) * (1 - clamp(evaporation, 0, 0.95));
  if (!outcome.verified) return evaporated;
  const reward = outcome.success ? 0.08 + (outcome.paid ? 0.1 : 0) + clamp((outcome.value ?? 0) / 10000, 0, 0.12) : -0.12;
  return clamp(evaporated + reward);
}

export function swarmQuorum(signals: QuorumSignal[], threshold = 0.67, minIndependentSources = 2): QuorumDecision {
  const independent = signals.filter((signal) => signal.independentEvidence);
  const denominator = signals.reduce((sum, signal) => sum + clamp(signal.confidence), 0);
  const numerator = signals.reduce((sum, signal) => sum + clamp(signal.support) * clamp(signal.confidence), 0);
  const weightedSupport = denominator > 0 ? numerator / denominator : 0;
  const reached = weightedSupport >= threshold && independent.length >= minIndependentSources;
  return {
    reached,
    weightedSupport,
    independentSources: independent.length,
    reason: reached ? "quorum reached with independent evidence" : "quorum not reached or evidence insufficiently independent",
  };
}

export function hormesisGain(stress: number): number {
  const s = clamp(stress);
  // Inverted-U: modest verified stress encourages adaptation; extremes suppress risky exploration.
  return clamp(4 * s * (1 - s));
}

export function redQueenPressure(organism: OrganismState, environment: EnvironmentState): number {
  const external = 0.30 * clamp(environment.competition)
    + 0.20 * clamp(environment.volatility)
    + 0.15 * clamp(environment.failurePressure)
    + 0.10 * clamp(environment.evidenceScarcity);
  const internal = 0.15 * (1 - clamp(organism.novelty)) + 0.10 * (1 - clamp(organism.fitness));
  return clamp(external + internal);
}

export function homeostasisAdjustment(
  organism: OrganismState,
  environment: EnvironmentState,
  targets: HomeostasisTargets = { energy: 0.65, stress: 0.35, exploration: 0.15 },
): HomeostasisAdjustment {
  const reasons: string[] = [];
  const energyDeficit = clamp(targets.energy - clamp(organism.energy), 0, 1);
  const stressExcess = clamp(clamp(organism.stress) - targets.stress, 0, 1);
  const scarcity = clamp(environment.resourceScarcity);
  let explorationMultiplier = 1;
  let executionMultiplier = 1;
  if (energyDeficit > 0.15) {
    explorationMultiplier *= 0.7;
    executionMultiplier *= 0.85;
    reasons.push("energy below homeostatic target");
  }
  if (stressExcess > 0.15) {
    explorationMultiplier *= 0.65;
    executionMultiplier *= 0.8;
    reasons.push("stress above homeostatic target");
  }
  if (scarcity > 0.6) {
    explorationMultiplier *= 0.8;
    reasons.push("resource scarcity favors exploit/recovery");
  }
  const adaptive = hormesisGain(organism.stress);
  explorationMultiplier *= 0.85 + 0.3 * adaptive;
  return {
    explorationMultiplier: clamp(explorationMultiplier, 0.2, 1.5),
    executionMultiplier: clamp(executionMultiplier, 0.2, 1.2),
    recoveryPriority: clamp(0.55 * energyDeficit + 0.35 * stressExcess + 0.1 * scarcity),
    reason: reasons.length > 0 ? reasons : ["within homeostatic envelope"],
  };
}

export function immuneDecision(pattern: ImmunePattern): { action: "allow" | "challenge" | "block"; confidence: number; reason: string } {
  if (pattern.observations <= 0) return { action: "challenge", confidence: 0, reason: "unknown signature requires evidence" };
  const failureRate = pattern.failures / pattern.observations;
  const confidence = clamp(Math.log2(pattern.observations + 1) / 6);
  if (pattern.severity >= 0.85 && failureRate >= 0.5 && pattern.observations >= 2) {
    return { action: "block", confidence, reason: "high-severity recurrent failure signature" };
  }
  if (failureRate >= 0.35 || pattern.severity >= 0.6) {
    return { action: "challenge", confidence, reason: "signature requires sandbox/probe before trust" };
  }
  return { action: "allow", confidence, reason: "observed signature remains below immune challenge threshold" };
}

export function asexualBud(parent: OrganismState, childId: string, traitMutations: Record<string, number | string | boolean> = {}): OrganismState {
  return {
    ...parent,
    id: childId,
    generation: parent.generation + 1,
    telomere: clamp(parent.telomere - 0.025),
    energy: clamp(parent.energy * 0.7),
    confidence: clamp(parent.confidence * 0.75),
    novelty: clamp(parent.novelty + 0.08),
    traits: { ...parent.traits, ...traitMutations },
    parentIds: [parent.id],
    status: "experimental",
  };
}

export function sexualRecombine(plan: RecombinationPlan): OrganismState {
  if (plan.parentA.niche !== plan.parentB.niche) throw new Error("sexual recombination requires same niche unless explicit speciation workflow is used");
  const keys = [...new Set(plan.traitKeysFromB)];
  const traits = { ...plan.parentA.traits };
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(plan.parentB.traits, key)) traits[key] = plan.parentB.traits[key]!;
  }
  return {
    ...plan.parentA,
    id: plan.childId,
    generation: Math.max(plan.parentA.generation, plan.parentB.generation) + 1,
    telomere: clamp((plan.parentA.telomere + plan.parentB.telomere) / 2 - 0.015),
    energy: clamp((plan.parentA.energy + plan.parentB.energy) / 2 * 0.75),
    fitness: 0,
    confidence: 0,
    novelty: clamp((plan.parentA.novelty + plan.parentB.novelty) / 2 + 0.12),
    stress: clamp((plan.parentA.stress + plan.parentB.stress) / 2),
    dormancy: 0,
    traits,
    parentIds: [plan.parentA.id, plan.parentB.id],
    status: "experimental",
  };
}

export function epigeneticAdaptation(organism: OrganismState, environment: EnvironmentState): Record<string, number> {
  return {
    explorationExpression: clamp(0.55 + 0.35 * environment.volatility - 0.4 * environment.resourceScarcity),
    cautionExpression: clamp(0.35 + 0.4 * environment.failurePressure + 0.25 * environment.evidenceScarcity),
    cooperationExpression: clamp(0.45 + 0.3 * environment.competition - 0.2 * organism.stress),
    dormancyExpression: clamp(0.15 + 0.5 * environment.resourceScarcity + 0.25 * organism.stress),
  };
}

export function nicheDistance(a: OrganismState, b: OrganismState): number {
  const keys = new Set([...Object.keys(a.traits), ...Object.keys(b.traits)]);
  if (keys.size === 0) return a.niche === b.niche ? 0 : 1;
  let diff = a.niche === b.niche ? 0 : 0.35;
  for (const key of keys) {
    const av = a.traits[key];
    const bv = b.traits[key];
    if (typeof av === "number" && typeof bv === "number") diff += Math.min(1, Math.abs(av - bv));
    else if (av !== bv) diff += 1;
  }
  return clamp(diff / (keys.size + 0.35));
}

export function shouldSpeciate(a: OrganismState, b: OrganismState, threshold = 0.62): boolean {
  return nicheDistance(a, b) >= threshold;
}

export function updateSenescence(organism: OrganismState, verifiedOutcome: { success: boolean; paid?: boolean } | null): OrganismState {
  let telomere = clamp(organism.telomere);
  if (verifiedOutcome?.success && verifiedOutcome.paid) telomere = clamp(telomere + 0.05);
  else if (verifiedOutcome && !verifiedOutcome.success) telomere = clamp(telomere - 0.08);
  const status = telomere <= 0.05 && organism.status !== "champion" ? "senescent" : organism.status;
  return { ...organism, telomere, status };
}

export function dormancyDecision(organism: OrganismState, environment: EnvironmentState): { hibernate: boolean; wake: boolean; score: number } {
  const sleepPressure = clamp(0.45 * environment.resourceScarcity + 0.25 * organism.stress + 0.2 * (1 - organism.fitness) + 0.1 * (1 - organism.telomere));
  const wakePressure = clamp(0.5 * environment.demand + 0.3 * organism.energy + 0.2 * organism.fitness);
  return { hibernate: sleepPressure >= 0.7 && wakePressure < 0.55, wake: wakePressure >= 0.68, score: sleepPressure };
}

export function symbiosisScore(a: OrganismState, b: OrganismState): number {
  const diversity = nicheDistance(a, b);
  const health = (clamp(a.fitness) + clamp(b.fitness) + clamp(a.confidence) + clamp(b.confidence)) / 4;
  const stressPenalty = (clamp(a.stress) + clamp(b.stress)) / 4;
  return clamp(0.5 * diversity + 0.5 * health - stressPenalty);
}

export function competitionPressure(population: OrganismState[], organism: OrganismState): number {
  const peers = population.filter((peer) => peer.id !== organism.id && peer.niche === organism.niche && peer.status !== "archived");
  if (peers.length === 0) return 0;
  const stronger = peers.filter((peer) => peer.fitness * peer.confidence > organism.fitness * organism.confidence).length;
  return clamp(stronger / peers.length);
}

export function migrationScore(organism: OrganismState, current: EnvironmentState, candidate: EnvironmentState): number {
  const currentUtility = current.demand - current.competition - 0.5 * current.resourceScarcity - 0.3 * current.failurePressure;
  const candidateUtility = candidate.demand - candidate.competition - 0.5 * candidate.resourceScarcity - 0.3 * candidate.failurePressure;
  return clamp(0.5 + (candidateUtility - currentUtility) / 2 + 0.1 * organism.novelty);
}

export function apoptosisArchive(organism: OrganismState, evidenceCount: number): OrganismState {
  const shouldArchive = evidenceCount >= 3 && organism.status !== "champion" && (
    organism.telomere <= 0.03 || (organism.fitness <= 0.12 && organism.confidence >= 0.5)
  );
  return shouldArchive ? { ...organism, status: "archived" } : organism;
}

export function woundHealingPriority(input: { failedJobs: number; deadLetters: number; openCircuits: number; criticalDrift: number; staleHeartbeat: boolean }): number {
  const raw = 0.12 * Math.min(input.failedJobs, 5)
    + 0.16 * Math.min(input.deadLetters, 4)
    + 0.2 * Math.min(input.openCircuits, 3)
    + 0.25 * Math.min(input.criticalDrift, 2)
    + (input.staleHeartbeat ? 0.35 : 0);
  return clamp(raw);
}

export function metabolicBudget(input: { available: number; maintenanceDemand: number; explorationDemand: number; executionDemand: number }) {
  const available = Math.max(0, input.available);
  const maintenance = Math.min(available, Math.max(0, input.maintenanceDemand));
  const afterMaintenance = Math.max(0, available - maintenance);
  const execution = Math.min(afterMaintenance, Math.max(0, input.executionDemand));
  const afterExecution = Math.max(0, afterMaintenance - execution);
  const exploration = Math.min(afterExecution, Math.max(0, input.explorationDemand));
  return { maintenance, execution, exploration, reserve: Math.max(0, available - maintenance - execution - exploration) };
}
