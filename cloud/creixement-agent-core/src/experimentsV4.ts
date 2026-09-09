export interface BinaryArmObservation {
  arm: string;
  successes: number;
  trials: number;
  paidSuccesses?: number;
  harmfulEvents?: number;
}

export interface ExperimentRule {
  minTrialsPerArm: number;
  minEffect: number;
  maxTrialsPerArm: number;
  requirePaidEvidenceForPaidDemandClaim: boolean;
  harmStopThreshold: number;
}

export interface ExperimentDecision {
  status: "continue" | "winner" | "inconclusive" | "stop_harm" | "budget_exhausted";
  winnerArm?: string;
  reason: string;
  estimatedEffect?: number;
  confidenceScore: number;
}

function betaMean(successes: number, trials: number): number {
  return (successes + 1) / (trials + 2);
}

function betaVariance(successes: number, trials: number): number {
  const a = successes + 1;
  const b = trials - successes + 1;
  return (a * b) / ((a + b) ** 2 * (a + b + 1));
}

function normalAdvantageProbability(a: BinaryArmObservation, b: BinaryArmObservation): number {
  const meanA = betaMean(a.successes, a.trials);
  const meanB = betaMean(b.successes, b.trials);
  const variance = betaVariance(a.successes, a.trials) + betaVariance(b.successes, b.trials);
  if (variance <= Number.EPSILON) return meanA > meanB ? 1 : meanA < meanB ? 0 : 0.5;
  const z = (meanA - meanB) / Math.sqrt(variance);
  // Logistic approximation to the normal CDF is deterministic and sufficient for a conservative gate.
  return 1 / (1 + Math.exp(-1.702 * z));
}

export function adjudicateBinaryExperiment(
  control: BinaryArmObservation,
  treatment: BinaryArmObservation,
  rule: ExperimentRule,
): ExperimentDecision {
  if (control.trials < control.successes || treatment.trials < treatment.successes) {
    throw new Error("Successes cannot exceed trials");
  }

  const totalHarm = (control.harmfulEvents ?? 0) + (treatment.harmfulEvents ?? 0);
  const totalTrials = control.trials + treatment.trials;
  if (totalTrials > 0 && totalHarm / totalTrials >= rule.harmStopThreshold) {
    return { status: "stop_harm", reason: "Observed harm rate crossed the configured stop threshold.", confidenceScore: 1 };
  }

  if (control.trials >= rule.maxTrialsPerArm && treatment.trials >= rule.maxTrialsPerArm) {
    return { status: "budget_exhausted", reason: "Maximum observation budget reached without a promotable result.", confidenceScore: 1 };
  }

  if (control.trials < rule.minTrialsPerArm || treatment.trials < rule.minTrialsPerArm) {
    return { status: "continue", reason: "Minimum observations have not been reached.", confidenceScore: 0 };
  }

  const controlRate = betaMean(control.successes, control.trials);
  const treatmentRate = betaMean(treatment.successes, treatment.trials);
  const effect = treatmentRate - controlRate;
  const advantage = normalAdvantageProbability(treatment, control);

  if (rule.requirePaidEvidenceForPaidDemandClaim && (treatment.paidSuccesses ?? 0) === 0) {
    return {
      status: "continue",
      reason: "Engagement may be positive, but no paid evidence exists for a paid-demand claim.",
      estimatedEffect: Number(effect.toFixed(6)),
      confidenceScore: Number(advantage.toFixed(6)),
    };
  }

  if (effect >= rule.minEffect && advantage >= 0.95) {
    return {
      status: "winner",
      winnerArm: treatment.arm,
      reason: "Treatment exceeds the minimum effect with conservative posterior confidence.",
      estimatedEffect: Number(effect.toFixed(6)),
      confidenceScore: Number(advantage.toFixed(6)),
    };
  }

  if (Math.abs(effect) < rule.minEffect / 2 && advantage > 0.2 && advantage < 0.8 &&
      control.trials >= Math.ceil(rule.maxTrialsPerArm * 0.75) && treatment.trials >= Math.ceil(rule.maxTrialsPerArm * 0.75)) {
    return {
      status: "inconclusive",
      reason: "Large observation budget with little practical separation; stop and preserve the result as inconclusive.",
      estimatedEffect: Number(effect.toFixed(6)),
      confidenceScore: Number(advantage.toFixed(6)),
    };
  }

  return {
    status: "continue",
    reason: "Evidence is not yet strong enough to promote a winner.",
    estimatedEffect: Number(effect.toFixed(6)),
    confidenceScore: Number(advantage.toFixed(6)),
  };
}
