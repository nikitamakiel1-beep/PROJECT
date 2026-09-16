import type { RuntimeEnv } from "./env.js";

export function supabaseAuthHeaders(apiKey: string): Record<string, string> {
  const headers: Record<string, string> = { apikey: apiKey };
  // Modern Supabase secret keys (sb_secret_...) are API keys, not JWTs.
  // Sending them as Authorization: Bearer can be rejected as Invalid JWT.
  // Legacy service_role JWTs still require/accept the bearer header.
  if (!apiKey.startsWith("sb_secret_")) {
    headers.Authorization = `Bearer ${apiKey}`;
  }
  return headers;
}

function normalizedRelayUrl(env: RuntimeEnv): string | null {
  const explicit = env.databaseRelayUrl?.trim().replace(/\/$/, "") || null;
  if (explicit) return explicit;
  // Cloudflare's outer entry wrapper also rewrites SUPABASE_URL to the relay before
  // delegating bearer-protected HTTP endpoints to the legacy worker. Recognize only
  // the exact managed relay path so ordinary Supabase URLs can never be mistaken for it.
  try {
    const candidate = new URL(env.supabaseUrl);
    if (candidate.protocol === "https:" && candidate.pathname.replace(/\/$/, "").endsWith("/api/runtime-db")) {
      return env.supabaseUrl.trim().replace(/\/$/, "");
    }
  } catch {
    // Environment validation owns malformed URL errors. This helper remains pure/fail-closed.
  }
  return null;
}

export function databaseAuthHeaders(env: RuntimeEnv): Record<string, string> {
  if (normalizedRelayUrl(env)) {
    return {
      "x-creixement-runtime-token": env.supabaseServiceRoleKey,
      "x-creixement-runtime-id": env.runtimeId,
    };
  }
  return supabaseAuthHeaders(env.supabaseServiceRoleKey);
}

export function databaseRequestUrl(env: RuntimeEnv, path: string): string {
  const relay = normalizedRelayUrl(env);
  if (!relay) return `${env.supabaseUrl}/rest/v1/${path}`;

  const queryStart = path.indexOf("?");
  const resource = queryStart >= 0 ? path.slice(0, queryStart) : path;
  const query = queryStart >= 0 ? path.slice(queryStart) : "";
  return `${relay}/${resource}${query}`;
}

export class SupabaseHttp {
  constructor(private readonly env: RuntimeEnv) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    for (const [name, value] of Object.entries(databaseAuthHeaders(this.env))) {
      headers.set(name, value);
    }
    headers.set("Content-Type", "application/json");
    if (!headers.has("Prefer")) headers.set("Prefer", "return=representation");

    const timeout = AbortSignal.timeout(this.env.requestTimeoutMs);
    const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
    const target = databaseRequestUrl(this.env, path);

    let response: Response;
    try {
      response = await fetch(target, { ...init, headers, signal });
    } catch (error) {
      if (signal.aborted) {
        throw new Error(`Database request timed out after ${this.env.requestTimeoutMs}ms: ${path.slice(0, 200)}`);
      }
      throw error;
    }

    const text = await response.text();
    if (!response.ok) {
      const transport = normalizedRelayUrl(this.env) ? "Managed relay" : "Supabase";
      throw new Error(`${transport} ${response.status}: ${text.slice(0, 1000)}`);
    }
    if (!text) return undefined as T;
    return JSON.parse(text) as T;
  }

  select<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "GET" });
  }

  insert<T>(table: string, body: unknown, onConflict?: string): Promise<T> {
    const conflict = onConflict ? `?on_conflict=${encodeURIComponent(onConflict)}` : "";
    const headers: Record<string, string> = {};
    if (onConflict) headers.Prefer = "resolution=ignore-duplicates,return=representation";
    return this.request<T>(`${table}${conflict}`, { method: "POST", headers, body: JSON.stringify(body) });
  }

  patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
  }

  rpc<T>(functionName: string, body: unknown): Promise<T> {
    return this.request<T>(`rpc/${functionName}`, { method: "POST", body: JSON.stringify(body) });
  }
}
