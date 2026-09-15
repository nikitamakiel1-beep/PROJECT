import test from "node:test";
import assert from "node:assert/strict";
import { compileSupervisorySnapshot } from "./kaironSupervisorHandler.js";

const healthy = {
  legacy: {
    economicL2Allowed: true,
    safetyClean: true,
  },
  proof: {
    cloudflare_scheduler_verified: true,
  },
  ecology: {
    recent_red_queen_pressure: 0.42,
    active_population: 18,
    active_niches: 6,
    mean_fitness: 0.7,
    mean_telomere: 0.8,
  },
  courts: {
    total_courts: 4,
    failed_courts: 0,
    verified_canaries: 5,
  },
  health: {
    open_job_dead_letters: 0,
    open_outbox_dead_letters: 0,
    open_handler_circuits: 0,
    critical_drift: 0,
    healthy_runtime_instances: 1,
  },
};

test("healthy proofs keep supervised economic L2 open", () => {
  const snapshot = compileSupervisorySnapshot(healthy);
  assert.equal(snapshot.authority.supervisedEconomicL2Open, true);
  assert.equal(snapshot.adaptation.mode, "balanced");
  assert.equal(snapshot.proofDigest.length, 64);
});

test("configuration without scheduler execution proof closes economic L2", () => {
  const snapshot = compileSupervisorySnapshot({
    ...healthy,
    proof: { cloudflare_scheduler_verified: false },
  });
  assert.equal(snapshot.authority.supervisedEconomicL2Open, false);
  assert.equal(snapshot.truth.configurationCountsAsExecution, false);
});

test("failed adversarial courts close economic L2", () => {
  const snapshot = compileSupervisorySnapshot({
    ...healthy,
    courts: { total_courts: 4, failed_courts: 1, verified_canaries: 5 },
  });
  assert.equal(snapshot.authority.courtEvidenceReady, false);
  assert.equal(snapshot.authority.supervisedEconomicL2Open, false);
});

test("runtime injury switches Kairon into recovery adaptation", () => {
  const snapshot = compileSupervisorySnapshot({
    ...healthy,
    health: {
      open_job_dead_letters: 4,
      open_outbox_dead_letters: 2,
      open_handler_circuits: 2,
      critical_drift: 2,
      healthy_runtime_instances: 0,
    },
  });
  assert.equal(snapshot.adaptation.mode, "recovery");
  assert.ok(snapshot.adaptation.woundHealingPriority >= 0.8);
  assert.equal(snapshot.authority.supervisedEconomicL2Open, false);
});

test("same stable inputs produce same supervisory digest", () => {
  assert.equal(
    compileSupervisorySnapshot(healthy).proofDigest,
    compileSupervisorySnapshot(healthy).proofDigest,
  );
});
