import test from "node:test";
import assert from "node:assert/strict";
import { SupabaseHttp } from "./supabase.js";
import { runRuntimeTick } from "./tick.js";
import type { RuntimeEnv } from "./env.js";

const env: RuntimeEnv = {
  supabaseUrl: "https://example.supabase.co",
  supabaseServiceRoleKey: "service-role-test",
  cronSecret: "cron-test",
  apiToken: "api-test",
  runtimeId: "test-runtime",
};

class EmptyDb extends SupabaseHttp {
  constructor() { super(env); }
  override async select<T>(): Promise<T> { return [] as T; }
  override async insert<T>(): Promise<T> { return [] as T; }
  override async rpc<T>(functionName: string): Promise<T> {
    if (functionName === "creixement_claim_jobs") return [] as T;
    return [] as T;
  }
}

class SchedulingFailureDb extends EmptyDb {
  override async select<T>(): Promise<T> { throw new Error("schedule unavailable"); }
}

test("empty runtime tick succeeds without fabricating work", async () => {
  const result = await runRuntimeTick(new EmptyDb(), env, { now: new Date("2026-09-09T19:00:00Z") });
  assert.equal(result.ok, true);
  assert.equal(result.scheduling.ok, true);
  assert.equal(result.execution.ok, true);
  assert.equal(result.execution.claimed, 0);
  assert.equal(result.runtimeId, "test-runtime");
});

test("tick reports scheduling failure explicitly", async () => {
  const result = await runRuntimeTick(new SchedulingFailureDb(), env, { now: new Date("2026-09-09T19:00:00Z") });
  assert.equal(result.ok, false);
  assert.equal(result.scheduling.ok, false);
  assert.match(result.scheduling.error ?? "", /schedule unavailable/);
  // Execution phase is attempted independently instead of being falsely marked successful as a whole.
  assert.equal(result.execution.ok, true);
});
