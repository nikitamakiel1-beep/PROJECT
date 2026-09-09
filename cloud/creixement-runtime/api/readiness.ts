import type { VercelRequest, VercelResponse } from "@vercel/node";
import { authorizeBearer } from "../src/auth.js";
import { loadEnv } from "../src/env.js";
import { SupabaseHttp } from "../src/supabase.js";

interface ConnectorHealthRow {
  slug: string;
  effective_health: string;
}

interface JobRow {
  job_key: string;
  enabled: boolean;
  required_connectors: string[];
}

interface GoalRow {
  goal_key: string;
  execution_mode: string;
  blocker_type: string | null;
  runnable: boolean;
  status: string;
}

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
    const [connectors, jobs, goals, incidents] = await Promise.all([
      db.select<ConnectorHealthRow[]>("v_connector_health?select=slug,effective_health&order=slug.asc"),
      db.select<JobRow[]>("job_definitions?select=job_key,enabled,required_connectors&order=job_key.asc"),
      db.select<GoalRow[]>("v_goal_queue_v4?select=goal_key,execution_mode,blocker_type,runnable,status&order=priority_score.desc"),
      db.select<Array<{ severity: string; status: string }>>("incidents?select=severity,status&status=neq.resolved&status=neq.closed"),
    ]);

    const connectorState = new Map(connectors.map((row) => [row.slug, row.effective_health]));
    const enabledJobs = jobs.filter((job) => job.enabled);
    const blockedEnabledJobs = enabledJobs.flatMap((job) => {
      const missing = job.required_connectors.filter((slug) => connectorState.get(slug) !== "runtime_ready");
      return missing.length ? [{ jobKey: job.job_key, missingConnectors: missing }] : [];
    });

    const criticalIncidents = incidents.filter((incident) => incident.severity === "critical").length;
    const internalJobs = enabledJobs.filter((job) => job.required_connectors.length === 0);
    const ownerQueue = goals.filter((goal) => goal.execution_mode === "owner" || goal.blocker_type === "owner_policy");
    const externalBlockers = goals.filter((goal) => goal.blocker_type === "external_account" || goal.blocker_type === "connector");

    const readyForInternalAutonomy = internalJobs.length > 0 && criticalIncidents === 0;
    const readyForConnectorAutonomy = blockedEnabledJobs.length === 0 && criticalIncidents === 0;
    const readyForExternalAutonomy = false;

    response.status(readyForInternalAutonomy ? 200 : 503).json({
      ok: readyForInternalAutonomy,
      runtimeId: env.runtimeId,
      observedAt: new Date().toISOString(),
      readiness: {
        internalAutonomy: readyForInternalAutonomy,
        connectorAutonomy: readyForConnectorAutonomy,
        externalAutonomy: readyForExternalAutonomy,
      },
      counts: {
        connectors: connectors.length,
        runtimeReadyConnectors: connectors.filter((row) => row.effective_health === "runtime_ready").length,
        enabledJobs: enabledJobs.length,
        internalJobs: internalJobs.length,
        blockedEnabledJobs: blockedEnabledJobs.length,
        criticalIncidents,
        ownerQueue: ownerQueue.length,
        externalBlockers: externalBlockers.length,
      },
      blockers: {
        enabledJobs: blockedEnabledJobs,
        owner: ownerQueue.map((goal) => goal.goal_key),
        external: externalBlockers.map((goal) => goal.goal_key),
        externalAutonomy: "Disabled until an explicit outbound/publication authorization envelope is configured and verified.",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    response.status(503).json({ ok: false, error: "readiness_unavailable", detail: message.slice(0, 1000) });
  }
}
