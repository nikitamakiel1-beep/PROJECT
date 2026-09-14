import assert from "node:assert/strict";
import test from "node:test";
import { supabaseAuthHeaders } from "./supabase.js";

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
