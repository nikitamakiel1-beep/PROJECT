import test from "node:test";
import assert from "node:assert/strict";
import { adjudicateBinaryExperiment } from "./experimentsV4.js";

const rule = {
  minTrialsPerArm: 20,
  minEffect: 0.1,
  maxTrialsPerArm: 100,
  requirePaidEvidenceForPaidDemandClaim: true,
  harmStopThreshold: 0.1,
};

test("does not call engagement a paid-demand winner without paid evidence", () => {
  const decision = adjudicateBinaryExperiment(
    { arm: "control", successes: 4, trials: 30 },
    { arm: "treatment", successes: 15, trials: 30, paidSuccesses: 0 },
    rule,
  );
  assert.equal(decision.status, "continue");
});

test("promotes a strong treatment with paid evidence", () => {
  const decision = adjudicateBinaryExperiment(
    { arm: "control", successes: 4, trials: 50 },
    { arm: "treatment", successes: 20, trials: 50, paidSuccesses: 3 },
    rule,
  );
  assert.equal(decision.status, "winner");
  assert.equal(decision.winnerArm, "treatment");
});

test("stops on harmful event threshold", () => {
  const decision = adjudicateBinaryExperiment(
    { arm: "control", successes: 1, trials: 10, harmfulEvents: 2 },
    { arm: "treatment", successes: 2, trials: 10, harmfulEvents: 1 },
    rule,
  );
  assert.equal(decision.status, "stop_harm");
});
