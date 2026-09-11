import type { VercelRequest, VercelResponse } from "@vercel/node";
import { authorizeBearer } from "../src/auth.js";
import { loadEnv } from "../src/env.js";
import { SupabaseHttp } from "../src/supabase.js";

export default async function handler(request: VercelRequest, response: VercelResponse): Promise<void> {
  if (request.method !== "GET") {
    response.status(405).json({ ok: false, error: "method_not_allowed" });
    return;
  }

  try {
    const env = loadEnv();
    if (!authorizeBearer(request.headers.authorization, env.apiToken)) {
      response.status(401).json({ ok: false, error: "unauthorized" });
      return;
    }

    const db = new SupabaseHttp(env);
    const [healthRows, schedulerRows, gateRows, connectorBlockers, ownerActions, goals, providers] = await Promise.all([
      db.select<Array<Record<string, unknown>>>("v_operating_health_v6?select=*&limit=1"),
      db.select<Array<Record<string, unknown>>>("v_scheduler_readiness_v6?select=*&limit=1"),
      db.select<Array<Record<string, unknown>>>("v_production_gate_v6?select=*&limit=1"),
      db.select<Array<Record<string, unknown>>>("v_enabled_job_connector_blockers_v6?select=*&order=job_key.asc"),
      db.select<Array<Record<string, unknown>>>("v_owner_action_queue_v4?select=*&limit=100"),
      db.select<Array<Record<string, unknown>>>("v_goal_queue_v4?select=goal_key,status,execution_mode,blocker_type,runnable,priority_score&order=priority_score.desc&limit=100"),
      db.select<Array<Record<string, unknown>>>("v_provider_readiness_v6?select=provider_key,runtime_state,authorized,runtime_ready,operational&order=provider_key.asc"),
    ]);

    const health = healthRows.at(0) ?? {};
    const scheduler = schedulerRows.at(0) ?? {};
    const productionGate = gateRows.at(0) ?? {};
    const healthyInstances = Number(health.healthy_runtime_instances ?? 0);
    const criticalDrift = Number(health.critical_drift ?? 0);
    const criticalIncidents = Number(health.critical_incidents ?? 0);
    const openJobDeadLetters = Number(health.open_job_dead_letters ?? 0);
    const openOutboxDeadLetters = Number(health.open_outbox_dead_letters ?? 0);
    const openHandlerCircuits = Number(health.open_handler_circuits ?? 0);
    const highFrequencyReady = scheduler.high_frequency_ready === true;

    const safetyClean = criticalDrift === 0 && criticalIncidents === 0
      && openJobDeadLetters === 0 && openOutboxDeadLetters === 0 && openHandlerCircuits === 0;
    const internalAutonomy = healthyInstances > 0 && safetyClean;
    const connectorAutonomy = internalAutonomy && connectorBlockers.length === 0;
    const continuousAutonomy = connectorAutonomy && highFrequencyReady;

    response.status(internalAutonomy ? 200 : 503).json({
      ok: internalAutonomy,
      runtimeId: env.runtimeId,
      version: env.runtimeVersion,
      commitSha: env.commitSha,
      observedAt: new Date().toISOString(),
      readiness: {
        internalAutonomy,
        connectorAutonomy,
        continuousAutonomy,
        externalAutonomy: false,
        productionPromotable: productionGate.promotable === true,
      },
      operatingHealth: health,
      scheduler,
      productionGate,
      blockers: {
        enabledJobConnectors: connectorBlockers,
        ownerActions,
        goals: goals.filter((goal) => goal.runnable !== true),
        safety: {
          criticalDrift,
          criticalIncidents,
          openJobDeadLetters,
          openOutboxDeadLetters,
          openHandlerCircuits,
        },
        externalAutonomy: "Disabled until explicit external-effect authorization envelopes, providers, budgets and receipts are all verified.",
      },
      providers,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    response.status(503).json({ ok: false, error: "readiness_unavailable", detail: message.slice(0, 1000) });
  }
}
