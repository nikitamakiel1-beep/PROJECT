export type ConnectorDeclaredState = "connected" | "needs_auth" | "needs_setup" | "degraded" | "disabled" | string;
export type EffectiveConnectorHealth = "runtime_ready" | "not_runtime_ready" | "blocked" | "degraded" | "disabled" | "unknown";

export interface ConnectorDescriptor {
  slug: string;
  state: ConnectorDeclaredState;
  canRead: boolean;
  canWrite: boolean;
  runtimeConnection?: string | null;
  requiredSecrets?: string[];
  lastError?: string | null;
  lastVerifiedHealthAt?: string | null;
}

const NOT_WIRED = new Set([
  "available_not_wired",
  "chat_connector_available_runtime_not_wired",
  "contracts_and_provider_access_required",
  "provider_setup_required",
  "project_created_build_blocked_by_credits",
  "cloud_service_not_deployed",
  "optional_migration_not_configured",
  "future",
]);

export function effectiveConnectorHealth(connector: ConnectorDescriptor): EffectiveConnectorHealth {
  if (connector.state === "disabled") return "disabled";
  if (connector.state === "needs_auth" || connector.state === "needs_setup") return "blocked";
  if (connector.state === "degraded") return "degraded";
  if (!connector.runtimeConnection || NOT_WIRED.has(connector.runtimeConnection)) return "not_runtime_ready";
  if (connector.state === "connected") return "runtime_ready";
  return "unknown";
}

export function connectorCapabilityDecision(
  connector: ConnectorDescriptor,
  mode: "read" | "write",
): { allowed: boolean; reason: string } {
  const health = effectiveConnectorHealth(connector);
  if (health !== "runtime_ready") {
    return { allowed: false, reason: `Connector ${connector.slug} is ${health}; declared availability is not runtime execution.` };
  }
  if (mode === "read" && !connector.canRead) return { allowed: false, reason: `Connector ${connector.slug} has no read capability.` };
  if (mode === "write" && !connector.canWrite) return { allowed: false, reason: `Connector ${connector.slug} has no write capability.` };
  return { allowed: true, reason: `Connector ${connector.slug} is runtime-ready for ${mode}.` };
}

export function missingSecretNames(connector: ConnectorDescriptor, availableSecretNames: Iterable<string>): string[] {
  const available = new Set(availableSecretNames);
  return (connector.requiredSecrets ?? []).filter((name) => !available.has(name));
}

export function connectorTruthSummary(connectors: ConnectorDescriptor[]): {
  total: number;
  runtimeReady: number;
  blocked: number;
  degraded: number;
  disabled: number;
  notRuntimeReady: number;
} {
  const result = { total: connectors.length, runtimeReady: 0, blocked: 0, degraded: 0, disabled: 0, notRuntimeReady: 0 };
  for (const connector of connectors) {
    switch (effectiveConnectorHealth(connector)) {
      case "runtime_ready": result.runtimeReady += 1; break;
      case "blocked": result.blocked += 1; break;
      case "degraded": result.degraded += 1; break;
      case "disabled": result.disabled += 1; break;
      case "not_runtime_ready": result.notRuntimeReady += 1; break;
      default: result.notRuntimeReady += 1;
    }
  }
  return result;
}
