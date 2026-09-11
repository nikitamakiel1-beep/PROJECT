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
  runtimeVersion: "0.6.1-test",
  commitSha: "abc123",
  environment: "test",
  requestTimeoutMs: 1000,
};

class EmptyDb extends SupabaseHttp {
  constructor() { super(env); }
  override async select<T>(): Promise<T> { return [] as T; }
  override async insert<T>(): Promise<T> { return [] as T; }
  override async rpc<T>(functionName: string): Promise<T> {
    if (functionName === "creixement_reap_expired_leases_v6") {
      return [{ job_requeued: 0, job_dead_lettered: 0, outbox_requeued: 0, outbox_dead_lettered: 0 }] as T;
    }
    return [] as T;
  }
}

class SchedulingFailureDb extends EmptyDb {
  override async select<T>(): Promise<T> { throw new Error("schedule unavailable"); }
}

test("empty tick succeeds without fabricating work", async () => {
  const result = await runRuntimeTick(new EmptyDb(), env, { now: new Date("2026-09-11T20:00:00Z") });
  assert.equal(result.ok, true);
  assert.equal(result.phases.maintenance.ok, true);
  assert.equal(result.phases.outbox.ok, true);
  assert.equal(result.phases.scheduling.ok, true);
  assert.equal(result.phases.reconciliation.ok, true);
  assert.equal(result.phases.execution.ok, true);
  assert.equal(result.runtimeId, "test-runtime");
  assert.equal(result.version, "0.6.1-test");
});

test("one phase failure is explicit and other phases are still attempted", async () => {
  const result = await runRuntimeTick(new SchedulingFailureDb(), env, { now: new Date("2026-09-11T20:00:00Z") });
  assert.equal(result.ok, false);
  assert.equal(result.phases.scheduling.ok, false);
  assert.match(result.phases.scheduling.error ?? "", /schedule unavailable/);
  assert.equal(result.phases.maintenance.ok, true);
  assert.equal(result.phases.outbox.ok, true);
  assert.equal(result.phases.reconciliation.ok, true);
  assert.equal(result.phases.execution.ok, true);
});
