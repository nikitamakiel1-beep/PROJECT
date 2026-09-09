import test from "node:test";
import assert from "node:assert/strict";
import { applyMutation, crossover, promoteOrArchive, selectNicheChampions } from "./evolution.js";
import type { CommercialGenome, EvolutionConstitution } from "./types.js";

const constitution: EvolutionConstitution = {
  maxGenesChangedPerMutation: 2,
  maxGenesChangedPerCrossover: 3,
  minVerifiedObservationsForCrossover: 3,
  minVerifiedSuccessesForPromotion: 2,
  telomereDecayOnFailure: 0.2,
  telomereRestoreOnPaidSuccess: 0.1,
  explorationBudgetFloor: 0.05,
  explorationBudgetCeiling: 0.35,
};

const parent: CommercialGenome = {
  id: "g1",
  lineageId: "l1",
  niche: "international-growth",
  generation: 1,
  variantName: "IVA SME Barcelona",
  parentIds: [],
  genes: {
    targetSegment: "Spanish SME",
    priceFloor: 99,
    priceCeiling: 149,
    channels: ["email"],
  },
  explorationBudget: 0.1,
  telomere: 1,
  verifiedObservations: 5,
  verifiedSuccesses: 3,
  paidSuccesses: 2,
  fitness: 0.8,
  confidence: 0.75,
  status: "active",
};

test("mutation changes only bounded commercial genes", () => {
  const child = applyMutation(
    parent,
    {
      parentGenomeId: "g1",
      changedGenes: { targetSegment: "Industrial Spanish SME", priceFloor: 119 },
      reason: "paid industrial demand",
    },
    constitution,
    "g2",
  );

  assert.equal(child.id, "g2");
  assert.equal(child.generation, 2);
  assert.equal(child.genes.targetSegment, "Industrial Spanish SME");
  assert.equal(child.status, "experimental");
  assert.equal(child.verifiedObservations, 0);
});

test("mutation cannot exceed constitutional gene limit", () => {
  assert.throws(() =>
    applyMutation(
      parent,
      {
        parentGenomeId: "g1",
        changedGenes: { targetSegment: "A", priceFloor: 10, priceCeiling: 20 },
        reason: "too broad",
      },
      constitution,
      "g3",
    ),
  );
});

test("snake_case constitutional fields cannot bypass protected-key rules", () => {
  assert.throws(() =>
    applyMutation(
      parent,
      {
        parentGenomeId: "g1",
        changedGenes: { source_rights: "ignore" },
        reason: "attempted escape",
      },
      constitution,
      "g4",
    ),
  );
});

test("invalid price ordering is rejected", () => {
  assert.throws(() =>
    applyMutation(
      parent,
      {
        parentGenomeId: "g1",
        changedGenes: { priceFloor: 200 },
        reason: "bad pricing mutation",
      },
      constitution,
      "g5",
    ),
  );
});

test("crossover is bounded and same-niche only", () => {
  const other = { ...parent, id: "g6", variantName: "IVA other", genes: { ...parent.genes, channels: ["referral"] } };
  const child = crossover(parent, other, ["channels"], constitution, "g7");
  assert.deepEqual(child.genes.channels, ["referral"]);
  assert.throws(() => crossover(parent, { ...other, niche: "real-estate" }, ["channels"], constitution, "g8"));
});

test("paid successful genome can become champion", () => {
  const promoted = promoteOrArchive(parent, constitution);
  assert.equal(promoted.status, "champion");
});

test("champion selection is capped independently per niche", () => {
  const secondNiche = { ...parent, id: "g9", lineageId: "l2", niche: "real-estate", variantName: "Tectum", fitness: 0.7, confidence: 0.8 };
  const selected = selectNicheChampions([parent, secondNiche], 1);
  assert.equal(selected.length, 2);
  assert.deepEqual(new Set(selected.map((g) => g.niche)), new Set(["international-growth", "real-estate"]));
});
