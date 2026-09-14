import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, ArrowLeft, CheckCircle2, Cloud, Database, GitCommitHorizontal, RefreshCw, Timer, XCircle } from "lucide-react";
import { readRows, supabaseConfigured } from "../lib/supabase";

export const Route = createFileRoute("/runtime-diagnostics")({ component: RuntimeDiagnostics });

type Row = Record<string, unknown>;
type Probe = {
  operational?: boolean;
  observedAt?: string;
  configuration?: {
    runtimeBindingsConfigured?: boolean;
    runtimeBindingsPresent?: number;
    runtimeBindingsRequired?: number;
    ownerBindingConfigured?: boolean;
    commitAttested?: boolean;
    runtimeId?: string;
    runtimeVersion?: string;
    branch?: string;
    commit?: string;
    cloudflareVersionId?: string | null;
  };
  database?: { reachable?: boolean; state?: string };
  scheduler?: { expectedCron?: string; heartbeatFound?: boolean; heartbeatFresh?: boolean; heartbeatAgeSeconds?: number | null; inferredActive?: boolean };
  heartbeat?: { status?: string | null; version?: string | null; commit?: string | null; lastSeenAt?: string | null; versionMatches?: boolean | null; commitMatches?: boolean | null } | null;
  truth?: { workerResponding?: boolean; databaseReachabilityVerified?: boolean; schedulerExecutionVerified?: boolean; exactCommitVerified?: boolean };
};

type LoadState<T> = { data: T; loading: boolean; error: string };

function useRelation(relation: string, limit = 20): LoadState<Row[]> {
  const [state, setState] = useState<LoadState<Row[]>>({ data: [], loading: true, error: "" });
  useEffect(() => {
    let active = true;
    setState({ data: [], loading: true, error: "" });
    readRows<Row>(relation, limit)
      .then((data) => active && setState({ data, loading: false, error: "" }))
      .catch((error: unknown) => active && setState({ data: [], loading: false, error: error instanceof Error ? error.message : String(error) }));
    return () => { active = false; };
  }, [relation, limit]);
  return state;
}

function useWorkerProbe(): LoadState<Probe | null> & { url: string; refresh: () => void } {
  const url = String(import.meta.env.VITE_KAIRON_RUNTIME_URL ?? "").trim().replace(/\/$/, "");
  const [nonce, setNonce] = useState(0);
  const [state, setState] = useState<LoadState<Probe | null>>({ data: null, loading: Boolean(url), error: "" });
  useEffect(() => {
    if (!url) { setState({ data: null, loading: false, error: "" }); return; }
    const controller = new AbortController();
    setState({ data: null, loading: true, error: "" });
    const timeout = setTimeout(() => controller.abort(), 8000);
    fetch(`${url}/diagz`, { headers: { accept: "application/json" }, signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Worker diagnostics returned HTTP ${response.status}`);
        return await response.json() as Probe;
      })
      .then((data) => setState({ data, loading: false, error: "" }))
      .catch((error: unknown) => setState({ data: null, loading: false, error: error instanceof Error ? error.message : String(error) }))
      .finally(() => clearTimeout(timeout));
    return () => { clearTimeout(timeout); controller.abort(); };
  }, [url, nonce]);
  return { ...state, url, refresh: () => setNonce((n) => n + 1) };
}

function truth(value: boolean | null | undefined): "verified" | "blocked" | "unknown" {
  return value === true ? "verified" : value === false ? "blocked" : "unknown";
}

function Status({ value }: { value: "verified" | "blocked" | "unknown" }) {
  const Icon = value === "verified" ? CheckCircle2 : value === "blocked" ? XCircle : AlertTriangle;
  return <span className={`rd-status rd-${value}`}><Icon size={14}/>{value === "verified" ? "Verified" : value === "blocked" ? "Not verified" : "Unknown"}</span>;
}

function Card({ icon, label, value, state, detail }: { icon: React.ReactNode; label: string; value: string; state: "verified" | "blocked" | "unknown"; detail?: string }) {
  return <article className="rd-card"><div className="rd-card-head"><span className="rd-icon">{icon}</span><Status value={state}/></div><small>{label}</small><strong>{value}</strong>{detail && <p>{detail}</p>}</article>;
}

function ageLabel(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "No heartbeat";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

function RuntimeDiagnostics() {
  const probe = useWorkerProbe();
  const heartbeats = useRelation("runtime_heartbeats_v5", 20);
  const runtime = useRelation("v_runtime_readiness_v5", 1);
  const gate = useRelation("v_production_gate_v6", 1);
  const scheduler = useRelation("v_scheduler_readiness_v6", 1);
  const court = useRelation("v_conway_court_status_v9", 1);
  const latestHeartbeat = heartbeats.data[0] ?? null;
  const p = probe.data;

  const databaseReachable = p?.database?.reachable ?? (supabaseConfigured && !heartbeats.error);
  const heartbeatFound = p?.scheduler?.heartbeatFound ?? Boolean(latestHeartbeat);
  const heartbeatFresh = p?.scheduler?.heartbeatFresh ?? false;
  const schedulerVerified = p?.truth?.schedulerExecutionVerified ?? false;
  const commitVerified = p?.truth?.exactCommitVerified ?? false;
  const workerResponding = p?.truth?.workerResponding ?? false;
  const buildIdentity = p?.configuration?.commit ?? (latestHeartbeat?.commit_sha ? String(latestHeartbeat.commit_sha).slice(0,12) : "Unverified");
  const version = p?.configuration?.runtimeVersion ?? (latestHeartbeat?.version ? String(latestHeartbeat.version) : "0.9.1 target");

  const blockerList = useMemo(() => {
    const blockers: string[] = [];
    if (!probe.url) blockers.push("VITE_KAIRON_RUNTIME_URL is not configured in the UI environment, so direct Worker diagnostics cannot run.");
    if (probe.error) blockers.push(`Direct Worker probe failed: ${probe.error}`);
    if (p && p.configuration?.runtimeBindingsConfigured === false) blockers.push("One or more required Cloudflare runtime bindings/secrets are missing.");
    if (p && p.database?.reachable === false) blockers.push(`Cloudflare cannot reach/authenticate Supabase (${p.database.state ?? "unknown"}).`);
    if (!heartbeatFound) blockers.push("No runtime heartbeat is recorded in Supabase; scheduled execution is not proven.");
    else if (!heartbeatFresh) blockers.push("The latest runtime heartbeat is stale; the five-minute scheduler is not currently proven.");
    if (heartbeatFound && !commitVerified) blockers.push("A heartbeat exists but the exact deployed Git commit is not verified against runtime identity.");
    if (scheduler.error) blockers.push(`Scheduler readiness view unavailable to this UI session: ${scheduler.error}`);
    return blockers;
  }, [probe.url, probe.error, p, heartbeatFound, heartbeatFresh, commitVerified, scheduler.error]);

  return <div className="rd-page">
    <style>{`
      .rd-page{min-height:100vh;background:#f5f1e8;color:#262822;padding:34px 20px 70px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.rd-wrap{max-width:1180px;margin:0 auto}.rd-back{display:inline-flex;gap:7px;align-items:center;color:#56594f;text-decoration:none;font-size:13px;margin-bottom:28px}.rd-eyebrow{font-size:11px;letter-spacing:.18em;font-weight:800;color:#77786f}.rd-title{font:600 clamp(38px,7vw,72px)/1 Georgia,"Times New Roman",serif;letter-spacing:-.045em;margin:9px 0 12px}.rd-lead{max-width:760px;color:#676960;line-height:1.65;margin:0}.rd-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}.rd-button{border:1px solid #292b25;background:#292b25;color:white;border-radius:10px;padding:10px 13px;font-weight:700;font-size:13px;display:inline-flex;align-items:center;gap:7px;cursor:pointer}.rd-button.secondary{background:transparent;color:#292b25;border-color:#bbb6aa;text-decoration:none}.rd-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:28px 0}.rd-card,.rd-panel{background:#fffdf8;border:1px solid #d9d3c7;border-radius:17px}.rd-card{padding:17px;min-height:160px}.rd-card-head{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:17px}.rd-icon{width:34px;height:34px;border-radius:10px;background:#eeeadf;display:grid;place-items:center}.rd-card small{display:block;text-transform:uppercase;letter-spacing:.08em;color:#787a71;font-size:10px}.rd-card strong{display:block;font-size:22px;letter-spacing:-.02em;margin:7px 0;word-break:break-word}.rd-card p{margin:0;color:#6a6c64;line-height:1.45;font-size:12px}.rd-status{display:inline-flex;align-items:center;gap:5px;border:1px solid;border-radius:999px;padding:5px 8px;font-size:10px;font-weight:800}.rd-verified{color:#31583a;background:#edf4ec;border-color:#bdd0bb}.rd-blocked{color:#7b3a31;background:#f9ece9;border-color:#e3c3bd}.rd-unknown{color:#6a5b32;background:#f6f1e1;border-color:#ddd0a9}.rd-cols{display:grid;grid-template-columns:1.1fr .9fr;gap:12px}.rd-panel{padding:20px}.rd-panel h2{font-size:16px;margin:0 0 15px}.rd-blocker{display:flex;gap:10px;padding:11px 0;border-top:1px solid #ece7dd;color:#62645c;font-size:13px;line-height:1.5}.rd-blocker:first-of-type{border-top:0}.rd-good{display:flex;align-items:center;gap:9px;color:#31583a;background:#edf4ec;border:1px solid #bdd0bb;border-radius:12px;padding:13px;font-size:13px}.rd-table{width:100%;border-collapse:collapse;font-size:12px}.rd-table td{padding:10px 6px;border-top:1px solid #ece7dd;vertical-align:top}.rd-table td:first-child{color:#77786f;width:42%}.rd-code{font-family:"SFMono-Regular",Consolas,monospace;font-size:11px;word-break:break-all}.rd-note{font-size:12px;color:#77786f;line-height:1.5;margin-top:12px}@media(max-width:900px){.rd-grid{grid-template-columns:1fr 1fr}.rd-cols{grid-template-columns:1fr}}@media(max-width:520px){.rd-grid{grid-template-columns:1fr}.rd-page{padding:24px 14px 50px}}
    `}</style>
    <div className="rd-wrap">
      <Link className="rd-back" to="/"><ArrowLeft size={15}/> Back to Kairon cockpit</Link>
      <div className="rd-eyebrow">CREIXEMENT / RUNTIME TRUTH</div>
      <h1 className="rd-title">Cloudflare diagnostics</h1>
      <p className="rd-lead">This page separates build configuration from executed runtime evidence. A green build does not count as an active autonomous runtime until Cloudflare can reach Supabase and a fresh scheduled heartbeat is recorded.</p>
      <div className="rd-actions"><button className="rd-button" onClick={probe.refresh}><RefreshCw size={15}/> Re-run Worker probe</button>{probe.url && <a className="rd-button secondary" href={`${probe.url}/diagz`} target="_blank" rel="noreferrer"><Cloud size={15}/> Open raw /diagz</a>}</div>

      <div className="rd-grid">
        <Card icon={<Cloud size={17}/>} label="Worker response" value={workerResponding ? "Responding" : probe.url ? "Unverified" : "URL not configured"} state={truth(workerResponding)} detail={probe.loading ? "Running safe diagnostic probe…" : probe.error || "HTTP liveness is not the same as scheduler execution."}/>
        <Card icon={<Database size={17}/>} label="Supabase path" value={databaseReachable ? "Reachable" : "Not verified"} state={truth(databaseReachable)} detail={p?.database?.state ? `Worker reports: ${p.database.state}` : heartbeats.error || "Validated independently from runtime execution."}/>
        <Card icon={<Timer size={17}/>} label="5-minute scheduler" value={schedulerVerified ? "Verified active" : heartbeatFound ? "Heartbeat stale/unmatched" : "No heartbeat"} state={truth(schedulerVerified)} detail={p?.scheduler ? `Latest heartbeat: ${ageLabel(p.scheduler.heartbeatAgeSeconds)}` : "No runtime_heartbeats_v5 evidence is visible."}/>
        <Card icon={<GitCommitHorizontal size={17}/>} label="Exact release" value={buildIdentity} state={truth(commitVerified)} detail={`Runtime ${version}. Exact SHA must match the production deployment heartbeat.`}/>
      </div>

      <div className="rd-cols">
        <section className="rd-panel"><h2>Current blockers</h2>{blockerList.length === 0 ? <div className="rd-good"><CheckCircle2 size={17}/>No runtime blockers detected by the available evidence.</div> : blockerList.map((blocker) => <div className="rd-blocker" key={blocker}><AlertTriangle size={16}/><span>{blocker}</span></div>)}</section>
        <section className="rd-panel"><h2>Evidence snapshot</h2><table className="rd-table"><tbody>
          <tr><td>Production target</td><td className="rd-code">production/creixement-kairon</td></tr>
          <tr><td>Expected runtime</td><td>0.9.1</td></tr>
          <tr><td>Expected cron</td><td className="rd-code">*/5 * * * *</td></tr>
          <tr><td>Latest heartbeat row</td><td>{latestHeartbeat ? "Present" : "Absent"}</td></tr>
          <tr><td>Runtime readiness view</td><td>{runtime.loading ? "Loading" : runtime.error ? "Unavailable" : runtime.data.length ? "Present" : "Empty"}</td></tr>
          <tr><td>Production gate view</td><td>{gate.loading ? "Loading" : gate.error ? "Unavailable" : gate.data.length ? "Present" : "Empty"}</td></tr>
          <tr><td>Scheduler readiness view</td><td>{scheduler.loading ? "Loading" : scheduler.error ? "Unavailable" : scheduler.data.length ? "Present" : "Empty"}</td></tr>
          <tr><td>Conway court status</td><td>{court.loading ? "Loading" : court.error ? "Unavailable" : court.data.length ? "Present" : "Empty"}</td></tr>
        </tbody></table><p className="rd-note">Browser access uses only publishable Supabase credentials. Service-role, cron, owner and API token values are never exposed here.</p></section>
      </div>
    </div>
  </div>;
}
