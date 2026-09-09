import type { VercelRequest, VercelResponse } from "@vercel/node";
import { authorizeBearer } from "../src/auth.js";
import { loadEnv } from "../src/env.js";
import { SupabaseHttp } from "../src/supabase.js";

interface ReleaseBody {
  releaseKey?: string;
  branch?: string;
  commitSha?: string;
  ciStatus?: "success" | "failure" | "pending" | "unknown";
  evidenceRefs?: string[];
}

function parseBody(value: unknown): ReleaseBody {
  if (typeof value === "string") {
    try { return JSON.parse(value) as ReleaseBody; } catch { return {}; }
  }
  return value && typeof value === "object" ? value as ReleaseBody : {};
}

export default async function handler(request: VercelRequest, response: VercelResponse): Promise<void> {
  if (request.method !== "GET" && request.method !== "POST") {
    response.setHeader("Allow", "GET, POST");
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

    if (request.method === "POST") {
      const body = parseBody(request.body);
      const commitSha = body.commitSha?.trim() || env.commitSha;
      if (!commitSha) {
        response.status(400).json({ ok: false, error: "commit_sha_required" });
        return;
      }
      const releaseKey = body.releaseKey?.trim() || `runtime-v6:${commitSha}`;
      const branch = body.branch?.trim() || process.env.VERCEL_GIT_COMMIT_REF?.trim() || "unknown";
      const ciStatus = body.ciStatus ?? "unknown";
      const attestation = await db.rpc<Record<string, unknown>>("creixement_assess_release_v6", {
        p_release_key: releaseKey.slice(0, 300),
        p_branch: branch.slice(0, 300),
        p_commit_sha: commitSha.slice(0, 100),
        p_ci_status: ciStatus,
        p_evidence_refs: Array.isArray(body.evidenceRefs) ? body.evidenceRefs.slice(0, 100) : [],
      });
      response.status(200).json({ ok: true, attestation });
      return;
    }

    const [attestations, health, scheduler, providers] = await Promise.all([
      db.select<Array<Record<string, unknown>>>("release_attestations_v6?select=*&order=assessed_at.desc&limit=10"),
      db.select<Array<Record<string, unknown>>>("v_operating_health_v6?select=*&limit=1"),
      db.select<Array<Record<string, unknown>>>("v_scheduler_readiness_v6?select=*&limit=1"),
      db.select<Array<Record<string, unknown>>>("v_provider_readiness_v6?select=provider_key,runtime_state,authorized,runtime_ready,operational&order=provider_key.asc"),
    ]);

    response.status(200).json({
      ok: true,
      observedAt: new Date().toISOString(),
      latest: attestations.at(0) ?? null,
      recentAttestations: attestations,
      operatingHealth: health.at(0) ?? null,
      scheduler: scheduler.at(0) ?? null,
      providers,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    response.status(503).json({ ok: false, error: "release_status_unavailable", detail: message.slice(0, 1000) });
  }
}
