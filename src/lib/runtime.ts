export type RuntimeProbe = {
  configured: boolean;
  reachable: boolean;
  status: 'unconfigured' | 'healthy' | 'degraded' | 'unreachable';
  origin: string | null;
  observedAt: string;
  payload: Record<string, unknown> | null;
  error: string | null;
};

const rawOrigin = String(import.meta.env.VITE_KAIRON_RUNTIME_URL ?? '').trim().replace(/\/$/, '');

export async function probeRuntime(timeoutMs = 4500): Promise<RuntimeProbe> {
  const observedAt = new Date().toISOString();
  if (!rawOrigin) {
    return { configured: false, reachable: false, status: 'unconfigured', origin: null, observedAt, payload: null, error: null };
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${rawOrigin}/diagz`, {
      method: 'GET',
      headers: { accept: 'application/json' },
      signal: controller.signal,
      cache: 'no-store',
    });
    const body = (await response.json().catch(() => null)) as Record<string, unknown> | null;
    if (!response.ok) {
      return {
        configured: true,
        reachable: true,
        status: 'degraded',
        origin: rawOrigin,
        observedAt,
        payload: body,
        error: `Runtime returned HTTP ${response.status}`,
      };
    }
    const healthText = String(body?.status ?? body?.state ?? body?.health ?? '').toLowerCase();
    const healthy = healthText === 'healthy' || healthText === 'ok' || body?.ok === true;
    return {
      configured: true,
      reachable: true,
      status: healthy ? 'healthy' : 'degraded',
      origin: rawOrigin,
      observedAt,
      payload: body,
      error: null,
    };
  } catch (error) {
    return {
      configured: true,
      reachable: false,
      status: 'unreachable',
      origin: rawOrigin,
      observedAt,
      payload: null,
      error: error instanceof Error ? error.message : String(error),
    };
  } finally {
    window.clearTimeout(timer);
  }
}
