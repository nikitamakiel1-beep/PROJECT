export type DriftSeverity = "info" | "warning" | "critical";

export interface DesiredRuntimeState {
  key: string;
  kind: "connector" | "job" | "agent" | "policy" | "service" | "release";
  desired: Record<string, unknown>;
  autoRemediate: boolean;
}

export interface ObservedRuntimeState {
  key: string;
  kind: DesiredRuntimeState["kind"];
  observed: Record<string, unknown>;
  observedAt: string;
}

export interface DriftFinding {
  key: string;
  kind: DesiredRuntimeState["kind"];
  field: string;
  desired: unknown;
  observed: unknown;
  severity: DriftSeverity;
  remediation: "none" | "automatic" | "approval_required";
}

const comparable = (value: unknown): string => JSON.stringify(value);

function severityFor(field: string): DriftSeverity {
  if (["enabled", "state", "runtimeReady", "policyDecision", "cloudOnly"].includes(field)) return "critical";
  if (["version", "owner", "schedule", "maxAutonomy", "requiredConnectors"].includes(field)) return "warning";
  return "info";
}

export function reconcileRuntime(
  desiredStates: DesiredRuntimeState[],
  observedStates: ObservedRuntimeState[],
): DriftFinding[] {
  const observedByKey = new Map(observedStates.map((state) => [`${state.kind}:${state.key}`, state]));
  const findings: DriftFinding[] = [];

  for (const desired of desiredStates) {
    const observed = observedByKey.get(`${desired.kind}:${desired.key}`);
    if (!observed) {
      findings.push({
        key: desired.key,
        kind: desired.kind,
        field: "__missing__",
        desired: desired.desired,
        observed: null,
        severity: "critical",
        remediation: desired.autoRemediate ? "automatic" : "approval_required",
      });
      continue;
    }

    for (const [field, desiredValue] of Object.entries(desired.desired)) {
      const observedValue = observed.observed[field];
      if (comparable(desiredValue) === comparable(observedValue)) continue;
      const severity = severityFor(field);
      findings.push({
        key: desired.key,
        kind: desired.kind,
        field,
        desired: desiredValue,
        observed: observedValue,
        severity,
        remediation: desired.autoRemediate && severity !== "critical" ? "automatic" : "approval_required",
      });
    }
  }

  return findings.sort((a, b) => {
    const rank: Record<DriftSeverity, number> = { critical: 3, warning: 2, info: 1 };
    return rank[b.severity] - rank[a.severity] || a.key.localeCompare(b.key) || a.field.localeCompare(b.field);
  });
}
