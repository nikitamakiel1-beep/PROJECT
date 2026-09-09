import test from "node:test";
import assert from "node:assert/strict";
import { signServiceRequest, verifyServiceRequest, type NonceStore, type ServiceIdentity } from "./serviceIdentity.js";

class MemoryNonceStore implements NonceStore {
  private readonly nonces = new Set<string>();
  async has(service: string, nonce: string): Promise<boolean> { return this.nonces.has(`${service}:${nonce}`); }
  async put(service: string, nonce: string): Promise<void> { this.nonces.add(`${service}:${nonce}`); }
}

const identity: ServiceIdentity = {
  service: "opportunity-worker",
  keyId: "k1",
  enabled: true,
  allowedAudiences: ["control-plane-api"],
  allowedOperations: ["opportunity.score"],
  maxClockSkewSeconds: 60,
};

test("signed service request verifies once and replay is blocked", async () => {
  const now = new Date("2026-09-09T18:00:00.000Z");
  const signed = signServiceRequest({
    service: "opportunity-worker",
    keyId: "k1",
    audience: "control-plane-api",
    operation: "opportunity.score",
    correlationId: "c1",
    nonce: "n1",
    timestamp: now.toISOString(),
    bodyDigest: "a".repeat(64),
  }, "secret");
  const store = new MemoryNonceStore();
  assert.equal((await verifyServiceRequest(signed, identity, "secret", store, now)).allowed, true);
  assert.equal((await verifyServiceRequest(signed, identity, "secret", store, now)).allowed, false);
});

test("wrong secret cannot verify", async () => {
  const now = new Date("2026-09-09T18:00:00.000Z");
  const signed = signServiceRequest({
    service: "opportunity-worker", keyId: "k1", audience: "control-plane-api", operation: "opportunity.score",
    correlationId: "c2", nonce: "n2", timestamp: now.toISOString(), bodyDigest: "b".repeat(64),
  }, "secret");
  assert.equal((await verifyServiceRequest(signed, identity, "wrong", new MemoryNonceStore(), now)).allowed, false);
});
