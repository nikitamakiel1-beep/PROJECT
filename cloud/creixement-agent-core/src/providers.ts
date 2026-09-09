export interface ProviderDescriptor {
  key: string;
  operations: string[];
  runtimeReady: boolean;
  rightsStatus: "permitted" | "restricted" | "unknown" | "blocked";
  receiptSupport: boolean;
  idempotentWrites: boolean;
  estimatedCostEur: number;
  reliability: number;
  evidenceQuality: number;
  freshness: number;
  latencyMs: number;
  circuitState: "closed" | "open" | "half_open";
}

export interface ProviderRequirement {
  operation: string;
  write: boolean;
  maxCostEur: number;
  minReliability: number;
  minEvidenceQuality: number;
  minFreshness: number;
}

export interface ProviderRoute {
  mode: "USE" | "BUILD" | "BUY" | "COMBINE" | "ABSTAIN";
  provider?: ProviderDescriptor;
  reason: string;
}

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));

function usable(provider: ProviderDescriptor, requirement: ProviderRequirement): boolean {
  if (!provider.operations.includes(requirement.operation)) return false;
  if (!provider.runtimeReady || provider.circuitState === "open") return false;
  if (provider.rightsStatus !== "permitted") return false;
  if (!provider.receiptSupport) return false;
  if (requirement.write && !provider.idempotentWrites) return false;
  if (provider.estimatedCostEur > requirement.maxCostEur) return false;
  if (provider.reliability < requirement.minReliability) return false;
  if (provider.evidenceQuality < requirement.minEvidenceQuality) return false;
  if (provider.freshness < requirement.minFreshness) return false;
  return true;
}

export function routeProvider(
  providers: ProviderDescriptor[],
  requirement: ProviderRequirement,
  buyEnabled = false,
): ProviderRoute {
  const candidates = providers.filter((provider) => usable(provider, requirement));
  if (candidates.length > 0) {
    const ranked = [...candidates].sort((a, b) => {
      const score = (p: ProviderDescriptor): number =>
        clamp01(p.reliability) * 0.35 +
        clamp01(p.evidenceQuality) * 0.30 +
        clamp01(p.freshness) * 0.20 -
        Math.min(p.estimatedCostEur / Math.max(requirement.maxCostEur || 1, 1), 1) * 0.10 -
        Math.min(p.latencyMs / 10000, 1) * 0.05;
      return score(b) - score(a) || a.key.localeCompare(b.key);
    });
    const best = ranked.at(0);
    if (!best) throw new Error("Provider ranking invariant failed");
    return { mode: "USE", provider: best, reason: "Best runtime-ready permitted provider satisfying the operation contract." };
  }

  const near = providers.some((provider) =>
    provider.operations.includes(requirement.operation) && provider.rightsStatus !== "blocked",
  );
  if (near) {
    return {
      mode: "BUILD",
      reason: "Providers exist but none satisfy runtime, rights, receipt, reliability, freshness or budget requirements; build or repair the adapter.",
    };
  }

  if (buyEnabled) {
    return { mode: "BUY", reason: "No internal/provider capability exists; procurement evaluation is permitted." };
  }

  return { mode: "ABSTAIN", reason: "No compliant capability is available and procurement is disabled." };
}
