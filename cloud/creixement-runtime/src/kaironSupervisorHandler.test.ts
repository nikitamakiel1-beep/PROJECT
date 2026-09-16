import test from "node:test";
import assert from "node:assert/strict";
import { compileSupervisorySnapshot, summarizeLatestCourtSuite } from "./kaironSupervisorHandler.js";

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
    total_courts: 12,
    failed_courts: 2,
    verified_canaries: 5,
    latest_suite_total: 4,
    latest_suite_failed: 0,
    latest_suite_fresh: true,
    latest_suite_complete: true,
  },
  health: {
    open_job_dead_letters: 0,
    open_outbox_dead_letters: 0,
    open_handler_circuits: 0,
    critical_drift: 0,
    healthy_runtime_instances: 1,
  },
  portfolio: {
    operating_projects: 1,
    incubating_projects: 0,
    paused_projects: 0,
    foundry_candidates: 0,
    actionable_opportunities: 0,
    tectum_operating: 1,
    supervised_economic_l2_open: true,
  },
};

test("healthy fresh proofs keep supervised economic L2 open despite historical failed courts", () => {
  const snapshot = compileSupervisorySnapshot(healthy);
  assert.equal(snapshot.version, "10.0");
  assert.equal(snapshot.role, "chief-operator");
  assert.equal(snapshot.executiveAgent, "Kairon");
  assert.equal(snapshot.authority.courtEvidenceReady, true);
  assert.equal(snapshot.authority.supervisedEconomicL2Open, true);
  assert.equal(snapshot.adaptation.failedCourts, 0);
  assert.equal(snapshot.adaptation.mode, "balanced");
  assert.equal(snapshot.portfolio.operatingProjects, 1);
  assert.equal(snapshot.portfolio.tectumOperating, true);
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

test("failed current adversarial court suite closes economic L2", () => {
  const snapshot = compileSupervisorySnapshot({
    ...healthy,
    courts: { ...healthy.courts, latest_suite_failed: 1 },
  });
  assert.equal(snapshot.authority.courtEvidenceReady, false);
  assert.equal(snapshot.authority.supervisedEconomicL2Open, false);
});

test("stale court evidence closes economic L2", () => {
  const snapshot = compileSupervisorySnapshot({
    ...healthy,
    courts: { ...healthy.courts, latest_suite_fresh: false },
  });
  assert.equal(snapshot.authority.courtEvidenceFresh, false);
  assert.equal(snapshot.authority.courtEvidenceReady, false);
  assert.equal(snapshot.authority.supervisedEconomicL2Open, false);
});

test("incomplete court evidence closes economic L2", () => {
  const snapshot = compileSupervisorySnapshot({
    ...healthy,
    courts: { ...healthy.courts, latest_suite_total: 3, latest_suite_complete: false },
  });
  assert.equal(snapshot.authority.courtSuiteComplete, false);
  assert.equal(snapshot.authority.supervisedEconomicL2Open, false);
});

test("portfolio evidence is descriptive and never expands authority", () => {
  const snapshot = compileSupervisorySnapshot({
    ...healthy,
    portfolio: {
      ...healthy.portfolio,
      operating_projects: 7,
      incubating_projects: 4,
      foundry_candidates: 25,
      actionable_opportunities: 100,
    },
  });
  assert.equal(snapshot.portfolio.operatingProjects, 7);
  assert.equal(snapshot.portfolio.incubatingProjects, 4);
  assert.equal(snapshot.portfolio.foundryCandidates, 25);
  assert.equal(snapshot.autonomyCeiling, "L2");
  assert.equal(snapshot.authority.consequentialBoundary, "L3-owner-only");
});

test("latest court-suite summarizer binds the four expected courts to one execution", () => {
  const now = Date.parse("2026-09-15T14:00:00Z");
  const rows = [
    { court_key: "cycle:new:authority", court_type: "authority_traversal", passed: true, created_at: "2026-09-15T13:17:01Z" },
    { court_key: "cycle:new:faustian", court_type: "faustian_fuzz", passed: true, created_at: "2026-09-15T13:17:02Z" },
    { court_key: "cycle:new:auditor", court_type: "auditor_of_auditors", passed: true, created_at: "2026-09-15T13:17:03Z" },
    { court_key: "cycle:new:canary", court_type: "mutation_detection", passed: true, created_at: "2026-09-15T13:17:04Z" },
    { court_key: "cycle:old:authority", court_type: "authority_traversal", passed: false, created_at: "2026-09-15T12:17:01Z" },
  ];
  const suite = summarizeLatestCourtSuite(rows, now);
  assert.equal(suite.latest_suite_key, "cycle:new");
  assert.equal(suite.latest_suite_total, 4);
  assert.equal(suite.latest_suite_failed, 0);
  assert.equal(suite.latest_suite_complete, true);
  assert.equal(suite.latest_suite_fresh, true);
});

test("partial or old latest court suites fail freshness/completeness", () => {
  const now = Date.parse("2026-09-15T16:30:00Z");
  const rows = [
    { court_key: "partial:authority", court_type: "authority_traversal", passed: true, created_at: "2026-09-15T13:00:00Z" },
    { court_key: "partial:faustian", court_type: "faustian_fuzz", passed: true, created_at: "2026-09-15T13:00:01Z" },
  ];
  const suite = summarizeLatestCourtSuite(rows, now);
  assert.equal(suite.latest_suite_complete, false);
  assert.equal(suite.latest_suite_fresh, false);
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
