import { createHash } from "node:crypto";

export interface AuthorityNode {
  key: string;
  actionClass: string;
  maxAutonomy: "L0" | "L1" | "L2" | "L3";
  forbidden: boolean;
  next: string[];
}

export interface PathExplorationResult {
  explored: number;
  terminal: number;
  forbiddenPaths: string[][];
  safePaths: string[][];
  digest: string;
}

export interface VetoCandidate {
  key: string;
  expectedValue: number;
  confidence: number;
  strategicFit: number;
  risk: number;
  hardVeto: boolean;
  vetoReasons: string[];
}

export interface HysteresisState {
  state: "off" | "candidate" | "on" | "degrading";
  consecutiveAbove: number;
  consecutiveBelow: number;
}

export interface CanaryObservation {
  id: string;
  passed: boolean;
  receipted: boolean;
  deterministicReplay: boolean;
  digestMatch: boolean;
}

function canonical(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  const entries = Object.entries(value as Record<string, unknown>)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, child]) => `${JSON.stringify(key)}:${canonical(child)}`);
  return `{${entries.join(",")}}`;
}

export function conwayStableDigest(value: unknown): string {
  return createHash("sha256").update(canonical(value)).digest("hex");
}

export function deterministicAuthorityTraversal(
  nodes: AuthorityNode[],
  startKey: string,
  options: { maxDepth?: number; maxPaths?: number } = {},
): PathExplorationResult {
  const byKey = new Map(nodes.map((node) => [node.key, node]));
  const maxDepth = Math.max(1, Math.min(options.maxDepth ?? 8, 32));
  const maxPaths = Math.max(1, Math.min(options.maxPaths ?? 200000, 200000));
  const queue: string[][] = [[startKey]];
  const safePaths: string[][] = [];
  const forbiddenPaths: string[][] = [];
  let explored = 0;
  let terminal = 0;

  while (queue.length > 0 && explored < maxPaths) {
    const path = queue.shift()!;
    explored += 1;
    const key = path[path.length - 1]!;
    const node = byKey.get(key);
    if (!node) {
      terminal += 1;
      safePaths.push(path);
      continue;
    }
    if (node.forbidden || node.maxAutonomy === "L3") {
      forbiddenPaths.push(path);
      terminal += 1;
      continue;
    }
    const next = [...new Set(node.next)].sort();
    if (next.length === 0 || path.length >= maxDepth) {
      safePaths.push(path);
      terminal += 1;
      continue;
    }
    for (const child of next) {
      if (path.includes(child)) continue;
      queue.push([...path, child]);
    }
  }

  return {
    explored,
    terminal,
    forbiddenPaths,
    safePaths,
    digest: conwayStableDigest({ safePaths, forbiddenPaths }),
  };
}

export function hardVetoSelection(candidates: VetoCandidate[]): { selected: VetoCandidate | null; vetoed: VetoCandidate[] } {
  const vetoed = candidates.filter((candidate) => candidate.hardVeto || candidate.vetoReasons.length > 0);
  const allowed = candidates.filter((candidate) => !candidate.hardVeto && candidate.vetoReasons.length === 0);
  const score = (candidate: VetoCandidate) =>
    (candidate.expectedValue * Math.max(0, candidate.confidence) * Math.max(0, candidate.strategicFit)) /
    Math.max(0.05, 1 + Math.max(0, candidate.risk));
  const selected = [...allowed].sort((a, b) => score(b) - score(a) || a.key.localeCompare(b.key))[0] ?? null;
  return { selected, vetoed };
}

export function updateHysteresis(
  prior: HysteresisState,
  score: number,
  config: { enterThreshold: number; exitThreshold: number; dwellEnter: number; dwellExit: number },
): HysteresisState {
  if (config.exitThreshold > config.enterThreshold) throw new Error("exitThreshold must be <= enterThreshold");
  const above = score >= config.enterThreshold;
  const below = score <= config.exitThreshold;
  let state = prior.state;
  const consecutiveAbove = above ? prior.consecutiveAbove + 1 : 0;
  const consecutiveBelow = below ? prior.consecutiveBelow + 1 : 0;

  if ((state === "off" || state === "candidate") && above) {
    state = consecutiveAbove >= config.dwellEnter ? "on" : "candidate";
  } else if ((state === "on" || state === "degrading") && below) {
    state = consecutiveBelow >= config.dwellExit ? "off" : "degrading";
  } else if (state === "candidate" && !above) {
    state = "off";
  } else if (state === "degrading" && !below) {
    state = "on";
  }

  return { state, consecutiveAbove, consecutiveBelow };
}

export function canaryPromotion(
  observations: CanaryObservation[],
  options: { minRuns?: number; minPassRate?: number } = {},
): { promotable: boolean; passRate: number; reason: string } {
  const minRuns = Math.max(1, options.minRuns ?? 5);
  const minPassRate = Math.max(0, Math.min(1, options.minPassRate ?? 1));
  if (observations.length < minRuns) return { promotable: false, passRate: 0, reason: "insufficient canary runs" };
  const valid = observations.filter((item) => item.passed && item.receipted && item.deterministicReplay && item.digestMatch);
  const passRate = valid.length / observations.length;
  return {
    promotable: passRate >= minPassRate,
    passRate,
    reason: passRate >= minPassRate ? "canary evidence satisfies promotion contract" : "canary evidence below promotion threshold",
  };
}

export function auditorOfAuditors(baseline: unknown, candidate: unknown): { match: boolean; baselineDigest: string; candidateDigest: string } {
  const baselineDigest = conwayStableDigest(baseline);
  const candidateDigest = conwayStableDigest(candidate);
  return { match: baselineDigest === candidateDigest, baselineDigest, candidateDigest };
}

const VOLATILE_PROJECTION_KEYS = new Set([
  "timestamp",
  "observedAt",
  "lastSeenAt",
  "heartbeatAt",
  "latencyMs",
  "runtimeTelemetry",
  "ephemeralNonce",
]);

export function sanitizePublicProjection(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizePublicProjection);
  if (value === null || typeof value !== "object") return value;
  const output: Record<string, unknown> = {};
  for (const [key, child] of Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b))) {
    if (VOLATILE_PROJECTION_KEYS.has(key)) continue;
    output[key] = sanitizePublicProjection(child);
  }
  return output;
}

export function deterministicSkillIdentity(input: { skillKey: string; version: string; contract: unknown }): { skillId: string; digest: string } {
  const digest = conwayStableDigest({ skillKey: input.skillKey, version: input.version, contract: sanitizePublicProjection(input.contract) });
  return { skillId: `${input.skillKey}@${input.version}:${digest.slice(0, 16)}`, digest };
}
