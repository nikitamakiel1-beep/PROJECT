import type { VercelRequest, VercelResponse } from "@vercel/node";
import { authorizeBearer } from "../src/auth.js";
import { loadEnv } from "../src/env.js";
import { SupabaseHttp } from "../src/supabase.js";
import { runRuntimeTick } from "../src/tick.js";

export default async function handler(request: VercelRequest, response: VercelResponse): Promise<void> {
  if (request.method !== "GET") {
    response.status(405).json({ ok: false, error: "method_not_allowed" });
    return;
  }

  try {
    const env = loadEnv();
    if (!authorizeBearer(request.headers.authorization, env.cronSecret)) {
      response.status(401).json({ ok: false, error: "unauthorized" });
      return;
    }

    const db = new SupabaseHttp(env);
    const result = await runRuntimeTick(db, env);
    response.status(result.ok ? 200 : 207).json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    response.status(503).json({ ok: false, error: "tick_failed", detail: message.slice(0, 500) });
  }
}
