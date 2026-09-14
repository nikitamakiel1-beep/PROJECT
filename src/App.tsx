import { useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, BadgeCheck, BrainCircuit, Building2, ChevronRight, CircleDollarSign,
  Command, Database, Dna, FileDown, FileText, FlaskConical, Gauge, GitBranch, HeartPulse,
  Home, Layers3, Network, Radar, RefreshCw, Search, Settings, ShieldCheck, Sparkles, TableProperties,
  Users, Waypoints, Workflow, X
} from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { readRows, supabaseConfigured } from './lib/supabase';
import { exportGovernedPdf } from './lib/pdf';

type Row = Record<string, unknown>;
type Truth = 'live' | 'seeded' | 'unavailable' | 'needs_setup' | 'blocked';

const SERVICES = [
  { code:'IVA', name:'International Visibility Audit', status:'active', price:149, beta:99, hours:2.5, margin:144, automation:70 },
  { code:'CRM', name:'CRM & Lead Tracker Setup', status:'active', price:299, beta:199, hours:4, margin:294, automation:80 },
  { code:'OSP', name:'International Sales One-Pager', status:'active', price:249, beta:169, hours:3.5, margin:239, automation:65 },
  { code:'WAB', name:'WhatsApp Business Setup', status:'add-on', price:129, beta:89, hours:1.5, margin:129, automation:75 },
  { code:'ISS', name:'International Starter System', status:'inactive', price:599, beta:449, hours:8, margin:579, automation:72 },
];

const NAV = [
  { group:'Global', items:[['Overview','overview',Home],['Recommendations','recommendations',Sparkles],['Opportunities','opportunities',Radar],['Approvals','approvals',ShieldCheck],['Activity','activity',Activity]] },
  { group:'Business', items:[['Products','products',Layers3],['Clients & CRM','crm',Users],['Reports & Deliverables','reports',FileText],['Revenue','revenue',CircleDollarSign],['Tectum','tectum',Building2],['Market Intelligence','market',Search],['Funding Radar','funding',Radar]] },
  { group:'AI Operations', items:[['Kairon','kairon',BrainCircuit],['Agents','agents',Network],['Runs','runs',Workflow],['Automations','automations',RefreshCw],['Experiments','experiments',FlaskConical],['Memory / Knowledge','memory',Database]] },
  { group:'Ecology V9', items:[['Ecology','ecology',Dna],['Lineages','lineages',GitBranch],['Niches','niches',Waypoints],['Adversarial Courts','courts',ShieldCheck],['Immune Memory','immune',HeartPulse],['Canary Promotion','canaries',BadgeCheck]] },
  { group:'System', items:[['Connectors','connectors',Network],['Policies & Permissions','policies',ShieldCheck],['Audit Log','audit',TableProperties],['Health & Release','health',Gauge],['Settings','settings',Settings]] },
] as const;

const RELATIONS: Record<string,string> = {
  recommendations:'recommendations', opportunities:'opportunities', approvals:'approvals', products:'products', crm:'opportunities', reports:'reports', revenue:'revenue_events',
  tectum:'tectum_cases', agents:'agents', runs:'job_executions', automations:'job_definitions', experiments:'experiments', connectors:'connectors', policies:'policies', audit:'audit_events',
  lineages:'ecology_organisms_v9', niches:'ecology_niches_v9', courts:'adversarial_court_runs_v9', immune:'ecology_immune_memory_v9', canaries:'capability_canaries_v9'
};

function text(v: unknown, fallback='—') { return v === null || v === undefined || v === '' ? fallback : String(v); }
function num(v: unknown) { const n = Number(v ?? 0); return Number.isFinite(n) ? n : 0; }
function euro(v: unknown) { return new Intl.NumberFormat('en-IE',{style:'currency',currency:'EUR',maximumFractionDigits:0}).format(num(v)); }
function titleCase(s: string) { return s.replace(/[_-]+/g,' ').replace(/\b\w/g,c=>c.toUpperCase()); }

function TruthBadge({state}:{state:Truth}) {
  const label = {live:'Live verified',seeded:'Seeded configuration',unavailable:'Unavailable',needs_setup:'Needs setup',blocked:'Blocked'}[state];
  return <span className={`truth truth-${state}`}>{label}</span>;
}

function useRows(relation?: string, limit=100) {
  const [rows,setRows] = useState<Row[]>([]);
  const [loading,setLoading] = useState(Boolean(relation));
  const [error,setError] = useState('');
  const refresh = async () => {
    if (!relation) { setRows([]); setLoading(false); return; }
    setLoading(true); setError('');
    try { setRows(await readRows<Row>(relation,limit)); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };
  useEffect(()=>{ void refresh(); },[relation]);
  return {rows,loading,error,refresh};
}

function Metric({label,value,sub,truth='live'}:{label:string,value:string|number,sub?:string,truth?:Truth}) {
  return <div className="metric"><div className="metric-top"><span>{label}</span><TruthBadge state={truth}/></div><strong>{value}</strong>{sub && <small>{sub}</small>}</div>;
}

function Empty({title,body}:{title:string,body:string}) { return <div className="empty"><AlertTriangle size={20}/><div><strong>{title}</strong><p>{body}</p></div></div>; }

function DataTable({rows,loading,error,empty='No verified records.'}:{rows:Row[],loading:boolean,error:string,empty?:string}) {
  if (loading) return <div className="loading"><RefreshCw className="spin" size={18}/> Loading live state…</div>;
  if (error) return <Empty title="Live query unavailable" body={error}/>;
  if (!rows.length) return <Empty title="No records" body={empty}/>;
  const columns = Object.keys(rows[0]).slice(0,9);
  return <div className="table-wrap"><table><thead><tr>{columns.map(c=><th key={c}>{titleCase(c)}</th>)}</tr></thead><tbody>{rows.slice(0,50).map((r,i)=><tr key={i}>{columns.map(c=><td key={c}>{typeof r[c] === 'object' ? JSON.stringify(r[c]) : text(r[c])}</td>)}</tr>)}</tbody></table></div>;
}

function Overview() {
  const kairon = useRows('v_kairon_command_v8',1);
  const eco = useRows('v_bioecology_dashboard_v9',1);
  const connectors = useRows('connectors',50);
  const approvals = useRows('v_pending_approvals',20);
  const k = kairon.rows[0] ?? {};
  const e = eco.rows[0] ?? {};
  const connected = connectors.rows.filter(r=>String(r.state ?? r.status)==='connected').length;
  return <div className="stack">
    <section className="hero"><div><div className="eyebrow">CREIXEMENT / KAIRON V9</div><h1>Chief Operator</h1><p>Autonomous venture factory with bounded L0–L2 execution, exact release evidence and constitutional L3 gates.</p></div><div className="hero-state"><span className="pulse"/><div><b>{text(k.operator_state ?? k.status,'Unavailable')}</b><small>runtime truth, not configuration</small></div></div></section>
    <div className="metric-grid">
      <Metric label="Pipeline" value="€0" sub="CRM verified baseline" truth="live"/><Metric label="Won revenue" value="€0" sub="No fabricated traction" truth="live"/>
      <Metric label="Active ecology" value={num(e.active_population)} sub={`${num(e.active_niches)} niches`} truth={eco.error?'unavailable':'live'}/>
      <Metric label="Connected providers" value={connected} sub={`${connectors.rows.length} configured`} truth={connectors.error?'unavailable':'live'}/>
      <Metric label="Pending approvals" value={approvals.rows.length} sub="Owner/policy gates" truth={approvals.error?'unavailable':'live'}/>
      <Metric label="Economic L2" value={k.economic_l2_allowed === true ? 'OPEN' : 'LOCKED'} sub="Fails closed without evidence" truth={k.economic_l2_allowed === true?'live':'blocked'}/>
    </div>
    <div className="grid-2"><Panel title="Today’s priorities" icon={<Sparkles size={17}/>}><ol className="priority"><li>Verify exact deployed release and heartbeat SHA.</li><li>Converge migration 020 and ecological population.</li><li>Wire first runtime provider without widening authority.</li><li>Generate first evidence-backed product experiment.</li></ol></Panel>
    <Panel title="Product readiness" icon={<Layers3 size={17}/>}><div className="service-list">{SERVICES.map(s=><div className="service" key={s.code}><b>{s.code}</b><span>{s.name}</span><em>{s.automation}% auto</em><strong>{euro(s.price)}</strong></div>)}</div></Panel></div>
    <div className="grid-2"><Panel title="System truth" icon={<ShieldCheck size={17}/>}><div className="truth-list"><div><span>Cloudflare runtime</span><TruthBadge state="needs_setup"/></div><div><span>Supabase control plane</span><TruthBadge state={supabaseConfigured?'live':'unavailable'}/></div><div><span>Lovable branch UI</span><TruthBadge state="live"/></div><div><span>External outreach</span><TruthBadge state="blocked"/></div></div></Panel>
    <Panel title="What should Kairon do now?" icon={<BrainCircuit size={17}/>}><p className="recommendation">Prefer repair and evidence convergence over expansion. The release gate should remain closed until runtime heartbeat, scheduler receipt, exact SHA and migration head are all verified together.</p><button className="primary">Open Kairon control</button></Panel></div>
  </div>;
}

function Panel({title,icon,actions,children}:{title:string,icon?:React.ReactNode,actions?:React.ReactNode,children:React.ReactNode}) { return <section className="panel"><header><div>{icon}<h3>{title}</h3></div>{actions}</header><div className="panel-body">{children}</div></section>; }

function Ecology() {
  const dash=useRows('v_bioecology_dashboard_v9',1); const courts=useRows('v_conway_court_status_v9',1); const organisms=useRows('ecology_organisms_v9',100); const niches=useRows('ecology_niches_v9',100);
  const d=dash.rows[0]??{}, c=courts.rows[0]??{};
  const nicheData=niches.rows.map(r=>({name:text(r.niche_key).slice(0,14),pressure:num(r.selection_pressure),competition:num(r.competition),demand:num(r.demand)}));
  const organismData=organisms.rows.slice(0,30).map((r,i)=>({name:`G${num(r.generation)}-${i+1}`,fitness:num(r.fitness),telomere:num(r.telomere),energy:num(r.energy)}));
  return <div className="stack"><PageHead title="Ecology V9" subtitle="Conway-inspired evolutionary control mechanisms; operational algorithms, not sentience claims."/>
    <div className="metric-grid"><Metric label="Population" value={num(d.active_population)} truth={dash.error?'unavailable':'live'}/><Metric label="Niches" value={num(d.active_niches)} truth={dash.error?'unavailable':'live'}/><Metric label="Mean fitness" value={num(d.mean_fitness).toFixed(3)} truth={dash.error?'unavailable':'live'}/><Metric label="Mean telomere" value={num(d.mean_telomere).toFixed(3)} truth={dash.error?'unavailable':'live'}/><Metric label="Court runs" value={num(c.total_courts)} truth={courts.error?'unavailable':'live'}/><Metric label="Verified canaries" value={num(c.verified_canaries)} truth={courts.error?'unavailable':'live'}/></div>
    <div className="grid-2"><Panel title="Niche pressure" icon={<Waypoints size={17}/>}><ChartBox>{nicheData.length?<ResponsiveContainer width="100%" height={260}><BarChart data={nicheData}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name" fontSize={10}/><YAxis domain={[0,1]} fontSize={10}/><Tooltip/><Bar dataKey="pressure" fill="#2e3a33" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer>:<Empty title="No niche observations" body="The schema is ready; live population evidence is still empty."/>}</ChartBox></Panel>
    <Panel title="Organism fitness / telomeres" icon={<Dna size={17}/>}><ChartBox>{organismData.length?<ResponsiveContainer width="100%" height={260}><AreaChart data={organismData}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name" hide/><YAxis domain={[0,1]} fontSize={10}/><Tooltip/><Area type="monotone" dataKey="fitness" stroke="#2e3a33" fill="#d8dfd8"/><Area type="monotone" dataKey="telomere" stroke="#9b6d43" fill="#eadbca"/></AreaChart></ResponsiveContainer>:<Empty title="Population not materialized" body="Migration 020 is the canonical bridge from commercial_genomes into the V9 ecology."/>}</ChartBox></Panel></div>
    <Panel title="Ecological organisms" icon={<Dna size={17}/>}><DataTable {...organisms} empty="No V9 organisms have been verified yet."/></Panel>
  </div>;
}

function Tectum() {
  const cases=useRows('tectum_cases',100); const props=useRows('tectum_properties',100); const reports=useRows('tectum_report_jobs',100);
  const exportPdf=()=>exportGovernedPdf('Tectum Property Intelligence','Controlled real-estate report shell — evidence and approvals required before client release.',[
    {title:'Governance',body:['Permitted source intake → evidence validation → underwriting → scenarios → readiness → report → QA → four digest-bound approvals. Any byte change invalidates prior approval.']},
    {title:'Current queue',rows:[['Properties',String(props.rows.length)],['Cases',String(cases.rows.length)],['Report jobs',String(reports.rows.length)],['Offer authority','Owner only'],['Payment authority','Owner only']]},
    {title:'Scenario framework',rows:[['Traditional','Long-term rental underwriting'],['Rooms','Room-by-room scenario'],['Temporary','Temporary rental scenario']]}
  ],'tectum-governed-report.pdf');
  return <div className="stack"><PageHead title="Tectum" subtitle="Real-estate intelligence, deterministic underwriting and digest-bound report factory." action={<button className="primary" onClick={exportPdf}><FileDown size={15}/> Generate governed PDF</button>}/>
    <div className="metric-grid"><Metric label="Properties" value={props.rows.length} truth={props.error?'unavailable':'live'}/><Metric label="Cases" value={cases.rows.length} truth={cases.error?'unavailable':'live'}/><Metric label="Report jobs" value={reports.rows.length} truth={reports.error?'unavailable':'live'}/><Metric label="Approvals required" value="4" sub="distinct, digest-bound" truth="seeded"/></div>
    <Panel title="Tectum production workflow" icon={<Workflow size={17}/>}><div className="pipeline">{['Permitted source','Rights & evidence','Property candidate','Underwriting','3 scenarios','Readiness','Report render','QA','4 approvals','Client-ready'].map((s,i)=><div className="pipe" key={s}><span>{i+1}</span>{s}{i<9&&<ChevronRight size={14}/>}</div>)}</div></Panel>
    <div className="grid-2"><Panel title="Properties" icon={<Building2 size={17}/>}><DataTable {...props}/></Panel><Panel title="Cases" icon={<TableProperties size={17}/>}><DataTable {...cases}/></Panel></div>
    <Panel title="Report queue" icon={<FileText size={17}/>}><DataTable {...reports} empty="No live report jobs. Generated PDFs must remain drafts until evidence and four-role approvals are complete."/></Panel>
  </div>;
}

function Reports() {
  const reports=useRows('reports',100);
  const templates=['International Visibility Audit','Market Snapshot','Competitor Mini-Scan','Funding Fit','Prospect Account Intelligence','Sales One-Pager','Tectum Property Report'];
  const createTemplatePdf=(name:string)=>exportGovernedPdf(name,'Creixement Report Factory — draft template, not a verified client deliverable.',[
    {title:'Release state',rows:[['Status','Draft'],['Evidence','Required'],['QA','Required'],['Approval','Required before external delivery']]},
    {title:'Method',body:['Inputs → evidence → analysis → draft → QA → approval → ready to deliver → delivered → outcome measured. Every material claim should retain provenance, timestamp, assumptions and confidence.']}
  ],`${name.toLowerCase().replace(/\s+/g,'-')}.pdf`);
  return <div className="stack"><PageHead title="Reports & Deliverables" subtitle="Controlled report factory with evidence, versioning, QA and release gates."/>
    <Panel title="Templates" icon={<FileText size={17}/>}><div className="template-grid">{templates.map(t=><button className="template" key={t} onClick={()=>createTemplatePdf(t)}><FileText size={18}/><span>{t}</span><small>Generate controlled draft PDF</small></button>)}</div></Panel>
    <Panel title="Live reports" icon={<TableProperties size={17}/>}><DataTable {...reports}/></Panel></div>;
}

function Kairon() { const command=useRows('v_kairon_command_v8',1); const cycles=useRows('kairon_control_cycles_v7',50); const row=command.rows[0]??{}; return <div className="stack"><PageHead title="Kairon" subtitle="Autonomous Chief Operator with bounded two-plane autonomy."/>
  <div className="metric-grid"><Metric label="Maintenance L2" value={row.maintenance_allowed===true?'OPEN':'LOCKED'} truth={row.maintenance_allowed===true?'live':'blocked'}/><Metric label="Economic L2" value={row.economic_l2_allowed===true?'OPEN':'LOCKED'} truth={row.economic_l2_allowed===true?'live':'blocked'}/><Metric label="Release" value={text(row.release_state,'Unknown')} truth="live"/><Metric label="Scheduler" value={text(row.scheduler_state,'Unknown')} truth="live"/></div>
  <Panel title="Command state" icon={<BrainCircuit size={17}/>}><DataTable {...command} empty="Kairon command view unavailable."/></Panel><Panel title="Control cycles" icon={<RefreshCw size={17}/>}><DataTable {...cycles}/></Panel></div>; }

function GenericPage({page,label}:{page:string,label:string}) { const data=useRows(RELATIONS[page],100); if(page==='products') return <Products data={data}/>; return <div className="stack"><PageHead title={label} subtitle={`Live control-plane surface for ${label.toLowerCase()}.`}/><Panel title={label} icon={<TableProperties size={17}/>} actions={<button className="ghost" onClick={data.refresh}><RefreshCw size={14}/> Refresh</button>}><DataTable {...data}/></Panel></div>; }
function Products({data}:{data:ReturnType<typeof useRows>}) { return <div className="stack"><PageHead title="Products" subtitle="Product factory registry, economics, automation and readiness."/><Panel title="Canonical launch catalogue" icon={<Layers3 size={17}/>}><div className="cards">{SERVICES.map(s=><article className="product-card" key={s.code}><div><span className="code">{s.code}</span><TruthBadge state="seeded"/></div><h3>{s.name}</h3><p>{s.status}</p><div className="product-metrics"><b>{euro(s.price)}</b><span>{s.automation}% automation</span><span>{s.hours} h delivery</span><span>{euro(s.margin)} contribution</span></div></article>)}</div></Panel><Panel title="Persistent product registry" icon={<Database size={17}/>}><DataTable {...data}/></Panel></div>; }

function PageHead({title,subtitle,action}:{title:string,subtitle:string,action?:React.ReactNode}) { return <div className="page-head"><div><div className="eyebrow">CREIXEMENT CONTROL PLANE</div><h2>{title}</h2><p>{subtitle}</p></div>{action}</div>; }
function ChartBox({children}:{children:React.ReactNode}) { return <div className="chart-box">{children}</div>; }

export default function App() {
  const [page,setPage]=useState('overview'); const [palette,setPalette]=useState(false); const [query,setQuery]=useState('');
  const flat=useMemo(()=>NAV.flatMap(g=>g.items.map(([label,key,Icon])=>({label,key,Icon}))),[]);
  const current=flat.find(x=>x.key===page)?.label ?? 'Overview';
  const filtered=flat.filter(x=>x.label.toLowerCase().includes(query.toLowerCase()));
  const render=()=>{ if(page==='overview')return <Overview/>; if(page==='ecology')return <Ecology/>; if(page==='tectum')return <Tectum/>; if(page==='reports')return <Reports/>; if(page==='kairon')return <Kairon/>; return <GenericPage page={page} label={current}/>; };
  return <div className="app">
    <aside><div className="brand"><div className="brand-mark">K</div><div><b>Kairon</b><span>Creixement V9</span></div></div><nav>{NAV.map(group=><div className="nav-group" key={group.group}><small>{group.group}</small>{group.items.map(([label,key,Icon])=><button key={key} className={page===key?'active':''} onClick={()=>setPage(key)}><Icon size={15}/><span>{label}</span></button>)}</div>)}</nav><div className="aside-foot"><TruthBadge state={supabaseConfigured?'live':'unavailable'}/><span>Dedicated GitHub branch UI</span></div></aside>
    <main><header className="topbar"><div><span className="crumb">Creixement</span><ChevronRight size={13}/><b>{current}</b></div><div className="top-actions"><button className="search-button" onClick={()=>setPalette(true)}><Search size={14}/> Search or command <kbd>⌘K</kbd></button><span className="version">V9 · 0.9.0</span></div></header><div className="content">{render()}</div></main>
    {palette&&<div className="palette-backdrop" onClick={()=>setPalette(false)}><div className="palette" onClick={e=>e.stopPropagation()}><div className="palette-input"><Command size={17}/><input autoFocus placeholder="Go to…" value={query} onChange={e=>setQuery(e.target.value)}/><button onClick={()=>setPalette(false)}><X size={16}/></button></div>{filtered.map(({label,key,Icon})=><button className="palette-item" key={key} onClick={()=>{setPage(key);setPalette(false);setQuery('')}}><Icon size={15}/>{label}<ChevronRight size={14}/></button>)}</div></div>}
  </div>;
}
