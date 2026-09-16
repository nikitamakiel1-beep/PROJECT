import { createHash } from "node:crypto";
import type { RuntimeEnv } from "../../creixement-runtime/src/env.js";
import { SupabaseHttp } from "../../creixement-runtime/src/supabase.js";

export interface DiagnosticEnv {
  SUPABASE_URL?: string;
  SUPABASE_SERVICE_ROLE_KEY?: string;
  CRON_SECRET?: string;
  CREIXEMENT_API_TOKEN?: string;
  CREIXEMENT_OWNER_TOKEN?: string;
  CREIXEMENT_RUNTIME_ID?: string;
  CREIXEMENT_RUNTIME_VERSION?: string;
  CREIXEMENT_COMMIT_SHA?: string;
  CREIXEMENT_BRANCH?: string;
  CREIXEMENT_ENVIRONMENT?: string;
  CREIXEMENT_DB_TIMEOUT_MS?: string;
  CF_VERSION_METADATA?: { id: string; tag?: string; timestamp?: string };
}

interface HeartbeatRow {
  runtime_id?: string;
  version?: string;
  commit_sha?: string | null;
  status?: string;
  last_seen_at?: string;
}

function present(value: string | undefined): boolean {
  return Boolean(value?.trim());
}

function classify(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (/timed out/i.test(message)) return "timeout";
  if (/Supabase 401/i.test(message)) return "unauthorized";
  if (/Supabase 403/i.test(message)) return "forbidden";
  if (/Supabase 404/i.test(message)) return "contract_missing";
  if (/Missing required/i.test(message)) return "configuration_missing";
  return "unavailable";
}

function runtimeEnv(env: DiagnosticEnv): RuntimeEnv | null {
  if (!present(env.SUPABASE_URL) || !present(env.SUPABASE_SERVICE_ROLE_KEY)) return null;
  const timeoutRaw = Number(env.CREIXEMENT_DB_TIMEOUT_MS ?? "8000");
  const requestTimeoutMs = Number.isInteger(timeoutRaw) && timeoutRaw >= 1000 && timeoutRaw <= 30000 ? timeoutRaw : 8000;
  return {
    supabaseUrl: env.SUPABASE_URL!.trim().replace(/\/$/, ""),
    supabaseServiceRoleKey: env.SUPABASE_SERVICE_ROLE_KEY!.trim(),
    cronSecret: env.CRON_SECRET?.trim() || "__diagnostic_http_not_required__",
    apiToken: env.CREIXEMENT_API_TOKEN?.trim() || "__diagnostic_http_not_required__",
    runtimeId: env.CREIXEMENT_RUNTIME_ID?.trim() || "kairon-cloudflare-v9",
    runtimeVersion: env.CREIXEMENT_RUNTIME_VERSION?.trim() || "0.9.1",
    commitSha: env.CREIXEMENT_COMMIT_SHA?.trim() || null,
    environment: env.CREIXEMENT_ENVIRONMENT?.trim() || "production",
    requestTimeoutMs,
  };
}

export async function diagnoseRuntime(env: DiagnosticEnv): Promise<Record<string, unknown>> {
  const schedulerBindings = [env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY];
  const schedulerBindingsPresent = schedulerBindings.filter(present).length;
  const httpControlBindings = [env.CRON_SECRET, env.CREIXEMENT_API_TOKEN];
  const httpControlBindingsPresent = httpControlBindings.filter(present).length;
  const ownerBindingConfigured = present(env.CREIXEMENT_OWNER_TOKEN);
  const runtime = runtimeEnv(env);
  const now = Date.now();
  // Bootstrap-only, one-way fingerprint used to bind the existing Cloudflare secret
  // to a server-side relay without exposing the raw secret. This field is removed
  // before any production merge.
  const bootstrapCredentialFingerprint = present(env.SUPABASE_SERVICE_ROLE_KEY)
    ? createHash("sha256").update(env.SUPABASE_SERVICE_ROLE_KEY!.trim()).digest("hex")
    : null;

  let databaseReachable = false;
  let databaseState = runtime ? "unchecked" : "configuration_missing";
  let heartbeat: HeartbeatRow | null = null;

  if (runtime) {
    try {
      const db = new SupabaseHttp(runtime);
      const runtimeId = encodeURIComponent(runtime.runtimeId);
      const rows = await db.select<HeartbeatRow[]>(
        `runtime_heartbeats_v5?select=runtime_id,version,commit_sha,status,last_seen_at&runtime_id=eq.${runtimeId}&order=last_seen_at.desc&limit=1`,
      );
      databaseReachable = true;
      databaseState = "reachable";
      heartbeat = rows.at(0) ?? null;
    } catch (error) {
      databaseState = classify(error);
    }
  }

  const lastSeenMs = heartbeat?.last_seen_at ? Date.parse(heartbeat.last_seen_at) : Number.NaN;
  const heartbeatAgeSeconds = Number.isFinite(lastSeenMs) ? Math.max(0, Math.round((now - lastSeenMs) / 1000)) : null;
  const heartbeatFresh = heartbeatAgeSeconds !== null && heartbeatAgeSeconds <= 15 * 60;
  const configuredCommit = env.CREIXEMENT_COMMIT_SHA?.trim() || null;
  const configuredVersion = env.CREIXEMENT_RUNTIME_VERSION?.trim() || "0.9.1";
  const heartbeatCommitMatches = configuredCommit && heartbeat?.commit_sha ? configuredCommit === heartbeat.commit_sha : null;
  const heartbeatVersionMatches = heartbeat?.version ? configuredVersion === heartbeat.version : null;
  const schedulerConfigured = schedulerBindingsPresent === 2;
  const httpControlConfigured = httpControlBindingsPresent === 2;
  const operational = schedulerConfigured && databaseReachable && heartbeatFresh;

  return {
    ok: true,
    service: "creixement-runtime",
    operator: "Kairon",
    platform: "cloudflare-workers",
    diagnosticVersion: 2,
    observedAt: new Date(now).toISOString(),
    operational,
    configuration: {
      schedulerBindingsConfigured: schedulerConfigured,
      schedulerBindingsPresent,
      schedulerBindingsRequired: 2,
      httpControlBindingsConfigured: httpControlConfigured,
      httpControlBindingsPresent,
      httpControlBindingsRequired: 2,
      ownerBindingConfigured,
      commitAttested: Boolean(configuredCommit),
      branchConfigured: present(env.CREIXEMENT_BRANCH),
      runtimeId: env.CREIXEMENT_RUNTIME_ID?.trim() || "kairon-cloudflare-v9",
      runtimeVersion: configuredVersion,
      branch: env.CREIXEMENT_BRANCH?.trim() || "unattested",
      commit: configuredCommit ? configuredCommit.slice(0, 12) : "unattested",
      cloudflareVersionId: env.CF_VERSION_METADATA?.id ?? null,
      cloudflareVersionTimestamp: env.CF_VERSION_METADATA?.timestamp ?? null,
      bootstrapCredentialFingerprint,
    },
    database: { reachable: databaseReachable, state: databaseState },
    scheduler: {
      expectedCron: "*/5 * * * *",
      heartbeatFound: Boolean(heartbeat),
      heartbeatFresh,
      heartbeatAgeSeconds,
      inferredActive: heartbeatFresh,
    },
    heartbeat: heartbeat ? {
      status: heartbeat.status ?? null,
      version: heartbeat.version ?? null,
      commit: heartbeat.commit_sha ? heartbeat.commit_sha.slice(0, 12) : null,
      lastSeenAt: heartbeat.last_seen_at ?? null,
      versionMatches: heartbeatVersionMatches,
      commitMatches: heartbeatCommitMatches,
    } : null,
    truth: {
      workerResponding: true,
      schedulerConfigurationVerified: schedulerConfigured,
      databaseReachabilityVerified: databaseReachable,
      schedulerExecutionVerified: heartbeatFresh,
      exactCommitVerified: heartbeatCommitMatches === true,
      httpControlReady: httpControlConfigured,
      ownerControlReady: ownerBindingConfigured,
    },
  };
}
