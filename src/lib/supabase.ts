import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = String(import.meta.env.VITE_SUPABASE_URL ?? '').trim();
const key = String(import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? '').trim();

export const supabaseConfigured = Boolean(url && key && !url.includes('<project-ref>') && !key.startsWith('<'));

let client: SupabaseClient | null = null;
if (supabaseConfigured) {
  client = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { 'x-creixement-ui': 'command-center-v9.2' } },
  });
}

export function getSupabase(): SupabaseClient | null {
  return client;
}

export async function readRows<T extends Record<string, unknown>>(
  relation: string,
  limit = 100,
): Promise<T[]> {
  if (!client) throw new Error('Supabase browser connection is not configured.');
  const { data, error } = await client.from(relation).select('*').limit(limit);
  if (error) throw new Error(`${relation}: ${error.message}`);
  return (data ?? []) as T[];
}

export async function readOrderedRows<T extends Record<string, unknown>>(
  relation: string,
  orderColumn: string,
  limit = 100,
): Promise<T[]> {
  if (!client) throw new Error('Supabase browser connection is not configured.');
  const { data, error } = await client.from(relation).select('*').order(orderColumn, { ascending: false }).limit(limit);
  if (error) throw new Error(`${relation}: ${error.message}`);
  return (data ?? []) as T[];
}
