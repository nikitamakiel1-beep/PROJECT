export interface SloTarget {
  key: string;
  target: number;
  direction: "max" | "min";
  criticalAfterConsecutiveBreaches: number;
}

export interface SloObservation {
  key: string;
  value: number;
  observedAt: string;
}

export interface SloEvaluation {
  key: string;
  healthy: boolean;
  breachedBy: number;
}

export function evaluateSlo(target: SloTarget, observation: SloObservation): SloEvaluation {
  if (target.key !== observation.key) throw new Error("SLO key mismatch");
  const healthy = target.direction === "max" ? observation.value <= target.target : observation.value >= target.target;
  const breachedBy = healthy ? 0 : Math.abs(observation.value - target.target);
  return { key: target.key, healthy, breachedBy: Number(breachedBy.toFixed(6)) };
}

export function incidentSeverity(
  evaluations: SloEvaluation[],
  consecutiveBreaches: Record<string, number>,
  targets: SloTarget[],
): "none" | "warning" | "critical" {
  let warning = false;
  for (const evaluation of evaluations) {
    if (evaluation.healthy) continue;
    warning = true;
    const target = targets.find((candidate) => candidate.key === evaluation.key);
    if (!target) continue;
    if ((consecutiveBreaches[evaluation.key] ?? 0) >= target.criticalAfterConsecutiveBreaches) return "critical";
  }
  return warning ? "warning" : "none";
}
