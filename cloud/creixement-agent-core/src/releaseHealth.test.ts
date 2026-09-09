import test from "node:test";
import assert from "node:assert/strict";
import { buildReleaseManifest, verifyReleaseManifest } from "./releaseManifest.js";
import { evaluateSlo, incidentSeverity } from "./health.js";

test("release manifest digest is reproducible and tamper-evident", () => {
  const manifest = buildReleaseManifest({
    releaseId: "r1", branch: "venture/creixement-overhaul-v4", commitSha: "a".repeat(40), createdAt: "2026-09-09T00:00:00Z",
    components: [
      { key: "migration-007", version: "007", digest: "b".repeat(64), kind: "migration" },
      { key: "core", version: "4.0.0", digest: "c".repeat(64), kind: "code" },
    ],
    migrationHead: "007", constitutionVersion: "3.0.0", schedulerVersion: "3.0.0",
  });
  assert.equal(verifyReleaseManifest(manifest), true);
  assert.equal(verifyReleaseManifest({ ...manifest, migrationHead: "999" }), false);
});

test("repeated SLO breach escalates to critical", () => {
  const target = { key: "job_failure_rate", target: 0.05, direction: "max" as const, criticalAfterConsecutiveBreaches: 3 };
  const evaluation = evaluateSlo(target, { key: "job_failure_rate", value: 0.2, observedAt: "2026-09-09T00:00:00Z" });
  assert.equal(evaluation.healthy, false);
  assert.equal(incidentSeverity([evaluation], { job_failure_rate: 3 }, [target]), "critical");
});
