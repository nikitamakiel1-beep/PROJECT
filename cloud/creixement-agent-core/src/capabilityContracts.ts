import type { AutonomyLevel } from "./types.js";

export interface CapabilityContract {
  key: string;
  version: string;
  description: string;
  inputSchemaRef: string;
  outputSchemaRef: string;
  requiredEvidenceKinds: string[];
  requiredRights: string[];
  maxAutonomy: AutonomyLevel;
  reversible: boolean;
  receiptRequired: boolean;
  idempotencyRequired: boolean;
  maxExternalCostEur: number;
  allowedProviders: string[];
  forbiddenEffects: string[];
  active: boolean;
}

export interface CapabilityInvocation {
  capabilityKey: string;
  providerKey?: string;
  autonomyLevel: AutonomyLevel;
  evidenceKinds: string[];
  rights: string[];
  reversible: boolean;
  hasReceiptAdapter: boolean;
  hasIdempotencyKey: boolean;
  estimatedExternalCostEur: number;
  effects: string[];
}

const rank: Record<AutonomyLevel, number> = { L0: 0, L1: 1, L2: 2, L3: 3 };

export function validateCapabilityInvocation(
  contract: CapabilityContract,
  invocation: CapabilityInvocation,
): { allowed: boolean; reasons: string[] } {
  const reasons: string[] = [];
  if (!contract.active) reasons.push("capability contract inactive");
  if (contract.key !== invocation.capabilityKey) reasons.push("capability key mismatch");
  if (rank[invocation.autonomyLevel] > rank[contract.maxAutonomy]) reasons.push("requested autonomy exceeds capability contract");
  if (contract.reversible && !invocation.reversible) reasons.push("invocation is not reversible as required");
  if (contract.receiptRequired && !invocation.hasReceiptAdapter) reasons.push("receipt adapter required");
  if (contract.idempotencyRequired && !invocation.hasIdempotencyKey) reasons.push("idempotency key required");
  if (invocation.estimatedExternalCostEur > contract.maxExternalCostEur + Number.EPSILON) reasons.push("external cost exceeds capability contract");
  for (const evidenceKind of contract.requiredEvidenceKinds) {
    if (!invocation.evidenceKinds.includes(evidenceKind)) reasons.push(`missing evidence kind: ${evidenceKind}`);
  }
  for (const right of contract.requiredRights) {
    if (!invocation.rights.includes(right)) reasons.push(`missing required right: ${right}`);
  }
  if (invocation.providerKey && contract.allowedProviders.length > 0 && !contract.allowedProviders.includes(invocation.providerKey)) {
    reasons.push("provider not allowed by capability contract");
  }
  for (const effect of invocation.effects) {
    if (contract.forbiddenEffects.includes(effect)) reasons.push(`forbidden effect: ${effect}`);
  }
  return { allowed: reasons.length === 0, reasons };
}
