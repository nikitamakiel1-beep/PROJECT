import type { VercelRequest, VercelResponse } from "@vercel/node";
import { authorizeBearer } from "../src/auth.js";
import { loadEnv } from "../src/env.js";
import { enqueueDueCronJobs } from "../src/scheduler.js";
import { SupabaseHttp } from "../src/supabase.js";
import { processClaimedJobs } from "../src/worker.js";

async function heartbeat(db: SupabaseHttp, env: ReturnType<typeof loadEnv>, status: "healthy" | "degraded", metadata: Record<string, unknown>): Promise<void> {
  await db.rpc("creixement_record_heartbeat_v5", {
    p_runtime_id: env.runtimeId,
    p_version: env.runtimeVersion,
    p_commit_sha: env.commitSha,
    p_status: status,
    p_metadata: { ...metadata, environment: env.environment },
  });
}

export default async function handler(req: VercelRequest, res: VercelResponse): Promise<void> {
  if (req.method !== "GET" && req.method !== "POST") {
    res.setHeader("Allow", "GET, POST");
    res.status(405).json({ ok: false, error: "method_not_allowed" });
    return;
  }

  let env;
  try {
    env = loadEnv();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    res.status(503).json({ ok: false, error: "runtime_not_configured", detail: message });
    return;
  }

  if (!authorizeBearer(req.headers.authorization, env.cronSecret)) {
    res.status(401).json({ ok: false, error: "unauthorized" });
    return;
  }

  const startedAt = new Date();
  const db = new SupabaseHttp(env);

  try {
    await heartbeat(db, env, "healthy", { phase: "tick_started", startedAt: startedAt.toISOString() });
    const schedule = await enqueueDueCronJobs(db, startedAt, 10);
    const worker = await processClaimedJobs(db, env, 8);
    const completedAt = new Date();
    const status = worker.failed === 0 ? "healthy" : "degraded";
    await heartbeat(db, env, status, {
      phase: "tick_completed",
      completedAt: completedAt.toISOString(),
      schedule,
      worker,
    });

    res.status(worker.failed === 0 ? 200 : 207).json({
      ok: worker.failed === 0,
      runtimeId: env.runtimeId,
      version: env.runtimeVersion,
      commitSha: env.commitSha,
      startedAt: startedAt.toISOString(),
      completedAt: completedAt.toISOString(),
      elapsedMs: completedAt.getTime() - startedAt.getTime(),
      schedule,
      worker,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    try {
      await heartbeat(db, env, "degraded", { phase: "tick_failed", error: message.slice(0, 1000) });
    } catch {
      // Preserve the primary failure; heartbeat storage may be the component that failed.
    }
    res.status(500).json({
      ok: false,
      runtimeId: env.runtimeId,
      version: env.runtimeVersion,
      commitSha: env.commitSha,
      error: "tick_failed",
      detail: message.slice(0, 1500),
      startedAt: startedAt.toISOString(),
      failedAt: new Date().toISOString(),
    });
  }
}
