import test from "node:test";
import assert from "node:assert/strict";
import { connectorCapabilityDecision, connectorTruthSummary, effectiveConnectorHealth, missingSecretNames } from "./connectors.js";

test("chat-connected connector is not misreported as runtime-ready", () => {
  const connector = {
    slug: "google-drive",
    state: "connected",
    canRead: true,
    canWrite: true,
    runtimeConnection: "chat_connector_available_runtime_not_wired",
  };
  assert.equal(effectiveConnectorHealth(connector), "not_runtime_ready");
  assert.equal(connectorCapabilityDecision(connector, "write").allowed, false);
});

test("runtime-connected connector gates by declared capability", () => {
  const connector = {
    slug: "market-data",
    state: "connected",
    canRead: true,
    canWrite: false,
    runtimeConnection: "server_adapter_verified",
  };
  assert.equal(effectiveConnectorHealth(connector), "runtime_ready");
  assert.equal(connectorCapabilityDecision(connector, "read").allowed, true);
  assert.equal(connectorCapabilityDecision(connector, "write").allowed, false);
});

test("secret check returns names only", () => {
  const missing = missingSecretNames(
    { slug: "x", state: "needs_auth", canRead: true, canWrite: true, requiredSecrets: ["A", "B"] },
    ["A"],
  );
  assert.deepEqual(missing, ["B"]);
});

test("truth summary counts effective runtime state", () => {
  const summary = connectorTruthSummary([
    { slug: "a", state: "connected", canRead: true, canWrite: true, runtimeConnection: "server_adapter_verified" },
    { slug: "b", state: "connected", canRead: true, canWrite: true, runtimeConnection: "available_not_wired" },
    { slug: "c", state: "disabled", canRead: false, canWrite: false },
  ]);
  assert.equal(summary.runtimeReady, 1);
  assert.equal(summary.notRuntimeReady, 1);
  assert.equal(summary.disabled, 1);
});
