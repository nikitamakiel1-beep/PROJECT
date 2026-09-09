export interface RuntimeEnv {
  supabaseUrl: string;
  supabaseServiceRoleKey: string;
  cronSecret: string;
  apiToken: string;
  runtimeId: string;
  runtimeVersion: string;
  commitSha: string | null;
  environment: string;
}

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

export function loadEnv(): RuntimeEnv {
  const supabaseUrl = required("SUPABASE_URL").replace(/\/$/, "");
  if (!/^https:\/\//.test(supabaseUrl)) throw new Error("SUPABASE_URL must use HTTPS");
  return {
    supabaseUrl,
    supabaseServiceRoleKey: required("SUPABASE_SERVICE_ROLE_KEY"),
    cronSecret: required("CRON_SECRET"),
    apiToken: required("CREIXEMENT_API_TOKEN"),
    runtimeId: process.env.CREIXEMENT_RUNTIME_ID?.trim() || "vercel-runtime-v5",
    runtimeVersion: process.env.CREIXEMENT_RUNTIME_VERSION?.trim() || "0.5.0",
    commitSha: process.env.VERCEL_GIT_COMMIT_SHA?.trim() || process.env.CREIXEMENT_COMMIT_SHA?.trim() || null,
    environment: process.env.VERCEL_ENV?.trim() || process.env.NODE_ENV?.trim() || "production",
  };
}
