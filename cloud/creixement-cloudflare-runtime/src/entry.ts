import runtimeWorker from "./index.js";
import { diagnoseRuntime, type DiagnosticEnv } from "./diagnostics.js";

type RuntimeEnv = Parameters<typeof runtimeWorker.fetch>[1] & DiagnosticEnv & {
  CREIXEMENT_RUNTIME_ID?: string;
  CREIXEMENT_RUNTIME_VERSION?: string;
  CREIXEMENT_COMMIT_SHA?: string;
  CREIXEMENT_BRANCH?: string;
  CREIXEMENT_ENVIRONMENT?: string;
};

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[char] ?? char);
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

function statusPage(env: RuntimeEnv): Response {
  const runtimeId = escapeHtml(env.CREIXEMENT_RUNTIME_ID ?? "kairon-cloudflare-v9");
  const version = escapeHtml(env.CREIXEMENT_RUNTIME_VERSION ?? "0.9.1");
  const branch = escapeHtml(env.CREIXEMENT_BRANCH ?? "unknown");
  const commit = escapeHtml(env.CREIXEMENT_COMMIT_SHA ?? "unattested");
  const environment = escapeHtml(env.CREIXEMENT_ENVIRONMENT ?? "production");
  const shortCommit = commit === "unattested" ? commit : commit.slice(0, 12);
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><meta name="color-scheme" content="light"/><title>Kairon Runtime · Creixement</title>
<style>:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#22231f;background:#f5f1e8}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 15% 0%,#fffdf8 0,#f5f1e8 44%,#efe9de 100%)}main{max-width:980px;margin:0 auto;padding:56px 22px 80px}.eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#73756c;font-weight:700}.hero{display:flex;justify-content:space-between;gap:28px;align-items:flex-end;padding-bottom:30px;border-bottom:1px solid #d8d2c6}.hero h1{font:600 clamp(40px,8vw,82px)/.95 Georgia,"Times New Roman",serif;letter-spacing:-.055em;margin:10px 0 16px}.hero p{max-width:610px;color:#64665e;font-size:16px;line-height:1.6}.live{display:inline-flex;align-items:center;gap:8px;border:1px solid #b7c4b4;background:#edf3eb;color:#314b36;border-radius:999px;padding:9px 13px;font-size:12px;font-weight:700}.dot{width:8px;height:8px;border-radius:50%;background:#3d7448;box-shadow:0 0 0 5px rgba(61,116,72,.09)}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:22px 0}.card{background:rgba(255,253,248,.82);border:1px solid #d8d2c6;border-radius:16px;padding:17px;min-height:112px}.card span{display:block;color:#77786f;font-size:11px;text-transform:uppercase;letter-spacing:.08em}.card strong{display:block;font-size:17px;margin-top:12px;word-break:break-word}.panel{border:1px solid #d8d2c6;background:#fffdf8;border-radius:18px;padding:24px;margin-top:12px}.panel h2{font-size:16px;margin:0 0 8px}.panel p{color:#66675f;line-height:1.55;margin:0 0 18px}.checks{display:grid;gap:9px}.check{display:flex;justify-content:space-between;gap:18px;border-top:1px solid #ebe6dc;padding-top:11px;font-size:13px}.check b{font-weight:600}.truth{color:#6e7067}.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}a.button{display:inline-flex;text-decoration:none;border:1px solid #262822;border-radius:10px;padding:10px 13px;color:#fff;background:#262822;font-size:13px;font-weight:650}a.secondary{color:#262822;background:transparent;border-color:#bbb6aa}code{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px}@media(max-width:760px){main{padding-top:34px}.hero{display:block}.live{margin-top:18px}.grid{grid-template-columns:1fr 1fr}}@media(max-width:450px){.grid{grid-template-columns:1fr}.hero h1{font-size:56px}}</style></head>
<body><main><div class="hero"><div><div class="eyebrow">Creixement Control Plane · Runtime</div><h1>Kairon</h1><p>This endpoint is the Cloudflare execution engine. The operator cockpit lives on the dedicated Lovable/GitHub UI branch. Configuration is not execution; deployment is not a verified external outcome.</p></div><div class="live"><span class="dot"></span>Worker responding</div></div>
<div class="grid"><div class="card"><span>Environment</span><strong>${environment}</strong></div><div class="card"><span>Runtime</span><strong>${runtimeId}</strong></div><div class="card"><span>Version</span><strong>${version}</strong></div><div class="card"><span>Commit</span><strong><code>${shortCommit}</code></strong></div></div>
<section class="panel"><h2>Runtime visibility</h2><p>Use the diagnostics endpoint to distinguish an HTTP deployment from an actually connected, scheduled runtime. It exposes no secret values.</p><div class="checks"><div class="check"><b>Branch</b><span class="truth"><code>${branch}</code></span></div><div class="check"><b>Scheduler target</b><span class="truth">every 5 minutes</span></div><div class="check"><b>Liveness</b><span class="truth"><code>/healthz</code></span></div><div class="check"><b>Safe diagnostics</b><span class="truth"><code>/diagz</code></span></div><div class="check"><b>Operator APIs</b><span class="truth">bearer-protected</span></div></div><div class="actions"><a class="button" href="/diagz">Open diagnostics</a><a class="button secondary" href="/healthz">Open liveness</a></div></section>
</main></body></html>`;
  return new Response(html,{status:200,headers:{"content-type":"text/html; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff","content-security-policy":"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"}});
}

export default {
  async fetch(request: Request, env: RuntimeEnv): Promise<Response> {
    const url = new URL(request.url);
    if ((url.pathname === "/" || url.pathname === "/status") && request.method === "GET") return statusPage(env);
    if (url.pathname === "/diagz" && request.method === "GET") return json(await diagnoseRuntime(env));
    return runtimeWorker.fetch(request, env);
  },
  scheduled(controller: ScheduledController, env: RuntimeEnv, ctx: ExecutionContext): Promise<void> {
    return runtimeWorker.scheduled(controller, env, ctx);
  },
};
