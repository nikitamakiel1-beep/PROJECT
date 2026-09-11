import { authorizeBearer } from "../../creixement-runtime/src/auth.js";
import type { RuntimeEnv } from "../../creixement-runtime/src/env.js";
import { SupabaseHttp } from "../../creixement-runtime/src/supabase.js";
import { runRuntimeTick } from "../../creixement-runtime/src/tick.js";

interface VersionMetadata {
  id: string;
  tag?: string;
  timestamp?: string;
}

interface Env {
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE_KEY: string;
  CRON_SECRET: string;
  CREIXEMENT_API_TOKEN: string;
  CREIXEMENT_OWNER_TOKEN: string;
  CREIXEMENT_RUNTIME_ID?: string;
  CREIXEMENT_RUNTIME_VERSION?: string;
  CREIXEMENT_COMMIT_SHA?: string;
  CREIXEMENT_BRANCH?: string;
  CREIXEMENT_ENVIRONMENT?: string;
  CREIXEMENT_DB_TIMEOUT_MS?: string;
  CF_VERSION_METADATA?: VersionMetadata;
}

interface OwnerDecisionBody {
  idempotencyKey?: string;
  subjectType?: string;
  subjectKey?: string;
  decision?: string;
  payloadDigest?: string;
  rationale?: string;
  modifications?: Record<string, unknown>;
  evidenceRefs?: string[];
}

interface ReleaseBody {
  releaseKey?: string;
  branch?: string;
  commitSha?: string;
  ciStatus?: "success" | "failure" | "pending" | "unknown";
  evidenceRefs?: string[];
}

function required(value: string | undefined, name: string): string {
  const normalized = value?.trim();
  if (!normalized) throw new Error(`Missing required binding: ${name}`);
  return normalized;
}

function boundedInteger(raw: string | undefined, fallback: number, min: number, max: number): number {
  if (!raw?.trim()) return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < min || value > max) throw new Error(`CREIXEMENT_DB_TIMEOUT_MS must be ${min}..${max}`);
  return value;
}

function buildRuntimeEnv(env: Env): RuntimeEnv {
  const supabaseUrl = required(env.SUPABASE_URL, "SUPABASE_URL").replace(/\/$/, "");
  if (!supabaseUrl.startsWith("https://")) throw new Error("SUPABASE_URL must use HTTPS");
  return {
    supabaseUrl,
    supabaseServiceRoleKey: required(env.SUPABASE_SERVICE_ROLE_KEY, "SUPABASE_SERVICE_ROLE_KEY"),
    cronSecret: required(env.CRON_SECRET, "CRON_SECRET"),
    apiToken: required(env.CREIXEMENT_API_TOKEN, "CREIXEMENT_API_TOKEN"),
    runtimeId: env.CREIXEMENT_RUNTIME_ID?.trim() || "cloudflare-runtime-v6",
    runtimeVersion: env.CREIXEMENT_RUNTIME_VERSION?.trim() || "0.6.2",
    commitSha: env.CREIXEMENT_COMMIT_SHA?.trim() || null,
    environment: env.CREIXEMENT_ENVIRONMENT?.trim() || "production",
    requestTimeoutMs: boundedInteger(env.CREIXEMENT_DB_TIMEOUT_MS, 8000, 1000, 30000),
  };
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function bearer(request: Request, secret: string): boolean {
  return authorizeBearer(request.headers.get("authorization") ?? undefined, secret);
}

async function safeBody<T extends object>(request: Request): Promise<T> {
  try {
    const value = await request.json<unknown>();
    return value && typeof value === "object" ? value as T : {} as T;
  } catch {
    return {} as T;
  }
}

async function executeTick(env: Env, source: string) {
  const runtime = buildRuntimeEnv(env);
  const db = new SupabaseHttp(runtime);
  const result = await runRuntimeTick(db, runtime, { lookbackMinutes: 1500, jobBatchSize: 12, outboxBatchSize: 40 });
  console.log(JSON.stringify({
    event: "creixement.runtime.tick",
    source,
    ok: result.ok,
    runtimeId: result.runtimeId,
    version: result.version,
    commitSha: result.commitSha,
    cloudflareVersionId: env.CF_VERSION_METADATA?.id ?? null,
    elapsedMs: result.elapsedMs,
    completedAt: result.completedAt,
    phases: result.phases,
  }));
  return result;
}

async function handleHealth(env: Env): Promise<Response> {
  const runtime = buildRuntimeEnv(env);
  const db = new SupabaseHttp(runtime);
  const [runtimeReadiness, operatingHealth] = await Promise.all([
    db.select<Array<Record<string, unknown>>>("v_runtime_readiness_v5?select=*&limit=1"),
    db.select<Array<Record<string, unknown>>>("v_operating_health_v6?select=*&limit=1"),
  ]);
  const readiness = runtimeReadiness.at(0) ?? null;
  const internalReady = readiness?.internal_runtime_ready === true;
  return json({
    ok: internalReady,
    platform: "cloudflare-workers",
    runtimeId: runtime.runtimeId,
    version: runtime.runtimeVersion,
    commitSha: runtime.commitSha,
    cloudflareVersionId: env.CF_VERSION_METADATA?.id ?? null,
    observedAt: new Date().toISOString(),
    runtimeReadiness: readiness,
    operatingHealth: operatingHealth.at(0) ?? null,
  }, internalReady ? 200 : 503);
}

async function handleReadiness(env: Env): Promise<Response> {
  const runtime = buildRuntimeEnv(env);
  const db = new SupabaseHttp(runtime);
  const [runtimeRows, gateRows, schedulerRows, providers, goals] = await Promise.all([
    db.select<Array<Record<string, unknown>>>("v_runtime_readiness_v5?select=*&limit=1"),
    db.select<Array<Record<string, unknown>>>("v_production_gate_v6?select=*&limit=1"),
    db.select<Array<Record<string, unknown>>>("v_scheduler_readiness_v6?select=*&limit=1"),
    db.select<Array<Record<string, unknown>>>("v_provider_readiness_v6?select=provider_key,runtime_state,authorized,runtime_ready,operational,last_verified_at&order=provider_key.asc"),
    db.select<Array<Record<string, unknown>>>("v_goal_queue_v4?select=goal_key,status,execution_mode,blocker_type,runnable&order=priority_score.desc"),
  ]);
  const runtimeReadiness = runtimeRows.at(0) ?? null;
  const internalReady = runtimeReadiness?.internal_runtime_ready === true;
  return json({
    ok: internalReady,
    observedAt: new Date().toISOString(),
    platform: "cloudflare-workers",
    runtime: runtimeReadiness,
    productionGate: gateRows.at(0) ?? null,
    scheduler: schedulerRows.at(0) ?? null,
    providers,
    goals,
  }, internalReady ? 200 : 503);
}

async function handleOwnerDecisions(request: Request, env: Env): Promise<Response> {
  const runtime = buildRuntimeEnv(env);
  const ownerToken = required(env.CREIXEMENT_OWNER_TOKEN, "CREIXEMENT_OWNER_TOKEN");
  if (!bearer(request, ownerToken)) return json({ ok: false, error: "unauthorized" }, 401);
  const db = new SupabaseHttp(runtime);

  if (request.method === "GET") {
    const decisions = await db.select<Array<Record<string, unknown>>>("v_owner_decision_queue_v6?select=*&order=created_at.asc&limit=100");
    return json({ ok: true, observedAt: new Date().toISOString(), decisions });
  }
  if (request.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);

  const body = await safeBody<OwnerDecisionBody>(request);
  const requiredFields = [body.idempotencyKey, body.subjectType, body.subjectKey, body.decision, body.payloadDigest];
  if (requiredFields.some((value) => typeof value !== "string" || value.trim().length === 0)) {
    return json({ ok: false, error: "missing_required_fields" }, 400);
  }
  if (!/^[0-9a-fA-F]{64}$/.test(body.payloadDigest!)) return json({ ok: false, error: "invalid_payload_digest" }, 400);

  const recorded = await db.rpc<Record<string, unknown>>("creixement_submit_owner_decision_v6", {
    p_idempotency_key: body.idempotencyKey!.slice(0, 200),
    p_subject_type: body.subjectType!.slice(0, 40),
    p_subject_key: body.subjectKey!.slice(0, 300),
    p_decision: body.decision!.slice(0, 20),
    p_payload_digest: body.payloadDigest!.toLowerCase(),
    p_rationale: body.rationale?.slice(0, 4000) ?? null,
    p_modifications: body.modifications ?? {},
    p_evidence_refs: Array.isArray(body.evidenceRefs) ? body.evidenceRefs.slice(0, 50) : [],
  });
  return json({ ok: true, recorded, execution: "not_performed", downstreamPolicyRecheckRequired: true }, 201);
}

async function handleReleaseStatus(request: Request, env: Env): Promise<Response> {
  const runtime = buildRuntimeEnv(env);
  if (!bearer(request, runtime.apiToken)) return json({ ok: false, error: "unauthorized" }, 401);
  const db = new SupabaseHttp(runtime);

  if (request.method === "POST") {
    const body = await safeBody<ReleaseBody>(request);
    const commitSha = body.commitSha?.trim() || runtime.commitSha;
    if (!commitSha) return json({ ok: false, error: "commit_sha_required" }, 400);
    const releaseKey = body.releaseKey?.trim() || `cloudflare-runtime-v6:${commitSha}`;
    const branch = body.branch?.trim() || env.CREIXEMENT_BRANCH?.trim() || "venture/creixement-overhaul-v6-converged";
    const attestation = await db.rpc<Record<string, unknown>>("creixement_assess_release_v6", {
      p_release_key: releaseKey.slice(0, 300),
      p_branch: branch.slice(0, 300),
      p_commit_sha: commitSha.slice(0, 100),
      p_ci_status: body.ciStatus ?? "unknown",
      p_evidence_refs: Array.isArray(body.evidenceRefs) ? body.evidenceRefs.slice(0, 100) : [],
    });
    return json({ ok: true, attestation });
  }
  if (request.method !== "GET") return json({ ok: false, error: "method_not_allowed" }, 405);

  const [attestations, gate, health, scheduler, providers] = await Promise.all([
    db.select<Array<Record<string, unknown>>>("release_attestations_v6?select=*&order=assessed_at.desc&limit=10"),
    db.select<Array<Record<string, unknown>>>("v_production_gate_v6?select=*&limit=1"),
    db.select<Array<Record<string, unknown>>>("v_operating_health_v6?select=*&limit=1"),
    db.select<Array<Record<string, unknown>>>("v_scheduler_readiness_v6?select=*&limit=1"),
    db.select<Array<Record<string, unknown>>>("v_provider_readiness_v6?select=provider_key,runtime_state,authorized,runtime_ready,operational&order=provider_key.asc"),
  ]);
  return json({
    ok: true,
    observedAt: new Date().toISOString(),
    latest: attestations.at(0) ?? null,
    recentAttestations: attestations,
    productionGate: gate.at(0) ?? null,
    operatingHealth: health.at(0) ?? null,
    scheduler: scheduler.at(0) ?? null,
    providers,
  });
}

async function route(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  try {
    if (url.pathname === "/healthz" && request.method === "GET") {
      return json({ ok: true, service: "creixement-runtime", platform: "cloudflare-workers", version: env.CREIXEMENT_RUNTIME_VERSION ?? "0.6.2", cloudflareVersionId: env.CF_VERSION_METADATA?.id ?? null });
    }
    if (url.pathname === "/api/tick") {
      if (request.method !== "GET" && request.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405);
      const runtime = buildRuntimeEnv(env);
      if (!bearer(request, runtime.cronSecret)) return json({ ok: false, error: "unauthorized" }, 401);
      const result = await executeTick(env, "http");
      return json(result, result.ok ? 200 : 207);
    }
    if (url.pathname === "/api/health" && request.method === "GET") {
      const runtime = buildRuntimeEnv(env);
      if (!bearer(request, runtime.apiToken)) return json({ ok: false, error: "unauthorized" }, 401);
      return await handleHealth(env);
    }
    if (url.pathname === "/api/readiness" && request.method === "GET") {
      const runtime = buildRuntimeEnv(env);
      if (!bearer(request, runtime.apiToken)) return json({ ok: false, error: "unauthorized" }, 401);
      return await handleReadiness(env);
    }
    if (url.pathname === "/api/owner-decisions") return await handleOwnerDecisions(request, env);
    if (url.pathname === "/api/release-status") return await handleReleaseStatus(request, env);
    return json({ ok: false, error: "not_found" }, 404);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(JSON.stringify({ event: "creixement.runtime.http_error", path: url.pathname, message: message.slice(0, 1000) }));
    return json({ ok: false, error: "runtime_unavailable", detail: message.slice(0, 1000) }, 503);
  }
}

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    return route(request, env);
  },
  async scheduled(controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil((async () => {
      try {
        const result = await executeTick(env, `cloudflare-cron:${controller.cron}`);
        if (!result.ok) throw new Error("runtime tick completed in degraded state");
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error(JSON.stringify({ event: "creixement.runtime.cron_failure", cron: controller.cron, message: message.slice(0, 1000), scheduledTime: controller.scheduledTime }));
        throw error;
      }
    })());
  },
};
