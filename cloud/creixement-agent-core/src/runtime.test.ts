import test from "node:test";
import assert from "node:assert/strict";
import {
  canLeaseJob,
  deterministicIdempotencyKey,
  evaluateCircuitBreaker,
  nextBackoffSeconds,
  recordCircuitBreakerFailure,
  stableDigest,
  truthLabel,
  validateRuntimeTransition,
} from "./runtime.js";

test("stable digest ignores object key insertion order", () => {
  assert.equal(stableDigest({ a: 1, b: { x: 2, y: 3 } }), stableDigest({ b: { y: 3, x: 2 }, a: 1 }));
});

test("idempotency keys are deterministic", () => {
  const a = deterministicIdempotencyKey({ action: "research", target: "acme", payload: { q: 1 } });
  const b = deterministicIdempotencyKey({ payload: { q: 1 }, target: "acme", action: "research" });
  assert.equal(a, b);
  assert.match(a, /^cx:[0-9a-f]{64}$/);
});

test("lease eligibility respects schedule, lease and max attempts", () => {
  const now = new Date("2026-09-09T10:00:00.000Z");
  const base = {
    id: "j1",
    jobKey: "radar",
    idempotencyKey: "i1",
    status: "queued" as const,
    attempt: 0,
    maxAttempts: 3,
    input: {},
  };
  assert.equal(canLeaseJob(base, now), true);
  assert.equal(canLeaseJob({ ...base, scheduledFor: "2026-09-09T11:00:00.000Z" }, now), false);
  assert.equal(canLeaseJob({ ...base, leaseUntil: "2026-09-09T10:05:00.000Z" }, now), false);
  assert.equal(canLeaseJob({ ...base, attempt: 3 }, now), false);
});

test("backoff grows exponentially but caps", () => {
  const p = { maxAttempts: 5, baseDelaySeconds: 10, maxDelaySeconds: 60, jitterPct: 0 };
  assert.equal(nextBackoffSeconds(1, p), 10);
  assert.equal(nextBackoffSeconds(2, p), 20);
  assert.equal(nextBackoffSeconds(4, p), 60);
});

test("circuit breaker opens then becomes half-open after cooldown", () => {
  const now = new Date("2026-09-09T10:00:00.000Z");
  const policy = { failureThreshold: 2, coolDownSeconds: 60 };
  const first = recordCircuitBreakerFailure({ state: "closed", consecutiveFailures: 0 }, policy, now);
  assert.equal(first.state, "closed");
  const second = recordCircuitBreakerFailure(first, policy, now);
  assert.equal(second.state, "open");
  const halfOpen = evaluateCircuitBreaker(second, new Date("2026-09-09T10:01:00.000Z"));
  assert.equal(halfOpen.state, "half_open");
});

test("terminal runtime states cannot be reopened", () => {
  assert.equal(validateRuntimeTransition("running", "succeeded"), true);
  assert.equal(validateRuntimeTransition("succeeded", "queued"), false);
  assert.equal(validateRuntimeTransition("dead_lettered", "queued"), false);
});

test("truth hierarchy never calls a bare hypothesis verified", () => {
  assert.equal(truthLabel({}), "hypothesis");
  assert.equal(truthLabel({ isInference: true }), "evidence_backed_model_inference");
  assert.equal(truthLabel({ hasConnectorReceipt: true }), "executed_connector_receipt");
  assert.equal(truthLabel({ hasVerifiedExternalOutcome: true, hasConnectorReceipt: true }), "verified_external_outcome");
});
