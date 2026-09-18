import type { VercelRequest, VercelResponse } from "@vercel/node";
import { loadEnv } from "../src/env.js";
import { SupabaseHttp } from "../src/supabase.js";

function ageSeconds(value: unknown): number | null {
  const ms = Date.parse(String(value ?? ""));
  return Number.isFinite(ms) ? Math.max(0, Math.round((Date.now() - ms) / 1000)) : null;
}

export default async function handler(request: VercelRequest, response: VercelResponse): Promise<void> {
  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    response.status(405).json({ ok: false, error: "method_not_allowed" });
    return;
  }

  try {
    const env = loadEnv();
    const db = new SupabaseHttp(env);
    const [proofRows, heartbeatRows, schedulerRows] = await Promise.all([
      db.select<Array<Record<string, unknown>>>("v_runtime_proof_summary_v11?select=*&limit=1"),
      db.select<Array<Record<string, unknown>>>(
        `runtime_heartbeats_v5?runtime_id=eq.${encodeURIComponent(env.runtimeId)}&select=runtime_id,version,commit_sha,status,last_seen_at,environment&order=last_seen_at.desc&limit=1`,
      ),
      db.select<Array<Record<string, unknown>>>("v_scheduler_readiness_v6?select=*&limit=1"),
    ]);

    const proof = proofRows.at(0) ?? {};
    const heartbeat = heartbeatRows.at(0) ?? {};
    const scheduler = schedulerRows.at(0) ?? {};
    const heartbeatAgeSeconds = ageSeconds(heartbeat.last_seen_at);
    const heartbeatFresh = heartbeatAgeSeconds !== null && heartbeatAgeSeconds <= 10 * 60;
    const commitMatches = Boolean(env.commitSha) && String(heartbeat.commit_sha ?? "") === env.commitSha;
    const schedulerVerified = proof.primary_scheduler_verified === true;
    const cadenceStable = proof.primary_cadence_stable === true;
    const databaseReachable = true;
    const operational = databaseReachable
      && heartbeat.status === "healthy"
      && heartbeatFresh
      && commitMatches
      && schedulerVerified
      && cadenceStable;

    response.status(operational ? 200 : 503).json({
      ok: operational,
      service: "creixement-runtime",
      operator: "Kairon",
      platform: "vercel-functions",
      scheduler: "supabase-pg-cron",
      diagnosticVersion: 11,
      observedAt: new Date().toISOString(),
      operational,
      configuration: {
        runtimeId: env.runtimeId,
        runtimeVersion: env.runtimeVersion,
        commit: env.commitSha,
        dataPlane: env.databaseRelayUrl ? "managed-relay" : "direct-supabase-compatibility",
        schedulerBindingKey: proof.scheduler_binding_key ?? null,
        platformState: proof.platform_state ?? null,
      },
      database: { reachable: databaseReachable, transport: env.databaseRelayUrl ? "managed-relay" : "direct" },
      heartbeat: {
        found: Boolean(heartbeat.runtime_id),
        status: heartbeat.status ?? null,
        version: heartbeat.version ?? null,
        commit: heartbeat.commit_sha ?? null,
        lastSeenAt: heartbeat.last_seen_at ?? null,
        ageSeconds: heartbeatAgeSeconds,
        fresh: heartbeatFresh,
        commitMatches,
      },
      cadence: {
        samples30m: Number(proof.samples_30m ?? 0),
        completedHealthyTicks30m: Number(proof.completed_healthy_ticks_30m ?? 0),
        stable: cadenceStable,
        schedulerVerified,
        lastVerifiedAt: proof.scheduler_last_verified_at ?? null,
        highFrequencyReady: scheduler.high_frequency_ready === true,
      },
      truth: {
        computeResponding: true,
        databaseReachabilityVerified: databaseReachable,
        schedulerExecutionVerified: schedulerVerified && cadenceStable,
        exactCommitVerified: commitMatches,
        cloudflareAuthoritative: false,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    response.status(503).json({
      ok: false,
      service: "creixement-runtime",
      platform: "vercel-functions",
      error: "runtime_proof_unavailable",
      detail: message.slice(0, 800),
      observedAt: new Date().toISOString(),
    });
  }
}
