export type ReleaseGateState = "pass" | "fail" | "blocked" | "not_applicable" | "unknown";

export interface ReleaseGate {
  key: string;
  state: ReleaseGateState;
  required: boolean;
  evidenceRefs: string[];
  reason: string;
}

export interface ReleaseAssessment {
  promotable: boolean;
  readiness: number;
  failingRequired: string[];
  unknownRequired: string[];
  passedRequired: number;
  totalRequired: number;
}

export function assessRelease(gates: ReleaseGate[]): ReleaseAssessment {
  const required = gates.filter((gate) => gate.required && gate.state !== "not_applicable");
  const failing = required.filter((gate) => gate.state === "fail" || gate.state === "blocked");
  const unknown = required.filter((gate) => gate.state === "unknown");
  const passed = required.filter((gate) => gate.state === "pass" && gate.evidenceRefs.length > 0);

  const readiness = required.length === 0 ? 0 : passed.length / required.length;
  return {
    promotable: required.length > 0 && failing.length === 0 && unknown.length === 0 && passed.length === required.length,
    readiness: Number(readiness.toFixed(6)),
    failingRequired: failing.map((gate) => gate.key),
    unknownRequired: unknown.map((gate) => gate.key),
    passedRequired: passed.length,
    totalRequired: required.length,
  };
}

export function standardV4ReleaseGates(input: {
  ciPassed: boolean;
  cleanInstallPassed: boolean;
  upgradePassed: boolean;
  cloudOnlyPassed: boolean;
  criticalIncidents: number;
  backupRestoreCurrent: boolean;
  connectorsReady: boolean;
  rollbackPlanPresent: boolean;
  cockpitTruthChecksPassed: boolean;
  tectumEnabled: boolean;
  tectumUnderwritingGoldenPassed?: boolean;
  tectumRenderGoldenPassed?: boolean;
}): ReleaseGate[] {
  const gate = (key: string, pass: boolean, reason: string): ReleaseGate => ({
    key,
    state: pass ? "pass" : "fail",
    required: true,
    evidenceRefs: pass ? [`evidence:${key}`] : [],
    reason,
  });

  return [
    gate("ci", input.ciPassed, "CI/typecheck/tests must pass."),
    gate("clean_install_migrations", input.cleanInstallPassed, "Fresh database migration path must succeed."),
    gate("upgrade_migrations", input.upgradePassed, "Existing database upgrade path must succeed."),
    gate("cloud_only", input.cloudOnlyPassed, "Desktop/local production dependencies are forbidden."),
    gate("critical_incidents", input.criticalIncidents === 0, "No unresolved critical incidents may exist."),
    gate("backup_restore", input.backupRestoreCurrent, "Backup and restore rehearsal must be current."),
    gate("runtime_connectors", input.connectorsReady, "All connectors required by enabled jobs must be runtime-ready."),
    gate("rollback_plan", input.rollbackPlanPresent, "A rollback plan must exist."),
    gate("cockpit_truth", input.cockpitTruthChecksPassed, "Operator UI must not present synthetic/configured states as live execution."),
    {
      key: "tectum_underwriting_golden",
      state: input.tectumEnabled ? (input.tectumUnderwritingGoldenPassed ? "pass" : "fail") : "not_applicable",
      required: input.tectumEnabled,
      evidenceRefs: input.tectumEnabled && input.tectumUnderwritingGoldenPassed ? ["evidence:tectum_underwriting_golden"] : [],
      reason: "Tectum underwriting requires golden-case equivalence before activation.",
    },
    {
      key: "tectum_render_golden",
      state: input.tectumEnabled ? (input.tectumRenderGoldenPassed ? "pass" : "fail") : "not_applicable",
      required: input.tectumEnabled,
      evidenceRefs: input.tectumEnabled && input.tectumRenderGoldenPassed ? ["evidence:tectum_render_golden"] : [],
      reason: "Tectum rendering requires golden-report fidelity before activation.",
    },
  ];
}
