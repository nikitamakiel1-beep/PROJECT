import type { RuntimeEnv } from "../../creixement-runtime/src/env.js";
import { SupabaseHttp } from "../../creixement-runtime/src/supabase.js";

export interface DiagnosticEnv {
  SUPABASE_URL?: string;
  SUPABASE_SERVICE_ROLE_KEY?: string;
  CREIXEMENT_DB_RELAY_URL?: string;
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
  if (/\b401\b/.test(message)) return "unauthorized";
  if (/\b403\b/.test(message)) return "forbidden";
  if (/\b404\b/.test(message)) return "contract_missing";
  if (/Missing required|configuration/i.test(message)) return "configuration_missing";
  return "unavailable";
}

function runtimeEnv(env: DiagnosticEnv): RuntimeEnv | null {
  if (!present(env.SUPABASE_URL) || !present(env.SUPABASE_SERVICE_ROLE_KEY)) return null;
  const relayUrl = env.CREIXEMENT_DB_RELAY_URL?.trim().replace(/\/$/, "") || null;
  if (relayUrl && !relayUrl.startsWith("https://")) return null;
  const timeoutRaw = Number(env.CREIXEMENT_DB_TIMEOUT_MS ?? "8000");
  const requestTimeoutMs = Number.isInteger(timeoutRaw) && timeoutRaw >= 1000 && timeoutRaw <= 30000 ? timeoutRaw : 8000;
  return {
    supabaseUrl: env.SUPABASE_URL!.trim().replace(/\/$/, ""),
    supabaseServiceRoleKey: env.SUPABASE_SERVICE_ROLE_KEY!.trim(),
    databaseRelayUrl: relayUrl,
    cronSecret: env.CRON_SECRET?.trim() || "__diagnostic_http_not_required__",
    apiToken: env.CREIXEMENT_API_TOKEN?.trim() || "__diagnostic_http_not_required__",
    runtimeId: env.CREIXEMENT_RUNTIME_ID?.trim() || "kairon-cloudflare-v10",
    runtimeVersion: env.CREIXEMENT_RUNTIME_VERSION?.trim() || "1.0.0",
    commitSha: env.CREIXEMENT_COMMIT_SHA?.trim() || null,
    environment: env.CREIXEMENT_ENVIRONMENT?.trim() || "production",
    requestTimeoutMs,
  };
}

export async function diagnoseRuntime(env: DiagnosticEnv): Promise<Record<string, unknown>> {
  const relayConfigured = present(env.CREIXEMENT_DB_RELAY_URL);
  const schedulerBindings = relayConfigured
    ? [env.CREIXEMENT_DB_RELAY_URL, env.SUPABASE_SERVICE_ROLE_KEY]
    : [env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY];
  const schedulerBindingsPresent = schedulerBindings.filter(present).length;
  const httpControlBindings = [env.CRON_SECRET, env.CREIXEMENT_API_TOKEN];
  const httpControlBindingsPresent = httpControlBindings.filter(present).length;
  const ownerBindingConfigured = present(env.CREIXEMENT_OWNER_TOKEN);
  const runtime = runtimeEnv(env);
  const dataPlane = runtime?.databaseRelayUrl ? "managed-relay" : "direct-supabase";
  const now = Date.now();

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
  const configuredVersion = env.CREIXEMENT_RUNTIME_VERSION?.trim() || "1.0.0";
  const heartbeatCommitMatches = configuredCommit && heartbeat?.commit_sha ? configuredCommit === heartbeat.commit_sha : null;
  const heartbeatVersionMatches = heartbeat?.version ? configuredVersion === heartbeat.version : null;
  const schedulerConfigured = schedulerBindingsPresent === 2 && (!relayConfigured || Boolean(runtime?.databaseRelayUrl));
  const httpControlConfigured = httpControlBindingsPresent === 2;
  const operational = schedulerConfigured && databaseReachable && heartbeatFresh;

  return {
    ok: true,
    service: "creixement-runtime",
    operator: "Kairon",
    platform: "cloudflare-workers",
    diagnosticVersion: 3,
    observedAt: new Date(now).toISOString(),
    operational,
    configuration: {
      schedulerBindingsConfigured: schedulerConfigured,
      schedulerBindingsPresent,
      schedulerBindingsRequired: 2,
      dataPlane,
      managedRelayConfigured: relayConfigured,
      httpControlBindingsConfigured: httpControlConfigured,
      httpControlBindingsPresent,
      httpControlBindingsRequired: 2,
      ownerBindingConfigured,
      commitAttested: Boolean(configuredCommit),
      branchConfigured: present(env.CREIXEMENT_BRANCH),
      runtimeId: env.CREIXEMENT_RUNTIME_ID?.trim() || "kairon-cloudflare-v10",
      runtimeVersion: configuredVersion,
      branch: env.CREIXEMENT_BRANCH?.trim() || "unattested",
      commit: configuredCommit ? configuredCommit.slice(0, 12) : "unattested",
      cloudflareVersionId: env.CF_VERSION_METADATA?.id ?? null,
      cloudflareVersionTimestamp: env.CF_VERSION_METADATA?.timestamp ?? null,
    },
    database: { reachable: databaseReachable, state: databaseState, transport: dataPlane },
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
