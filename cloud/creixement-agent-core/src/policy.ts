import type { PolicyDecision, PolicyEnvelope, ProposedAction } from "./types.js";

const LEVEL: Record<"L0" | "L1" | "L2" | "L3", number> = { L0: 0, L1: 1, L2: 2, L3: 3 };

const HARD_DENY = new Set([
  "rights_or_consent_bypass",
  "unreceipted_external_action",
  "secret_exfiltration",
  "audit_disable",
  "authentication_bypass",
]);

const HUMAN_GATED = new Set([
  "material_contract_signature",
  "bank_transfer",
  "unrestricted_payment",
  "property_offer",
  "property_purchase",
  "financing_commitment",
  "destructive_governed_record_deletion",
]);

export interface PolicyRuntimeContext {
  now?: Date;
  actionsThisRun?: number;
  externalSpendTodayEur?: number;
}

function limitNumber(envelope: PolicyEnvelope, key: string): number | undefined {
  const value = envelope.limits?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function limitBoolean(envelope: PolicyEnvelope, key: string): boolean | undefined {
  const value = envelope.limits?.[key];
  return typeof value === "boolean" ? value : undefined;
}

function limitList(envelope: PolicyEnvelope, key: string): string[] | undefined {
  const value = envelope.limits?.[key];
  return Array.isArray(value) && value.every((x) => typeof x === "string") ? value : undefined;
}

export function decidePolicy(
  action: ProposedAction,
  envelopes: PolicyEnvelope[],
  context: PolicyRuntimeContext = {},
): PolicyDecision {
  if (HARD_DENY.has(action.actionClass)) {
    return {
      allowed: false,
      requiresHumanApproval: false,
      reason: "Action class is constitutionally prohibited and cannot be approved around the control plane.",
    };
  }

  if (HUMAN_GATED.has(action.actionClass)) {
    return {
      allowed: false,
      requiresHumanApproval: true,
      reason: "Action class is non-delegable under the default constitution.",
    };
  }

  if (!action.hasReceiptAdapter) {
    return {
      allowed: false,
      requiresHumanApproval: false,
      reason: "No real execution/receipt adapter exists. Unavailable capabilities must not be fabricated.",
    };
  }

  if (!action.rightsSatisfied) {
    return {
      allowed: false,
      requiresHumanApproval: false,
      reason: "Rights/source prerequisites are not satisfied.",
    };
  }

  if (!action.consentSatisfied) {
    return {
      allowed: false,
      requiresHumanApproval: false,
      reason: "Consent/contact prerequisites are not satisfied.",
    };
  }

  const now = context.now ?? new Date();
  if (action.expiresAt && new Date(action.expiresAt).getTime() <= now.getTime()) {
    return {
      allowed: false,
      requiresHumanApproval: false,
      reason: "The proposed action has expired and must be re-planned from fresh evidence.",
    };
  }

  const envelope = envelopes.find((e) => e.actionClass === action.actionClass && e.enabled);
  if (!envelope) {
    return {
      allowed: false,
      requiresHumanApproval: action.autonomyLevel === "L3" || action.externalEffect === "external",
      reason: "No active authorization envelope exists for this action class.",
    };
  }

  if (envelope.expiresAt && new Date(envelope.expiresAt).getTime() <= now.getTime()) {
    return {
      allowed: false,
      requiresHumanApproval: false,
      reason: "Authorization envelope is expired.",
      policyVersion: envelope.version,
    };
  }

  if (LEVEL[action.autonomyLevel] > LEVEL[envelope.maxAutonomy]) {
    return {
      allowed: false,
      requiresHumanApproval: true,
      reason: `Action requires ${action.autonomyLevel}, above envelope maximum ${envelope.maxAutonomy}.`,
      policyVersion: envelope.version,
    };
  }

  const allowedAgents = envelope.allowedAgents ?? limitList(envelope, "allowedAgents");
  if (allowedAgents && !allowedAgents.includes(action.actorAgent)) {
    return {
      allowed: false,
      requiresHumanApproval: false,
      reason: "Actor agent is outside the envelope allowlist.",
      policyVersion: envelope.version,
    };
  }

  const allowedConnectors = envelope.allowedConnectors ?? limitList(envelope, "allowedConnectors");
  if (action.connector && allowedConnectors && !allowedConnectors.includes(action.connector)) {
    return {
      allowed: false,
      requiresHumanApproval: false,
      reason: "Connector is outside the envelope allowlist.",
      policyVersion: envelope.version,
    };
  }

  if (action.externalEffect === "external" && limitBoolean(envelope, "allowExternalEffect") !== true) {
    return {
      allowed: false,
      requiresHumanApproval: true,
      reason: "External effect is not explicitly enabled by this envelope.",
      policyVersion: envelope.version,
    };
  }

  const estimatedCost = Math.max(0, action.estimatedExternalCostEur ?? 0);
  const maxActionCost = limitNumber(envelope, "maxEstimatedExternalCostEur");
  if (estimatedCost > 0 && maxActionCost === undefined) {
    return {
      allowed: false,
      requiresHumanApproval: true,
      reason: "External spend is not bounded by the authorization envelope.",
      policyVersion: envelope.version,
    };
  }
  if (maxActionCost !== undefined && estimatedCost > maxActionCost) {
    return {
      allowed: false,
      requiresHumanApproval: true,
      reason: "Estimated external cost exceeds the per-action envelope limit.",
      policyVersion: envelope.version,
    };
  }

  const maxDailyCost = limitNumber(envelope, "maxExternalSpendPerDayEur");
  if (maxDailyCost !== undefined && (context.externalSpendTodayEur ?? 0) + estimatedCost > maxDailyCost) {
    return {
      allowed: false,
      requiresHumanApproval: true,
      reason: "Action would exceed the daily external-spend envelope.",
      policyVersion: envelope.version,
    };
  }

  const maxBatchSize = limitNumber(envelope, "maxBatchSize");
  if (maxBatchSize !== undefined && (action.batchSize ?? 1) > maxBatchSize) {
    return {
      allowed: false,
      requiresHumanApproval: true,
      reason: "Action batch size exceeds the envelope limit.",
      policyVersion: envelope.version,
    };
  }

  const maxActionsPerRun = limitNumber(envelope, "maxActionsPerRun");
  if (maxActionsPerRun !== undefined && (context.actionsThisRun ?? 0) >= maxActionsPerRun) {
    return {
      allowed: false,
      requiresHumanApproval: false,
      reason: "Run action limit reached; remaining work must be deferred to a new bounded run.",
      policyVersion: envelope.version,
    };
  }

  if (action.autonomyLevel === "L3" && envelope.maxAutonomy !== "L3") {
    return {
      allowed: false,
      requiresHumanApproval: true,
      reason: "Consequential action is outside the currently authorized envelope.",
      policyVersion: envelope.version,
    };
  }

  return {
    allowed: true,
    requiresHumanApproval: false,
    reason: "Action is explicitly authorized inside the active constitutional envelope and its bounded limits.",
    policyVersion: envelope.version,
  };
}

export function safeDefaultEnvelopes(): PolicyEnvelope[] {
  const safe = (actionClass: string, limits: PolicyEnvelope["limits"] = {}): PolicyEnvelope => ({
    version: "2.1.0",
    actionClass,
    maxAutonomy: "L2",
    enabled: true,
    limits: {
      maxActionsPerRun: 25,
      maxEstimatedExternalCostEur: 0,
      allowExternalEffect: false,
      ...limits,
    },
  });

  return [
    safe("public_research", { maxBatchSize: 50 }),
    safe("approved_source_research", { maxBatchSize: 50 }),
    safe("internal_normalise_dedupe", { maxBatchSize: 1000 }),
    safe("internal_crm_reversible_write", { maxBatchSize: 50 }),
    safe("report_draft", { maxBatchSize: 20 }),
    safe("internal_qa", { maxBatchSize: 50 }),
    safe("create_product_hypothesis", { maxBatchSize: 10 }),
    safe("create_experiment", { maxBatchSize: 10 }),
    safe("bounded_enrichment", { maxBatchSize: 25 }),
    safe("genome_evolution", { maxBatchSize: 10 }),
    safe("child_agent_spawn", { maxBatchSize: 6 }),
  ];
}
