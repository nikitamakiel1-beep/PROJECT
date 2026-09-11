import type { RuntimeEnv } from "./env.js";

export class SupabaseHttp {
  constructor(private readonly env: RuntimeEnv) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("apikey", this.env.supabaseServiceRoleKey);
    headers.set("Authorization", `Bearer ${this.env.supabaseServiceRoleKey}`);
    headers.set("Content-Type", "application/json");
    if (!headers.has("Prefer")) headers.set("Prefer", "return=representation");

    const timeout = AbortSignal.timeout(this.env.requestTimeoutMs);
    const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;

    let response: Response;
    try {
      response = await fetch(`${this.env.supabaseUrl}/rest/v1/${path}`, { ...init, headers, signal });
    } catch (error) {
      if (signal.aborted) {
        throw new Error(`Supabase request timed out after ${this.env.requestTimeoutMs}ms: ${path.slice(0, 200)}`);
      }
      throw error;
    }

    const text = await response.text();
    if (!response.ok) throw new Error(`Supabase ${response.status}: ${text.slice(0, 1000)}`);
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
