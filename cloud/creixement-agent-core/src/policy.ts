import type { PolicyDecision, PolicyEnvelope, ProposedAction } from "./types.js";

const LEVEL: Record<"L0" | "L1" | "L2" | "L3", number> = { L0: 0, L1: 1, L2: 2, L3: 3 };

const NON_DELEGABLE = new Set([
  "material_contract_signature",
  "bank_transfer",
  "unrestricted_payment",
  "property_offer",
  "property_purchase",
  "financing_commitment",
  "destructive_governed_record_deletion",
  "rights_or_consent_bypass",
  "unreceipted_external_action",
]);

export function decidePolicy(action: ProposedAction, envelopes: PolicyEnvelope[]): PolicyDecision {
  if (NON_DELEGABLE.has(action.actionClass)) {
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

  const envelope = envelopes.find((e) => e.actionClass === action.actionClass && e.enabled);
  if (!envelope) {
    return {
      allowed: false,
      requiresHumanApproval: action.autonomyLevel === "L3",
      reason: "No active authorization envelope exists for this action class.",
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
    reason: "Action is explicitly authorized inside the active constitutional envelope.",
    policyVersion: envelope.version,
  };
}

export function safeDefaultEnvelopes(): PolicyEnvelope[] {
  return [
    { version: "2.0.0", actionClass: "public_research", maxAutonomy: "L2", enabled: true },
    { version: "2.0.0", actionClass: "approved_source_research", maxAutonomy: "L2", enabled: true },
    { version: "2.0.0", actionClass: "internal_normalise_dedupe", maxAutonomy: "L2", enabled: true },
    { version: "2.0.0", actionClass: "internal_crm_reversible_write", maxAutonomy: "L2", enabled: true },
    { version: "2.0.0", actionClass: "report_draft", maxAutonomy: "L2", enabled: true },
    { version: "2.0.0", actionClass: "internal_qa", maxAutonomy: "L2", enabled: true },
    { version: "2.0.0", actionClass: "create_product_hypothesis", maxAutonomy: "L2", enabled: true },
    { version: "2.0.0", actionClass: "create_experiment", maxAutonomy: "L2", enabled: true },
    { version: "2.0.0", actionClass: "bounded_enrichment", maxAutonomy: "L2", enabled: true },
    { version: "2.0.0", actionClass: "genome_evolution", maxAutonomy: "L2", enabled: true },
  ];
}
