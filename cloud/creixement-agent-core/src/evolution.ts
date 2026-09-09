import type {
  CommercialGenome,
  EvolutionConstitution,
  GenomeGenes,
  MutationPlan,
} from "./types.js";

const PROTECTED_KEYS = new Set([
  "auditHistory",
  "evidenceProvenance",
  "revenueTruth",
  "authentication",
  "secretHandling",
  "privacyConsent",
  "sourceRights",
  "networkSecurity",
  "spendAuthority",
  "contractAuthority",
  "propertyCommitmentAuthority",
  "paymentAuthority",
  "emergencyLockdown",
  "reportDigestApprovalSemantics",
  "cloudOnlyRuntime",
]);

function cloneGenes(genes: GenomeGenes): GenomeGenes {
  return JSON.parse(JSON.stringify(genes)) as GenomeGenes;
}

export function applyMutation(
  parent: CommercialGenome,
  plan: MutationPlan,
  constitution: EvolutionConstitution,
  childId: string,
): CommercialGenome {
  if (plan.parentGenomeId !== parent.id) throw new Error("Mutation parent mismatch");

  const changes = Object.entries(plan.changedGenes);
  if (changes.length === 0) throw new Error("Mutation must change at least one gene");
  if (changes.length > constitution.maxGenesChangedPerMutation) {
    throw new Error("Mutation exceeds constitutional max gene changes");
  }

  for (const [key] of changes) {
    if (PROTECTED_KEYS.has(key)) throw new Error(`Protected constitutional field cannot evolve: ${key}`);
  }

  return {
    ...parent,
    id: childId,
    parentIds: [parent.id],
    generation: parent.generation + 1,
    variantName: `${parent.variantName} · m${parent.generation + 1}`,
    genes: { ...cloneGenes(parent.genes), ...plan.changedGenes },
    explorationBudget: Math.max(parent.explorationBudget, constitution.explorationBudgetFloor),
    telomere: Math.max(parent.telomere - 0.02, 0),
    fitness: undefined,
    confidence: undefined,
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

  const genes = cloneGenes(a.genes);
  for (const key of keysFromB) {
    if (PROTECTED_KEYS.has(key)) throw new Error(`Protected constitutional field cannot evolve: ${key}`);
    if (Object.prototype.hasOwnProperty.call(b.genes, key)) genes[key] = b.genes[key];
  }

  return {
    ...a,
    id: childId,
    lineageId: a.lineageId,
    parentIds: [a.id, b.id],
    generation: Math.max(a.generation, b.generation) + 1,
    variantName: `${a.variantName} × ${b.variantName}`,
    genes,
    explorationBudget: Math.max(
      (a.explorationBudget + b.explorationBudget) / 2,
      constitution.explorationBudgetFloor,
    ),
    telomere: Math.max((a.telomere + b.telomere) / 2 - 0.01, 0),
    fitness: undefined,
    confidence: undefined,
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
    (genome.fitness ?? 0) >= 0.55
  ) {
    return { ...genome, status: (genome.fitness ?? 0) >= 0.75 ? "champion" : "active" };
  }

  if (genome.telomere <= 0.05 && genome.verifiedObservations >= 3) {
    return { ...genome, status: "archived" };
  }

  return genome;
}

export function selectNicheChampions(genomes: CommercialGenome[], maxChampions = 2): CommercialGenome[] {
  const eligible = genomes.filter(
    (g) => g.status !== "blocked" && g.status !== "archived" && g.verifiedObservations > 0,
  );

  return [...eligible]
    .sort((a, b) => {
      const aScore = (a.fitness ?? 0) * (a.confidence ?? 0.25);
      const bScore = (b.fitness ?? 0) * (b.confidence ?? 0.25);
      return bScore - aScore;
    })
    .slice(0, maxChampions);
}
