import type { AutonomyLevel } from "./types.js";

const LEVEL: Record<AutonomyLevel, number> = { L0: 0, L1: 1, L2: 2, L3: 3 };

export interface ChildAgentTemplate {
  templateKey: string;
  parentAllowlist: string[];
  maxAutonomy: Exclude<AutonomyLevel, "L3">;
  allowedCapabilities: string[];
  forbiddenActions: string[];
  connectorAllowlist: string[];
  maxRuntimeSeconds: number;
  maxParallel: number;
  maxChildDepth: number;
  minVerifiedSuccessesForPromotion: number;
  enabled: boolean;
}

export interface SpawnRequest {
  parentAgent: string;
  templateKey: string;
  objective: string;
  requestedAutonomy: Exclude<AutonomyLevel, "L3">;
  requestedCapabilities: string[];
  requestedConnectors: string[];
  requestedRuntimeSeconds: number;
  currentDepth: number;
  currentlyRunningForTemplate: number;
}

export interface SpawnDecision {
  allowed: boolean;
  reason: string;
  effectiveAutonomy?: Exclude<AutonomyLevel, "L3">;
  effectiveCapabilities?: string[];
  effectiveConnectors?: string[];
  runtimeSeconds?: number;
}

function subset(requested: string[], allowed: string[]): boolean {
  const permitted = new Set(allowed);
  return requested.every((item) => permitted.has(item));
}

export function authorizeSpawn(request: SpawnRequest, template: ChildAgentTemplate): SpawnDecision {
  if (!template.enabled) return { allowed: false, reason: "Child-agent template is disabled." };
  if (request.templateKey !== template.templateKey) return { allowed: false, reason: "Template mismatch." };
  if (!template.parentAllowlist.includes(request.parentAgent)) {
    return { allowed: false, reason: "Parent agent is not authorized to spawn this specialist." };
  }
  if (!request.objective.trim()) return { allowed: false, reason: "A bounded objective is required." };
  if (request.currentDepth > template.maxChildDepth) {
    return { allowed: false, reason: "Child-agent depth exceeds the template limit." };
  }
  if (request.currentlyRunningForTemplate >= template.maxParallel) {
    return { allowed: false, reason: "Parallel child-agent limit reached." };
  }
  if (LEVEL[request.requestedAutonomy] > LEVEL[template.maxAutonomy]) {
    return { allowed: false, reason: "Requested autonomy exceeds the template ceiling." };
  }
  if (!subset(request.requestedCapabilities, template.allowedCapabilities)) {
    return { allowed: false, reason: "Requested capabilities exceed the template allowlist." };
  }
  if (!subset(request.requestedConnectors, template.connectorAllowlist)) {
    return { allowed: false, reason: "Requested connectors exceed the template allowlist." };
  }
  if (request.requestedRuntimeSeconds <= 0 || request.requestedRuntimeSeconds > template.maxRuntimeSeconds) {
    return { allowed: false, reason: "Requested runtime exceeds the bounded runtime window." };
  }

  return {
    allowed: true,
    reason: "Spawn is bounded by the parent, capability, connector, autonomy, depth and runtime envelopes.",
    effectiveAutonomy: request.requestedAutonomy,
    effectiveCapabilities: [...new Set(request.requestedCapabilities)].sort(),
    effectiveConnectors: [...new Set(request.requestedConnectors)].sort(),
    runtimeSeconds: request.requestedRuntimeSeconds,
  };
}

export function canPromoteChild(input: {
  verifiedSuccesses: number;
  totalRuns: number;
  paidSuccesses: number;
  qaPasses: number;
  severeFailures: number;
  template: ChildAgentTemplate;
}): { allowed: boolean; reason: string } {
  if (input.severeFailures > 0) return { allowed: false, reason: "Severe verified failure blocks persistent promotion." };
  if (input.verifiedSuccesses < input.template.minVerifiedSuccessesForPromotion) {
    return { allowed: false, reason: "Insufficient verified successes for persistent promotion." };
  }
  if (input.totalRuns < input.template.minVerifiedSuccessesForPromotion) {
    return { allowed: false, reason: "Insufficient run history for persistent promotion." };
  }
  if (input.qaPasses < input.template.minVerifiedSuccessesForPromotion) {
    return { allowed: false, reason: "Insufficient QA-passed evidence for persistent promotion." };
  }
  return {
    allowed: true,
    reason: input.paidSuccesses > 0
      ? "Verified repeated success including paid evidence supports promotion."
      : "Verified repeated operational success supports promotion; commercial proof remains unproven.",
  };
}

export function ensureNoForbiddenAction(actionClass: string, template: ChildAgentTemplate): void {
  if (template.forbiddenActions.includes(actionClass)) {
    throw new Error(`Child specialist cannot execute forbidden action class: ${actionClass}`);
  }
}
