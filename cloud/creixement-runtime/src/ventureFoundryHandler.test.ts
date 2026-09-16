import test from "node:test";
import assert from "node:assert/strict";
import { ventureFoundryCycle } from "./ventureFoundryHandler.js";
import type { HandlerContext } from "./handlers.js";

test("venture foundry executes only the governed RPC and returns portfolio evidence", async () => {
  const rpcCalls: string[] = [];
  const selects: string[] = [];
  const ctx = {
    runtimeId: "runtime-test",
    definition: { handler_key: "business.venture_foundry_cycle" },
    execution: { id: "exec-1", idempotency_key: "foundry:1" },
    db: {
      rpc: async (name: string) => {
        rpcCalls.push(name);
        return [{ evaluated: 3, retained_candidates: 2, experiments_ready: 1, incubated_projects: 1, economic_l2_open: true }];
      },
      select: async (path: string) => {
        selects.push(path);
        if (path.startsWith("v_business_portfolio_summary_v10")) return [{ operating_projects: 1, incubating_projects: 1, executive_agent: "Kairon" }];
        if (path.startsWith("v_business_portfolio_v10")) return [{ project_key: "tectum", status: "operating" }];
        if (path.startsWith("v_business_foundry_v10")) return [{ candidate_key: "venture:x", decision: "incubate" }];
        return [];
      },
    },
  } as unknown as HandlerContext;

  const result = await ventureFoundryCycle(ctx);
  assert.deepEqual(rpcCalls, ["creixement_run_venture_foundry_v10"]);
  assert.equal(selects.length, 3);
  assert.equal(result.status, "succeeded");
  assert.equal(result.output.operator, "Kairon");
  assert.equal(result.output.autonomyCeiling, "L2");
  assert.equal(result.receipt?.externalEffects, 0);
  assert.equal(result.receipt?.consequentialAuthority, "L3-owner-only");
});

test("empty foundry result fails closed to zero activity", async () => {
  const ctx = {
    runtimeId: "runtime-test",
    definition: { handler_key: "business.venture_foundry_cycle" },
    execution: { id: "exec-2", idempotency_key: "foundry:2" },
    db: {
      rpc: async () => [],
      select: async () => [],
    },
  } as unknown as HandlerContext;

  const result = await ventureFoundryCycle(ctx);
  assert.equal(result.receipt?.evaluated, 0);
  assert.equal(result.receipt?.incubatedProjects, 0);
  assert.equal(result.receipt?.economicL2Open, false);
});
