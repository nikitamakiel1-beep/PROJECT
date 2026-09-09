import type {
  CommercialGenome,
  EvolutionConstitution,
  GenomeGenes,
  MutationPlan,
} from "./types.js";

function normalizeProtectedKey(key: string): string {
  return key.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
}

const PROTECTED_KEYS = new Set([
  "audit_history",
  "evidence_provenance",
  "revenue_truth",
  "authentication",
  "secret_handling",
  "privacy_and_consent",
  "privacy_consent",
  "source_rights",
  "network_security",
  "spend_authority",
  "contract_authority",
  "property_commitment_authority",
  "payment_authority",
  "emergency_lockdown",
  "report_digest_approval_semantics",
  "cloud_only_runtime",
].map(normalizeProtectedKey));

function cloneGenes(genes: GenomeGenes): GenomeGenes {
  return JSON.parse(JSON.stringify(genes)) as GenomeGenes;
}

function equalValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function baseChild(parent: CommercialGenome): Omit<CommercialGenome, "fitness" | "confidence"> {
  const { fitness: _fitness, confidence: _confidence, ...rest } = parent;
  return rest;
}

function boundedExploration(value: number, constitution: EvolutionConstitution): number {
  const ceiling = constitution.explorationBudgetCeiling ?? 0.5;
  return Math.min(ceiling, Math.max(constitution.explorationBudgetFloor, value));
}

export function validateGenomeGenes(genes: GenomeGenes): void {
  if (genes.priceFloor !== undefined && (!Number.isFinite(genes.priceFloor) || genes.priceFloor < 0)) {
    throw new Error("priceFloor must be a finite non-negative number");
  }
  if (genes.priceCeiling !== undefined && (!Number.isFinite(genes.priceCeiling) || genes.priceCeiling < 0)) {
    throw new Error("priceCeiling must be a finite non-negative number");
  }
  if (genes.priceFloor !== undefined && genes.priceCeiling !== undefined && genes.priceFloor > genes.priceCeiling) {
    throw new Error("priceFloor cannot exceed priceCeiling");
  }
  if (genes.slaDays !== undefined && (!Number.isFinite(genes.slaDays) || genes.slaDays <= 0 || genes.slaDays > 365)) {
    throw new Error("slaDays must be within 1..365");
  }
  if (genes.qualificationThreshold !== undefined && (genes.qualificationThreshold < 0 || genes.qualificationThreshold > 1)) {
    throw new Error("qualificationThreshold must be within 0..1");
  }
  const weights = [genes.exploitWeight, genes.adjacencyWeight, genes.explorationWeight];
  if (weights.every((v) => v !== undefined)) {
    const total = (weights as number[]).reduce((sum, v) => sum + v, 0);
    if (weights.some((v) => (v as number) < 0) || Math.abs(total - 1) > 0.000001) {
      throw new Error("exploit/adjacency/exploration weights must be non-negative and sum to 1");
    }
  }
}

function assertEvolvableKeys(keys: string[]): void {
  for (const key of keys) {
    if (PROTECTED_KEYS.has(normalizeProtectedKey(key))) {
      throw new Error(`Protected constitutional field cannot evolve: ${key}`);
    }
  }
}

export function applyMutation(
  parent: CommercialGenome,
  plan: MutationPlan,
  constitution: EvolutionConstitution,
  childId: string,
): CommercialGenome {
  if (plan.parentGenomeId !== parent.id) throw new Error("Mutation parent mismatch");
  if (!plan.reason.trim()) throw new Error("Mutation requires an evidence-backed reason");

  const changes = Object.entries(plan.changedGenes).filter(([key, value]) => !equalValue(parent.genes[key], value));
  if (changes.length === 0) throw new Error("Mutation must materially change at least one gene");
  if (changes.length > constitution.maxGenesChangedPerMutation) {
    throw new Error("Mutation exceeds constitutional max gene changes");
  }
  assertEvolvableKeys(changes.map(([key]) => key));

  const genes = { ...cloneGenes(parent.genes), ...Object.fromEntries(changes) } as GenomeGenes;
  validateGenomeGenes(genes);

  return {
    ...baseChild(parent),
    id: childId,
    parentIds: [parent.id],
    generation: parent.generation + 1,
    variantName: `${parent.variantName} · m${parent.generation + 1}`,
    genes,
    explorationBudget: boundedExploration(parent.explorationBudget, constitution),
    telomere: Math.max(parent.telomere - 0.02, 0),
    verifiedObservations: 0,
    verifiedSuccesses: 0,
    paidSuccesses: 0,
    status: "experimental",
  };
}

export function crossover(
  a: CommercialGenome,
  b: CommercialGenome,
  keysFromB: string[],
  constitution: EvolutionConstitution,
  childId: string,
): CommercialGenome {
  if (a.niche !== b.niche) throw new Error("Cross-niche crossover is not permitted by default");
  if (
    a.verifiedObservations < constitution.minVerifiedObservationsForCrossover ||
    b.verifiedObservations < constitution.minVerifiedObservationsForCrossover
  ) {
    throw new Error("Insufficient verified observations for crossover");
  }

  const uniqueKeys = [...new Set(keysFromB)];
  const maxCrossoverChanges = constitution.maxGenesChangedPerCrossover ?? Math.max(2, constitution.maxGenesChangedPerMutation * 2);
  if (uniqueKeys.length > maxCrossoverChanges) throw new Error("Crossover exceeds constitutional max gene changes");
  assertEvolvableKeys(uniqueKeys);

  const genes = cloneGenes(a.genes);
  let materialChanges = 0;
  for (const key of uniqueKeys) {
    if (Object.prototype.hasOwnProperty.call(b.genes, key) && !equalValue(genes[key], b.genes[key])) {
      genes[key] = b.genes[key];
      materialChanges += 1;
    }
  }
  if (materialChanges === 0) throw new Error("Crossover must materially change at least one gene");
  validateGenomeGenes(genes);

  return {
    ...baseChild(a),
    id: childId,
    lineageId: a.lineageId,
    parentIds: [a.id, b.id],
    generation: Math.max(a.generation, b.generation) + 1,
    variantName: `${a.variantName} × ${b.variantName}`,
    genes,
    explorationBudget: boundedExploration((a.explorationBudget + b.explorationBudget) / 2, constitution),
    telomere: Math.max((a.telomere + b.telomere) / 2 - 0.01, 0),
    verifiedObservations: 0,
    verifiedSuccesses: 0,
    paidSuccesses: 0,
    status: "experimental",
  };
}

export function updateTelomere(
  genome: CommercialGenome,
  outcome: { verified: boolean; success: boolean; paid: boolean },
  constitution: EvolutionConstitution,
): CommercialGenome {
  if (!outcome.verified) return genome;

  let telomere = genome.telomere;
  if (outcome.paid && outcome.success) {
    telomere = Math.min(1, telomere + constitution.telomereRestoreOnPaidSuccess);
  } else if (!outcome.success) {
    telomere = Math.max(0, telomere - constitution.telomereDecayOnFailure);
  }

  const status = telomere <= 0.05 && genome.status !== "champion" ? "senescent" : genome.status;
  return { ...genome, telomere, status };
}

export function promoteOrArchive(
  genome: CommercialGenome,
  constitution: EvolutionConstitution,
): CommercialGenome {
  if (
    genome.verifiedSuccesses >= constitution.minVerifiedSuccessesForPromotion &&
    genome.paidSuccesses > 0 &&
    (genome.fitness ?? 0) >= 0.55 &&
    (genome.confidence ?? 0) >= 0.35
  ) {
    return { ...genome, status: (genome.fitness ?? 0) >= 0.75 && (genome.confidence ?? 0) >= 0.5 ? "champion" : "active" };
  }

  if (genome.telomere <= 0.05 && genome.verifiedObservations >= 3) {
    return { ...genome, status: "archived" };
  }

  return genome;
}

export function selectNicheChampions(genomes: CommercialGenome[], maxChampionsPerNiche = 2): CommercialGenome[] {
  const byNiche = new Map<string, CommercialGenome[]>();
  for (const genome of genomes) {
    if (genome.status === "blocked" || genome.status === "archived" || genome.verifiedObservations <= 0) continue;
    const list = byNiche.get(genome.niche) ?? [];
    list.push(genome);
    byNiche.set(genome.niche, list);
  }

  const champions: CommercialGenome[] = [];
  for (const list of byNiche.values()) {
    champions.push(
      ...[...list]
        .sort((a, b) => {
          const aScore = (a.fitness ?? 0) * (a.confidence ?? 0.25);
          const bScore = (b.fitness ?? 0) * (b.confidence ?? 0.25);
          return bScore - aScore;
        })
        .slice(0, Math.max(1, maxChampionsPerNiche)),
    );
  }
  return champions;
}
