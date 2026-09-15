import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  BarChart3,
  BrainCircuit,
  Building2,
  CircleDollarSign,
  Database,
  Dna,
  FileCheck2,
  Gauge,
  Home,
  Layers3,
  Network,
  Radar,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TableProperties,
  Users,
  Workflow,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { readOrderedRows, readRows, supabaseConfigured } from './lib/supabase';
import { probeRuntime, type RuntimeProbe } from './lib/runtime';

type Row = Record<string, unknown>;
type Truth = 'verified' | 'configured' | 'pending' | 'blocked' | 'unavailable';
type Page = 'overview' | 'runtime' | 'business' | 'ecology' | 'tectum' | 'approvals' | 'system';

type RelationState = {
  rows: Row[];
  loading: boolean;
  error: string;
  refresh: () => Promise<void>;
};

const NAV: Array<{ page: Page; label: string; icon: typeof Home; group: string }> = [
  { page: 'overview', label: 'Overview', icon: Home, group: 'Global' },
  { page: 'runtime', label: 'Runtime Proof', icon: Gauge, group: 'Global' },
  { page: 'business', label: 'Business', icon: CircleDollarSign, group: 'Company' },
  { page: 'tectum', label: 'Tectum', icon: Building2, group: 'Company' },
  { page: 'ecology', label: 'Ecology V9', icon: Dna, group: 'Intelligence' },
  { page: 'approvals', label: 'Approvals & Audit', icon: ShieldCheck, group: 'Governance' },
  { page: 'system', label: 'System', icon: Network, group: 'Governance' },
];

const SERVICES = [
  { code: 'IVA', name: 'International Visibility Audit', price: 149, beta: 99, hours: 2.5, contribution: 144, automation: 70 },
  { code: 'CRM', name: 'CRM & Lead Tracker Setup', price: 299, beta: 199, hours: 4, contribution: 294, automation: 80 },
  { code: 'OSP', name: 'International Sales One-Pager', price: 249, beta: 169, hours: 3.5, contribution: 239, automation: 65 },
  { code: 'WAB', name: 'WhatsApp Business Setup', price: 129, beta: 89, hours: 1.5, contribution: 129, automation: 75 },
  { code: 'ISS', name: 'International Starter System', price: 599, beta: 449, hours: 8, contribution: 579, automation: 72 },
];

function text(value: unknown, fallback = '—'): string {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

function num(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function yes(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1';
}

function euro(value: unknown): string {
  return new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(num(value));
}

function shortTime(value: unknown): string {
  if (!value) return '—';
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function titleCase(value: string): string {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (match) => match.toUpperCase());
}

function useRelation(relation: string, limit = 100, orderColumn?: string): RelationState {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = orderColumn
        ? await readOrderedRows<Row>(relation, orderColumn, limit)
        : await readRows<Row>(relation, limit);
      setRows(result);
    } catch (err) {
      setRows([]);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [relation, limit, orderColumn]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { rows, loading, error, refresh };
}

function truthFromQuery(query: RelationState, hasVerifiedRecord = query.rows.length > 0): Truth {
  if (query.error) return 'unavailable';
  if (query.loading) return 'pending';
  return hasVerifiedRecord ? 'verified' : 'configured';
}

function TruthBadge({ state }: { state: Truth }) {
  const labels: Record<Truth, string> = {
    verified: 'Live verified',
    configured: 'Configured / no live evidence',
    pending: 'Checking',
    blocked: 'Blocked',
    unavailable: 'Unavailable',
  };
  return <span className={`truth truth-${state}`}>{labels[state]}</span>;
}

function Panel({ title, icon, actions, children }: { title: string; icon?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <div>{icon}<h3>{title}</h3></div>
        {actions}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function Metric({ label, value, detail, truth }: { label: string; value: ReactNode; detail?: string; truth: Truth }) {
  return (
    <div className="metric">
      <div className="metric-label"><span>{label}</span><TruthBadge state={truth} /></div>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty">
      <AlertTriangle size={18} />
      <div><b>{title}</b><p>{body}</p></div>
    </div>
  );
}

function DataTable({ state, empty = 'No verified rows.' }: { state: RelationState; empty?: string }) {
  if (state.loading) return <div className="loading"><RefreshCw className="spin" size={17} /> Loading live state…</div>;
  if (state.error) return <Empty title="Live query unavailable" body={state.error} />;
  if (!state.rows.length) return <Empty title="No live records" body={empty} />;
  const columns = Object.keys(state.rows[0]).slice(0, 9);
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((column) => <th key={column}>{titleCase(column)}</th>)}</tr></thead>
        <tbody>
          {state.rows.slice(0, 50).map((row, index) => (
            <tr key={String(row.id ?? row.key ?? index)}>
              {columns.map((column) => {
                const value = row[column];
                return <td key={column}>{typeof value === 'object' && value !== null ? JSON.stringify(value) : text(value)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PageHead({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1><p>{subtitle}</p></div>
      {action}
    </div>
  );
}

function useRuntimeProbe() {
  const [state, setState] = useState<RuntimeProbe>({
    configured: false,
    reachable: false,
    status: 'unconfigured',
    origin: null,
    observedAt: new Date().toISOString(),
    payload: null,
    error: null,
  });
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true);
    setState(await probeRuntime());
    setLoading(false);
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return { state, loading, refresh };
}

function Overview({ setPage }: { setPage: (page: Page) => void }) {
  const proof = useRelation('v_runtime_proof_summary_v9', 1);
  const gate = useRelation('v_production_gate_v6', 1);
  const ecology = useRelation('v_bioecology_dashboard_v9', 1);
  const connectors = useRelation('v_connector_health', 50);
  const approvals = useRelation('v_owner_decision_queue_v6', 50);
  const opportunities = useRelation('opportunities', 100);
  const revenue = useRelation('revenue_events', 100);
  const runtime = useRuntimeProbe();

  const p = proof.rows[0] ?? {};
  const g = gate.rows[0] ?? {};
  const e = ecology.rows[0] ?? {};
  const runtimeTruth: Truth = runtime.loading ? 'pending' : runtime.state.status === 'healthy' ? 'verified' : runtime.state.configured ? 'blocked' : 'configured';
  const operationalConnectors = connectors.rows.filter((row) => String(row.effective_health ?? row.state ?? '') === 'runtime_ready').length;
  const wonRevenue = revenue.rows.reduce((sum, row) => sum + (String(row.event_type ?? row.type ?? '').toLowerCase().includes('won') ? num(row.amount ?? row.value) : 0), 0);

  return (
    <div className="stack">
      <section className="hero">
        <div>
          <div className="eyebrow">CREIXEMENT / KAIRON V9.2</div>
          <h1>Chief Operator</h1>
          <p>Truth-first venture operating system. Configuration never counts as execution; consequential authority remains outside the autonomous L0–L2 envelope.</p>
        </div>
        <div className="hero-state">
          <span className={`pulse ${runtime.state.status === 'healthy' ? 'pulse-live' : ''}`} />
          <div>
            <b>{runtime.loading ? 'Checking runtime' : titleCase(runtime.state.status)}</b>
            <small>{runtime.state.origin ?? 'No browser runtime origin configured'}</small>
          </div>
        </div>
      </section>

      <div className="metric-grid">
        <Metric label="Runtime" value={runtime.state.status.toUpperCase()} detail="Public /diagz probe" truth={runtimeTruth} />
        <Metric label="Scheduler proof" value={yes(p.cloudflare_scheduler_verified) ? 'VERIFIED' : 'UNVERIFIED'} detail={`${num(p.completed_healthy_ticks_30m)} completed healthy ticks / 30m`} truth={yes(p.cloudflare_scheduler_verified) ? 'verified' : proof.error ? 'unavailable' : 'blocked'} />
        <Metric label="Production gate" value={yes(g.promotable) ? 'OPEN' : 'CLOSED'} detail="Requires CI + matching runtime + scheduler + safety" truth={yes(g.promotable) ? 'verified' : gate.error ? 'unavailable' : 'blocked'} />
        <Metric label="Active ecology" value={num(e.active_population)} detail={`${num(e.active_niches)} active niches`} truth={truthFromQuery(ecology)} />
        <Metric label="Runtime-ready connectors" value={operationalConnectors} detail={`${connectors.rows.length} observed connectors`} truth={truthFromQuery(connectors, operationalConnectors > 0)} />
        <Metric label="Owner decisions" value={approvals.rows.length} detail="Explicit governance queue" truth={truthFromQuery(approvals, approvals.rows.length > 0)} />
        <Metric label="Opportunities" value={opportunities.rows.length} detail="Live opportunity records" truth={truthFromQuery(opportunities, opportunities.rows.length > 0)} />
        <Metric label="Verified won revenue" value={euro(wonRevenue)} detail="Never inferred from configuration" truth={wonRevenue > 0 ? 'verified' : truthFromQuery(revenue, revenue.rows.length > 0)} />
      </div>

      <div className="grid-2">
        <Panel title="Next operating priorities" icon={<Sparkles size={17} />}>
          <ol className="priority-list">
            <li><b>Prove runtime cadence.</b><span>Three healthy completed ticks from one deployed commit automatically verify the Cloudflare scheduler.</span></li>
            <li><b>Converge provider truth.</b><span>Only runtime-ready, permitted and receipt-capable connectors can support autonomous jobs.</span></li>
            <li><b>Create commercial evidence.</b><span>Move from configured services to verified opportunities, delivery receipts and paid outcomes.</span></li>
            <li><b>Preserve constitutional boundaries.</b><span>Payments, contracts, property commitments and irreversible actions remain owner-controlled.</span></li>
          </ol>
        </Panel>
        <Panel title="Service economics" icon={<Layers3 size={17} />}>
          <div className="service-list">
            {SERVICES.map((service) => (
              <div className="service-row" key={service.code}>
                <b>{service.code}</b><span>{service.name}</span><em>{service.automation}% auto</em><strong>{euro(service.price)}</strong>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="System truth boundary" icon={<ShieldCheck size={17} />}>
        <div className="truth-grid">
          <div><span>Supabase control plane</span><TruthBadge state={supabaseConfigured ? 'configured' : 'unavailable'} /></div>
          <div><span>Cloudflare runtime execution</span><TruthBadge state={runtimeTruth} /></div>
          <div><span>Immutable cadence evidence</span><TruthBadge state={yes(p.cloudflare_cadence_stable) ? 'verified' : proof.error ? 'unavailable' : 'blocked'} /></div>
          <div><span>External outreach</span><TruthBadge state="blocked" /></div>
          <div><span>Payment authority</span><TruthBadge state="blocked" /></div>
          <div><span>Contract / property authority</span><TruthBadge state="blocked" /></div>
        </div>
        <button className="primary" onClick={() => setPage('runtime')}>Inspect runtime proof</button>
      </Panel>
    </div>
  );
}

function RuntimePage() {
  const proof = useRelation('v_runtime_cadence_proof_v9', 1);
  const summary = useRelation('v_runtime_proof_summary_v9', 1);
  const heartbeats = useRelation('runtime_heartbeats_v5', 20, 'last_seen_at');
  const scheduler = useRelation('scheduler_bindings_v6', 30);
  const gate = useRelation('v_production_gate_v6', 1);
  const health = useRelation('v_operating_health_v6', 1);
  const providers = useRelation('v_provider_readiness_v6', 50);
  const runtime = useRuntimeProbe();
  const p = proof.rows[0] ?? {};
  const s = summary.rows[0] ?? {};
  const g = gate.rows[0] ?? {};
  const h = health.rows[0] ?? {};
  const refreshAll = () => void Promise.all([proof.refresh(), summary.refresh(), heartbeats.refresh(), scheduler.refresh(), gate.refresh(), health.refresh(), providers.refresh(), runtime.refresh()]);

  return (
    <div className="stack">
      <PageHead title="Runtime Proof" subtitle="Execution evidence, cadence proof and release readiness. No configuration-only success states." action={<button className="secondary" onClick={refreshAll}><RefreshCw size={15} /> Refresh all</button>} />
      <div className="metric-grid">
        <Metric label="Completed tick samples" value={num(s.completed_healthy_ticks_30m)} detail="Healthy tick_completed samples in 30m" truth={truthFromQuery(summary, num(s.completed_healthy_ticks_30m) > 0)} />
        <Metric label="Average cadence" value={`${num(p.average_gap_minutes).toFixed(2)} min`} detail="Same deployed commit only" truth={yes(p.cadence_stable) ? 'verified' : proof.error ? 'unavailable' : 'blocked'} />
        <Metric label="Maximum gap" value={`${num(p.maximum_gap_minutes).toFixed(2)} min`} detail="Contract 5m, tolerance +3m" truth={yes(p.cadence_stable) ? 'verified' : proof.error ? 'unavailable' : 'blocked'} />
        <Metric label="Scheduler binding" value={yes(s.cloudflare_scheduler_verified) ? 'ACTIVE' : 'NOT VERIFIED'} detail={shortTime(s.scheduler_last_verified_at)} truth={yes(s.cloudflare_scheduler_verified) ? 'verified' : 'blocked'} />
        <Metric label="Runtime instances" value={num(h.healthy_runtime_instances)} detail="Healthy within operating window" truth={num(h.healthy_runtime_instances) > 0 ? 'verified' : health.error ? 'unavailable' : 'blocked'} />
        <Metric label="Production promotable" value={yes(g.promotable) ? 'YES' : 'NO'} detail="Final evidence gate" truth={yes(g.promotable) ? 'verified' : gate.error ? 'unavailable' : 'blocked'} />
      </div>
      <div className="grid-2">
        <Panel title="Public Worker probe" icon={<Activity size={17} />}>
          <dl className="kv">
            <div><dt>Status</dt><dd>{runtime.state.status}</dd></div>
            <div><dt>Origin</dt><dd>{runtime.state.origin ?? 'not configured'}</dd></div>
            <div><dt>Reachable</dt><dd>{runtime.state.reachable ? 'yes' : 'no'}</dd></div>
            <div><dt>Observed</dt><dd>{shortTime(runtime.state.observedAt)}</dd></div>
            <div><dt>Error</dt><dd>{runtime.state.error ?? '—'}</dd></div>
          </dl>
          {runtime.state.payload ? <pre className="json-box">{JSON.stringify(runtime.state.payload, null, 2)}</pre> : null}
        </Panel>
        <Panel title="Cadence attestation" icon={<BadgeCheck size={17} />}>
          <dl className="kv">
            <div><dt>Runtime</dt><dd>{text(p.runtime_id)}</dd></div>
            <div><dt>Version</dt><dd>{text(p.version)}</dd></div>
            <div><dt>Commit</dt><dd className="mono">{text(p.commit_sha)}</dd></div>
            <div><dt>Stable</dt><dd>{yes(p.cadence_stable) ? 'yes' : 'no'}</dd></div>
            <div><dt>Latest receipt</dt><dd className="mono">{text(p.latest_receipt_ref)}</dd></div>
          </dl>
        </Panel>
      </div>
      <Panel title="Current runtime register" icon={<Database size={17} />}><DataTable state={heartbeats} empty="No runtime heartbeat has been observed." /></Panel>
      <Panel title="Scheduler bindings" icon={<Workflow size={17} />}><DataTable state={scheduler} empty="No scheduler bindings are recorded." /></Panel>
      <Panel title="Provider readiness" icon={<Network size={17} />}><DataTable state={providers} empty="No provider has produced live readiness evidence." /></Panel>
    </div>
  );
}

function BusinessPage() {
  const products = useRelation('products', 100);
  const opportunities = useRelation('opportunities', 100);
  const recommendations = useRelation('recommendations', 100);
  const experiments = useRelation('experiments', 100);
  const reports = useRelation('reports', 100);
  const revenue = useRelation('revenue_events', 100, 'created_at');
  const gross = revenue.rows.reduce((sum, row) => sum + num(row.amount ?? row.value ?? 0), 0);

  return (
    <div className="stack">
      <PageHead title="Business" subtitle="Products, opportunities, recommendations, experiments, deliverables and revenue evidence." />
      <div className="metric-grid">
        <Metric label="Products" value={products.rows.length} truth={truthFromQuery(products, products.rows.length > 0)} />
        <Metric label="Opportunities" value={opportunities.rows.length} truth={truthFromQuery(opportunities, opportunities.rows.length > 0)} />
        <Metric label="Recommendations" value={recommendations.rows.length} truth={truthFromQuery(recommendations, recommendations.rows.length > 0)} />
        <Metric label="Experiments" value={experiments.rows.length} truth={truthFromQuery(experiments, experiments.rows.length > 0)} />
        <Metric label="Reports" value={reports.rows.length} truth={truthFromQuery(reports, reports.rows.length > 0)} />
        <Metric label="Recorded revenue events" value={euro(gross)} detail={`${revenue.rows.length} events`} truth={truthFromQuery(revenue, revenue.rows.length > 0)} />
      </div>
      <div className="grid-2"><Panel title="Opportunities" icon={<Radar size={17} />}><DataTable state={opportunities} /></Panel><Panel title="Recommendations" icon={<BrainCircuit size={17} />}><DataTable state={recommendations} /></Panel></div>
      <div className="grid-2"><Panel title="Products" icon={<Layers3 size={17} />}><DataTable state={products} /></Panel><Panel title="Experiments" icon={<BarChart3 size={17} />}><DataTable state={experiments} /></Panel></div>
      <Panel title="Revenue evidence" icon={<CircleDollarSign size={17} />}><DataTable state={revenue} empty="No verified revenue event has been recorded." /></Panel>
    </div>
  );
}

function EcologyPage() {
  const dashboard = useRelation('v_bioecology_dashboard_v9', 1);
  const organisms = useRelation('ecology_organisms_v9', 100);
  const niches = useRelation('ecology_niches_v9', 100);
  const courts = useRelation('adversarial_court_runs_v9', 100, 'created_at');
  const canaries = useRelation('capability_canaries_v9', 100);
  const d = dashboard.rows[0] ?? {};
  const nicheData = niches.rows.slice(0, 20).map((row) => ({
    name: text(row.niche_key ?? row.display_name).slice(0, 18),
    pressure: num(row.selection_pressure),
    competition: num(row.competition),
    demand: num(row.demand),
  }));
  const organismData = organisms.rows.slice(0, 30).map((row, index) => ({
    name: `G${num(row.generation)}-${index + 1}`,
    fitness: num(row.fitness),
    telomere: num(row.telomere),
    energy: num(row.energy),
  }));

  return (
    <div className="stack">
      <PageHead title="Ecology V9" subtitle="Operational evolutionary mechanisms: selection, telomeres, niches, courts and canaries. No sentience claims." />
      <div className="metric-grid">
        <Metric label="Population" value={num(d.active_population)} truth={truthFromQuery(dashboard)} />
        <Metric label="Niches" value={num(d.active_niches)} truth={truthFromQuery(dashboard)} />
        <Metric label="Mean fitness" value={num(d.mean_fitness).toFixed(3)} truth={truthFromQuery(dashboard)} />
        <Metric label="Mean telomere" value={num(d.mean_telomere).toFixed(3)} truth={truthFromQuery(dashboard)} />
        <Metric label="Court runs" value={courts.rows.length} truth={truthFromQuery(courts, courts.rows.length > 0)} />
        <Metric label="Canaries" value={canaries.rows.length} truth={truthFromQuery(canaries, canaries.rows.length > 0)} />
      </div>
      <div className="grid-2">
        <Panel title="Niche pressure" icon={<Radar size={17} />}>
          {nicheData.length ? <div className="chart"><ResponsiveContainer width="100%" height={270}><BarChart data={nicheData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" fontSize={10} /><YAxis domain={[0, 1]} fontSize={10} /><Tooltip /><Bar dataKey="pressure" fill="#31453c" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div> : <Empty title="No niche observations" body="The schema is ready, but no live niche evidence is available to this UI." />}
        </Panel>
        <Panel title="Fitness and telomeres" icon={<Dna size={17} />}>
          {organismData.length ? <div className="chart"><ResponsiveContainer width="100%" height={270}><AreaChart data={organismData}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" hide /><YAxis domain={[0, 1]} fontSize={10} /><Tooltip /><Area type="monotone" dataKey="fitness" stroke="#31453c" fill="#dbe3dc" /><Area type="monotone" dataKey="telomere" stroke="#8b603f" fill="#eadbcf" /></AreaChart></ResponsiveContainer></div> : <Empty title="No organism observations" body="Population materialization has not produced UI-visible rows yet." />}
        </Panel>
      </div>
      <Panel title="Organisms" icon={<Dna size={17} />}><DataTable state={organisms} /></Panel>
      <div className="grid-2"><Panel title="Adversarial courts" icon={<ShieldCheck size={17} />}><DataTable state={courts} /></Panel><Panel title="Capability canaries" icon={<BadgeCheck size={17} />}><DataTable state={canaries} /></Panel></div>
    </div>
  );
}

function TectumPage() {
  const properties = useRelation('tectum_properties', 100);
  const cases = useRelation('tectum_cases', 100);
  const reportJobs = useRelation('tectum_report_jobs', 100);
  return (
    <div className="stack">
      <PageHead title="Tectum" subtitle="Cloud-only property intelligence: permitted sources → evidence → underwriting → scenarios → report → digest-bound approvals." />
      <div className="metric-grid">
        <Metric label="Properties" value={properties.rows.length} truth={truthFromQuery(properties, properties.rows.length > 0)} />
        <Metric label="Cases" value={cases.rows.length} truth={truthFromQuery(cases, cases.rows.length > 0)} />
        <Metric label="Report jobs" value={reportJobs.rows.length} truth={truthFromQuery(reportJobs, reportJobs.rows.length > 0)} />
        <Metric label="Required approvals" value="4" detail="Distinct and digest-bound" truth="configured" />
      </div>
      <Panel title="Governed workflow" icon={<Workflow size={17} />}>
        <div className="flow">
          {['Permitted source', 'Rights & evidence', 'Canonical property', 'Underwriting', 'Traditional / Rooms / Temporary', 'Readiness', 'Cloud render', 'QA', '4 approvals', 'Client-ready'].map((step, index) => <div className="flow-step" key={step}><span>{index + 1}</span>{step}</div>)}
        </div>
      </Panel>
      <div className="grid-2"><Panel title="Properties" icon={<Building2 size={17} />}><DataTable state={properties} /></Panel><Panel title="Cases" icon={<TableProperties size={17} />}><DataTable state={cases} /></Panel></div>
      <Panel title="Report jobs" icon={<FileCheck2 size={17} />}><DataTable state={reportJobs} empty="No live report jobs. Draft output is not client-ready until four digest-bound approvals exist." /></Panel>
    </div>
  );
}

function ApprovalsPage() {
  const pending = useRelation('v_pending_approvals', 100);
  const ownerQueue = useRelation('v_owner_decision_queue_v6', 100);
  const decisions = useRelation('owner_decisions_v6', 100, 'created_at');
  const approvals = useRelation('approvals', 100);
  const audit = useRelation('audit_events', 100, 'created_at');
  return (
    <div className="stack">
      <PageHead title="Approvals & Audit" subtitle="Consequential actions remain explicit, digest-bound and auditable. Autonomous execution stops at the L3 boundary." />
      <div className="metric-grid">
        <Metric label="Pending approvals" value={pending.rows.length} truth={truthFromQuery(pending, pending.rows.length > 0)} />
        <Metric label="Owner decision queue" value={ownerQueue.rows.length} truth={truthFromQuery(ownerQueue, ownerQueue.rows.length > 0)} />
        <Metric label="Recorded decisions" value={decisions.rows.length} truth={truthFromQuery(decisions, decisions.rows.length > 0)} />
        <Metric label="Approval records" value={approvals.rows.length} truth={truthFromQuery(approvals, approvals.rows.length > 0)} />
      </div>
      <div className="grid-2"><Panel title="Owner queue" icon={<Users size={17} />}><DataTable state={ownerQueue} /></Panel><Panel title="Pending approvals" icon={<ShieldCheck size={17} />}><DataTable state={pending} /></Panel></div>
      <Panel title="Owner decisions" icon={<BadgeCheck size={17} />}><DataTable state={decisions} /></Panel>
      <Panel title="Audit log" icon={<Database size={17} />}><DataTable state={audit} empty="No audit events are visible to this browser role." /></Panel>
    </div>
  );
}

function SystemPage() {
  const connectors = useRelation('connectors', 100);
  const health = useRelation('v_connector_health', 100);
  const policies = useRelation('policies', 100);
  const agents = useRelation('agents', 100);
  const jobs = useRelation('job_definitions', 100);
  const drift = useRelation('runtime_drift_findings_v4', 100, 'created_at');
  return (
    <div className="stack">
      <PageHead title="System" subtitle="Connectors, policies, agents, jobs and runtime drift. Browser configuration is never treated as production credentials." />
      <div className="metric-grid">
        <Metric label="Connectors" value={connectors.rows.length} truth={truthFromQuery(connectors, connectors.rows.length > 0)} />
        <Metric label="Runtime-ready" value={health.rows.filter((row) => String(row.effective_health) === 'runtime_ready').length} truth={truthFromQuery(health, health.rows.some((row) => String(row.effective_health) === 'runtime_ready'))} />
        <Metric label="Policies" value={policies.rows.length} truth={truthFromQuery(policies, policies.rows.length > 0)} />
        <Metric label="Agents" value={agents.rows.length} truth={truthFromQuery(agents, agents.rows.length > 0)} />
        <Metric label="Jobs" value={jobs.rows.length} truth={truthFromQuery(jobs, jobs.rows.length > 0)} />
        <Metric label="Open drift findings" value={drift.rows.filter((row) => String(row.status) === 'open').length} truth={truthFromQuery(drift, drift.rows.length > 0)} />
      </div>
      <div className="grid-2"><Panel title="Connector health" icon={<Network size={17} />}><DataTable state={health} /></Panel><Panel title="Policies" icon={<ShieldCheck size={17} />}><DataTable state={policies} /></Panel></div>
      <div className="grid-2"><Panel title="Agents" icon={<BrainCircuit size={17} />}><DataTable state={agents} /></Panel><Panel title="Jobs" icon={<Workflow size={17} />}><DataTable state={jobs} /></Panel></div>
      <Panel title="Runtime drift" icon={<AlertTriangle size={17} />}><DataTable state={drift} empty="No drift findings are visible." /></Panel>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>('overview');
  const groups = useMemo(() => Array.from(new Set(NAV.map((item) => item.group))), []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">C</div><div><b>Creixement</b><span>Kairon V9.2</span></div></div>
        <nav>
          {groups.map((group) => (
            <div className="nav-group" key={group}>
              <small>{group}</small>
              {NAV.filter((item) => item.group === group).map((item) => {
                const Icon = item.icon;
                return <button key={item.page} className={page === item.page ? 'active' : ''} onClick={() => setPage(item.page)}><Icon size={16} />{item.label}</button>;
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <TruthBadge state={supabaseConfigured ? 'configured' : 'unavailable'} />
          <span>Dedicated repo branch · credits-free UI</span>
        </div>
      </aside>
      <main className="content">
        {page === 'overview' && <Overview setPage={setPage} />}
        {page === 'runtime' && <RuntimePage />}
        {page === 'business' && <BusinessPage />}
        {page === 'ecology' && <EcologyPage />}
        {page === 'tectum' && <TectumPage />}
        {page === 'approvals' && <ApprovalsPage />}
        {page === 'system' && <SystemPage />}
      </main>
    </div>
  );
}
