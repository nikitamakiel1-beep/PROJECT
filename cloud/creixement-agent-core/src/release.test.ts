import test from "node:test";
import assert from "node:assert/strict";
import { assessRelease, standardV4ReleaseGates } from "./release.js";

test("release is promotable only when every required gate passes with evidence", () => {
  const gates = standardV4ReleaseGates({
    ciPassed: true,
    cleanInstallPassed: true,
    upgradePassed: true,
    cloudOnlyPassed: true,
    criticalIncidents: 0,
    backupRestoreCurrent: true,
    connectorsReady: true,
    rollbackPlanPresent: true,
    cockpitTruthChecksPassed: true,
    tectumEnabled: false,
  });
  const assessment = assessRelease(gates);
  assert.equal(assessment.promotable, true);
  assert.equal(assessment.readiness, 1);
});

test("Tectum activation requires both golden gates", () => {
  const gates = standardV4ReleaseGates({
    ciPassed: true,
    cleanInstallPassed: true,
    upgradePassed: true,
    cloudOnlyPassed: true,
    criticalIncidents: 0,
    backupRestoreCurrent: true,
    connectorsReady: true,
    rollbackPlanPresent: true,
    cockpitTruthChecksPassed: true,
    tectumEnabled: true,
    tectumUnderwritingGoldenPassed: true,
    tectumRenderGoldenPassed: false,
  });
  const assessment = assessRelease(gates);
  assert.equal(assessment.promotable, false);
  assert.ok(assessment.failingRequired.includes("tectum_render_golden"));
});
