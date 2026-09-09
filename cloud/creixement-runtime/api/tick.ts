import type { VercelRequest, VercelResponse } from "@vercel/node";
import { authorizeBearer } from "../src/auth.js";
import { loadEnv } from "../src/env.js";
import { enqueueDueCronJobs } from "../src/scheduler.js";
import { SupabaseHttp } from "../src/supabase.js";
import { processClaimedJobs } from "../src/worker.js";

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
    const schedule = await enqueueDueCronJobs(db, startedAt, 10);
    const worker = await processClaimedJobs(db, env, 8);
    const completedAt = new Date();

    res.status(200).json({
      ok: worker.failed === 0,
      runtimeId: env.runtimeId,
      startedAt: startedAt.toISOString(),
      completedAt: completedAt.toISOString(),
      elapsedMs: completedAt.getTime() - startedAt.getTime(),
      schedule,
      worker,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    res.status(500).json({
      ok: false,
      runtimeId: env.runtimeId,
      error: "tick_failed",
      detail: message.slice(0, 1500),
      startedAt: startedAt.toISOString(),
      failedAt: new Date().toISOString(),
    });
  }
}
