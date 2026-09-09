import { createHash } from "node:crypto";

export type RuntimeStatus =
  | "queued"
  | "leased"
  | "running"
  | "succeeded"
  | "failed"
  | "blocked"
  | "cancelled"
  | "dead_lettered";

export interface RuntimeJob {
  id: string;
  jobKey: string;
  idempotencyKey: string;
  status: RuntimeStatus;
  attempt: number;
  maxAttempts: number;
  scheduledFor?: string;
  leaseOwner?: string;
  leaseUntil?: string;
  input: Record<string, unknown>;
  lastError?: unknown;
}

export interface RuntimeEvent {
  eventKey: string;
  topic: string;
  type: string;
  payload: Record<string, unknown>;
  priority: number;
  attempts: number;
  maxAttempts: number;
  availableAt: string;
  leaseOwner?: string;
  leaseUntil?: string;
  status: "pending" | "leased" | "processed" | "failed" | "dead_lettered" | "cancelled";
}

export interface RetryPolicy {
  maxAttempts: number;
  baseDelaySeconds: number;
  maxDelaySeconds: number;
  jitterPct: number;
}

export interface CircuitBreakerState {
  state: "closed" | "open" | "half_open";
  consecutiveFailures: number;
  openedAt?: string;
  retryAt?: string;
}

export interface CircuitBreakerPolicy {
  failureThreshold: number;
  coolDownSeconds: number;
}

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => [k, canonical(v)]),
    );
  }
  return value;
}

export function stableDigest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(canonical(value))).digest("hex");
}

export function deterministicIdempotencyKey(parts: Record<string, unknown>): string {
  return `cx:${stableDigest(parts)}`;
}

export function canLeaseJob(job: RuntimeJob, now = new Date()): boolean {
  if (!(job.status === "queued" || job.status === "failed")) return false;
  if (job.attempt >= job.maxAttempts) return false;
  if (job.scheduledFor && new Date(job.scheduledFor).getTime() > now.getTime()) return false;
  if (job.leaseUntil && new Date(job.leaseUntil).getTime() > now.getTime()) return false;
  return true;
}

export function nextBackoffSeconds(attempt: number, policy: RetryPolicy, deterministicJitterSeed = 0): number {
  if (attempt <= 0) return 0;
  const exponential = Math.min(policy.maxDelaySeconds, policy.baseDelaySeconds * 2 ** (attempt - 1));
  const jitterBound = Math.max(0, Math.min(1, policy.jitterPct));
  const normalizedSeed = Math.max(-1, Math.min(1, deterministicJitterSeed));
  return Math.max(0, Math.round(exponential * (1 + jitterBound * normalizedSeed)));
}

export function shouldDeadLetter(attempt: number, maxAttempts: number): boolean {
  return attempt >= maxAttempts;
}

export function recordCircuitBreakerSuccess(_: CircuitBreakerState): CircuitBreakerState {
  return { state: "closed", consecutiveFailures: 0 };
}

export function recordCircuitBreakerFailure(
  current: CircuitBreakerState,
  policy: CircuitBreakerPolicy,
  now = new Date(),
): CircuitBreakerState {
  const failures = current.consecutiveFailures + 1;
  if (failures < policy.failureThreshold) {
    return { state: "closed", consecutiveFailures: failures };
  }
  const retryAt = new Date(now.getTime() + policy.coolDownSeconds * 1000).toISOString();
  return {
    state: "open",
    consecutiveFailures: failures,
    openedAt: now.toISOString(),
    retryAt,
  };
}

export function evaluateCircuitBreaker(
  current: CircuitBreakerState,
  now = new Date(),
): CircuitBreakerState {
  if (current.state !== "open" || !current.retryAt) return current;
  if (new Date(current.retryAt).getTime() <= now.getTime()) {
    return { ...current, state: "half_open" };
  }
  return current;
}

export function validateRuntimeTransition(from: RuntimeStatus, to: RuntimeStatus): boolean {
  const allowed: Record<RuntimeStatus, RuntimeStatus[]> = {
    queued: ["leased", "blocked", "cancelled"],
    leased: ["running", "queued", "failed", "cancelled"],
    running: ["succeeded", "failed", "blocked", "cancelled"],
    failed: ["queued", "leased", "dead_lettered", "cancelled"],
    blocked: ["queued", "cancelled"],
    succeeded: [],
    cancelled: [],
    dead_lettered: [],
  };
  return allowed[from].includes(to);
}

export function truthLabel(input: {
  hasVerifiedExternalOutcome?: boolean;
  hasConnectorReceipt?: boolean;
  hasGovernedEvidence?: boolean;
  humanApproved?: boolean;
  isInference?: boolean;
}): "verified_external_outcome" | "executed_connector_receipt" | "governed_source_evidence" | "human_approved_decision" | "evidence_backed_model_inference" | "hypothesis" {
  if (input.hasVerifiedExternalOutcome) return "verified_external_outcome";
  if (input.hasConnectorReceipt) return "executed_connector_receipt";
  if (input.hasGovernedEvidence) return "governed_source_evidence";
  if (input.humanApproved) return "human_approved_decision";
  if (input.isInference) return "evidence_backed_model_inference";
  return "hypothesis";
}
