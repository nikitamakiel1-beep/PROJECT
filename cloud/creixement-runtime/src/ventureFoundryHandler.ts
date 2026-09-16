import type { HandlerContext, HandlerResult } from "./handlers.js";

export interface VentureFoundryRunRow {
  evaluated: number;
  retained_candidates: number;
  experiments_ready: number;
  incubated_projects: number;
  economic_l2_open: boolean;
}

export async function ventureFoundryCycle(ctx: HandlerContext): Promise<HandlerResult> {
  const runRows = await ctx.db.rpc<VentureFoundryRunRow[]>("creixement_run_venture_foundry_v10", {});
  const run = runRows.at(0) ?? {
    evaluated: 0,
    retained_candidates: 0,
    experiments_ready: 0,
    incubated_projects: 0,
    economic_l2_open: false,
  };

  const [summaryRows, projects, candidates] = await Promise.all([
    ctx.db.select<Array<Record<string, unknown>>>("v_business_portfolio_summary_v10?select=*&limit=1"),
    ctx.db.select<Array<Record<string, unknown>>>(
      "v_business_portfolio_v10?select=project_key,display_name,project_type,niche,portfolio_role,status,origin,truth_level,autonomy_ceiling,executive_agent,updated_at&order=updated_at.desc&limit=25",
    ),
    ctx.db.select<Array<Record<string, unknown>>>(
      "v_business_foundry_v10?select=candidate_key,title,niche,stage,decision,autonomy_level,score,truth_level,last_evaluated_at&order=score.desc&limit=25",
    ),
  ]);

  const summary = summaryRows.at(0) ?? null;
  return {
    status: "succeeded",
    output: {
      operator: "Kairon",
      cycle: "business.venture_foundry_cycle",
      autonomyCeiling: "L2",
      executionBoundary: "internal-reversible-only",
      run,
      summary,
      projects,
      candidates,
      observedAt: new Date().toISOString(),
    },
    receipt: {
      operator: "Kairon",
      handler: "business.venture_foundry_cycle",
      runtimeId: ctx.runtimeId,
      evaluated: run.evaluated,
      retainedCandidates: run.retained_candidates,
      experimentsReady: run.experiments_ready,
      incubatedProjects: run.incubated_projects,
      economicL2Open: run.economic_l2_open,
      externalEffects: 0,
      consequentialAuthority: "L3-owner-only",
    },
  };
}
