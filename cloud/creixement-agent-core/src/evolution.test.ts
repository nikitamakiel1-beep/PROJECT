import test from "node:test";
import assert from "node:assert/strict";
import { applyMutation, promoteOrArchive } from "./evolution.js";
import type { CommercialGenome, EvolutionConstitution } from "./types.js";

const constitution: EvolutionConstitution = {
  maxGenesChangedPerMutation: 2,
  minVerifiedObservationsForCrossover: 3,
  minVerifiedSuccessesForPromotion: 2,
  telomereDecayOnFailure: 0.2,
  telomereRestoreOnPaidSuccess: 0.1,
  explorationBudgetFloor: 0.05,
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

test("paid successful genome can become champion", () => {
  const promoted = promoteOrArchive(parent, constitution);
  assert.equal(promoted.status, "champion");
});
