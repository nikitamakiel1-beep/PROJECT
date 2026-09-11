export interface RuntimeEnv {
  supabaseUrl: string;
  supabaseServiceRoleKey: string;
  cronSecret: string;
  apiToken: string;
  runtimeId: string;
  runtimeVersion: string;
  commitSha: string | null;
  environment: string;
  requestTimeoutMs: number;
}

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

function boundedInteger(name: string, fallback: number, min: number, max: number): number {
  const raw = process.env[name]?.trim();
  if (!raw) return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value) || value < min || value > max) {
    throw new Error(`${name} must be an integer between ${min} and ${max}`);
  }
  return value;
}

export function loadOwnerToken(): string {
  return required("CREIXEMENT_OWNER_TOKEN");
}

export function loadEnv(): RuntimeEnv {
  const supabaseUrl = required("SUPABASE_URL").replace(/\/$/, "");
  if (!/^https:\/\//.test(supabaseUrl)) throw new Error("SUPABASE_URL must use HTTPS");
  return {
    supabaseUrl,
    supabaseServiceRoleKey: required("SUPABASE_SERVICE_ROLE_KEY"),
    cronSecret: required("CRON_SECRET"),
    apiToken: required("CREIXEMENT_API_TOKEN"),
    runtimeId: process.env.CREIXEMENT_RUNTIME_ID?.trim() || "creixement-runtime-v6",
    runtimeVersion: process.env.CREIXEMENT_RUNTIME_VERSION?.trim() || "0.6.2",
    commitSha: process.env.VERCEL_GIT_COMMIT_SHA?.trim() || process.env.CREIXEMENT_COMMIT_SHA?.trim() || null,
    environment: process.env.VERCEL_ENV?.trim() || process.env.NODE_ENV?.trim() || "production",
    requestTimeoutMs: boundedInteger("CREIXEMENT_DB_TIMEOUT_MS", 8000, 1000, 30000),
  };
}
