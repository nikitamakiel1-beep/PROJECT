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
    const dashboard = await db.select<Array<Record<string, unknown>>>("v_chief_operator_dashboard?select=*&limit=1");
    response.status(200).json({
      ok: true,
      runtimeId: env.runtimeId,
      observedAt: new Date().toISOString(),
      database: "reachable",
      dashboard: dashboard.at(0) ?? null,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    response.status(503).json({ ok: false, error: "runtime_unhealthy", detail: message.slice(0, 500) });
  }
}
