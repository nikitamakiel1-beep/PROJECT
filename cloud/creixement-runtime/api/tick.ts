import type { VercelRequest, VercelResponse } from "@vercel/node";
import { authorizeBearer } from "../src/auth.js";
import { loadEnv } from "../src/env.js";
import { SupabaseHttp } from "../src/supabase.js";
import { runRuntimeTick } from "../src/tick.js";

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

  try {
    const result = await runRuntimeTick(new SupabaseHttp(env), env);
    res.status(result.ok ? 200 : 207).json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    res.status(500).json({
      ok: false,
      runtimeId: env.runtimeId,
      version: env.runtimeVersion,
      commitSha: env.commitSha,
      error: "tick_failed",
      detail: message.slice(0, 1500),
      failedAt: new Date().toISOString(),
    });
  }
}
