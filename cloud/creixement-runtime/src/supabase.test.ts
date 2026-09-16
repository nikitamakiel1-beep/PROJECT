import assert from "node:assert/strict";
import test from "node:test";
import type { RuntimeEnv } from "./env.js";
import { databaseAuthHeaders, databaseRequestUrl, supabaseAuthHeaders } from "./supabase.js";

function runtime(overrides: Partial<RuntimeEnv> = {}): RuntimeEnv {
  return {
    supabaseUrl: "https://example.supabase.co",
    supabaseServiceRoleKey: "opaque-runtime-token-that-is-long-enough-for-relay",
    databaseRelayUrl: null,
    cronSecret: "cron",
    apiToken: "api",
    runtimeId: "kairon-cloudflare-v10",
    runtimeVersion: "1.0.0",
    commitSha: "abc123",
    environment: "test",
    requestTimeoutMs: 8000,
    ...overrides,
  };
}

test("modern Supabase secret keys are sent only as apikey", () => {
  assert.deepEqual(supabaseAuthHeaders("sb_secret_example"), {
    apikey: "sb_secret_example",
  });
});

test("legacy service_role JWTs retain Authorization bearer compatibility", () => {
  const key = "eyJlegacy-service-role";
  assert.deepEqual(supabaseAuthHeaders(key), {
    apikey: key,
    Authorization: `Bearer ${key}`,
  });
});

test("managed relay uses only runtime identity headers, never Supabase auth headers", () => {
  const env = runtime({ databaseRelayUrl: "https://creixement-ops-hub.lovable.app/api/runtime-db" });
  const headers = databaseAuthHeaders(env);
  assert.deepEqual(headers, {
    "x-creixement-runtime-token": env.supabaseServiceRoleKey,
    "x-creixement-runtime-id": "kairon-cloudflare-v10",
  });
  assert.equal("apikey" in headers, false);
  assert.equal("Authorization" in headers, false);
});

test("managed relay preserves relation/RPC path and query string", () => {
  const env = runtime({ databaseRelayUrl: "https://creixement-ops-hub.lovable.app/api/runtime-db/" });
  assert.equal(
    databaseRequestUrl(env, "runtime_heartbeats_v5?select=runtime_id&limit=1"),
    "https://creixement-ops-hub.lovable.app/api/runtime-db/runtime_heartbeats_v5?select=runtime_id&limit=1",
  );
  assert.equal(
    databaseRequestUrl(env, "rpc/creixement_record_heartbeat_v5"),
    "https://creixement-ops-hub.lovable.app/api/runtime-db/rpc/creixement_record_heartbeat_v5",
  );
});

test("direct database transport remains available outside managed relay mode", () => {
  const env = runtime({ supabaseServiceRoleKey: "sb_secret_current", databaseRelayUrl: null });
  assert.deepEqual(databaseAuthHeaders(env), { apikey: "sb_secret_current" });
  assert.equal(
    databaseRequestUrl(env, "v_runtime_readiness_v5?select=*&limit=1"),
    "https://example.supabase.co/rest/v1/v_runtime_readiness_v5?select=*&limit=1",
  );
});
