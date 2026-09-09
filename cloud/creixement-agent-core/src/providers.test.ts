import test from "node:test";
import assert from "node:assert/strict";
import { routeProvider, type ProviderDescriptor, type ProviderRequirement } from "./providers.js";

const requirement: ProviderRequirement = {
  operation: "company.enrich",
  write: false,
  maxCostEur: 0,
  minReliability: 0.9,
  minEvidenceQuality: 0.8,
  minFreshness: 0.8,
};

const good: ProviderDescriptor = {
  key: "provider-good",
  operations: ["company.enrich"],
  runtimeReady: true,
  rightsStatus: "permitted",
  receiptSupport: true,
  idempotentWrites: true,
  estimatedCostEur: 0,
  reliability: 0.99,
  evidenceQuality: 0.9,
  freshness: 0.95,
  latencyMs: 1000,
  circuitState: "closed",
};

test("router chooses compliant runtime-ready provider", () => {
  const route = routeProvider([good], requirement);
  assert.equal(route.mode, "USE");
  assert.equal(route.provider?.key, "provider-good");
});

test("open circuit prevents provider use", () => {
  const route = routeProvider([{ ...good, circuitState: "open" }], requirement);
  assert.equal(route.mode, "BUILD");
});

test("procurement-disabled system abstains when no capability exists", () => {
  const route = routeProvider([], requirement, false);
  assert.equal(route.mode, "ABSTAIN");
});
