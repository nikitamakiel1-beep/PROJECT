export interface RuntimeEnv {
  supabaseUrl: string;
  supabaseServiceRoleKey: string;
  cronSecret: string;
  apiToken: string;
  runtimeId: string;
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
    runtimeId: process.env.CREIXEMENT_RUNTIME_ID?.trim() || "vercel-runtime-v4",
  };
}
