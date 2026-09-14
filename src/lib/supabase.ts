import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const key = (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || import.meta.env.VITE_SUPABASE_ANON_KEY) as string | undefined;

export const supabaseConfigured = Boolean(url && key);
export const supabase = supabaseConfigured
  ? createClient(url!, key!, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null;

export async function readRows<T = Record<string, unknown>>(relation: string, limit = 100): Promise<T[]> {
  if (!supabase) return [];
  const { data, error } = await supabase.from(relation).select('*').limit(limit);
  if (error) throw error;
  return (data ?? []) as T[];
}
