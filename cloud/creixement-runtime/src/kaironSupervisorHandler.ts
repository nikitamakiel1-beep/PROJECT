import { createHash } from "node:crypto";
import { runHandler as runLegacyHandler, type HandlerContext, type HandlerResult } from "./handlers.js";

function numeric(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function canonical(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  return `{${Object.entries(value as Record<string, unknown>)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, child]) => `${JSON.stringify(key)}:${canonical(child)}`)
    .join(",")}}`;
}

function digest(value: unknown): string {
  return createHash("sha256").update(canonical(value)).digest("hex");
}

const COURT_TYPES = new Set([
  "authority_traversal",
  "faustian_fuzz",
  "auditor_of_auditors",
  "mutation_detection",
]);
const COURT_FRESHNESS_MS = 2 * 60 * 60 * 1000;

export interface CourtRunRow {
  court_key: string;
  court_type: string;
  passed: boolean;
  created_at: string;
}

function courtCycleKey(courtKey: string): string {
  const parts = courtKey.split(":");
  return parts.length > 1 ? parts.slice(0, -1).join(":") : courtKey;
}

export function summarizeLatestCourtSuite(rows: CourtRunRow[], nowMs = Date.now()) {
  const sorted = [...rows].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  const newest = sorted.at(0);
  if (!newest) {
    return {
      latest_suite_key: null,
      latest_suite_total: 0,
      latest_suite_failed: 0,
      latest_suite_fresh: false,
      latest_suite_complete: false,
      latest_suite_at: null,
    };
  }

  const suiteKey = courtCycleKey(newest.court_key);
  const suite = sorted.filter((row) => courtCycleKey(row.court_key) === suiteKey);
  const presentTypes = new Set(suite.map((row) => row.court_type).filter((type) => COURT_TYPES.has(type)));
  const latestAtMs = Math.max(...suite.map((row) => Date.parse(row.created_at)).filter(Number.isFinite));
  const fresh = Number.isFinite(latestAtMs) && nowMs >= latestAtMs && (nowMs - latestAtMs) <= COURT_FRESHNESS_MS;
  const complete = COURT_TYPES.size === presentTypes.size && [...COURT_TYPES].every((type) => presentTypes.has(type));

  return {
    latest_suite_key: suiteKey,
    latest_suite_total: presentTypes.size,
    latest_suite_failed: suite.filter((row) => !row.passed).length,
    latest_suite_fresh: fresh,
    latest_suite_complete: complete,
    latest_suite_at: Number.isFinite(latestAtMs) ? new Date(latestAtMs).toISOString() : null,
  };
}

export interface KaironRuntimeSupervisorInput {
  legacy: Record<string, unknown>;
  proof: Record<string, unknown>;
  ecology: Record<string, unknown>;
  courts: Record<string, unknown>;
  health: Record<string, unknown>;
  portfolio: Record<string, unknown>;
}

export interface KaironRuntimeSupervisorSnapshot {
  version: "10.0";
  role: "chief-operator";
  executiveAgent: "Kairon";
  autonomyCeiling: "L2";
  truth: {
    schedulerExecutionProved: boolean;
    runtimeSafetyClean: boolean;
    configurationCountsAsExecution: false;
  };
  authority: {
    legacyEconomicL2Allowed: boolean;
    supervisedEconomicL2Open: boolean;
    courtEvidenceReady: boolean;
    courtEvidenceFresh: boolean;
    courtSuiteComplete: boolean;
    courtSuiteSize: number;
    courtSuiteFailed: number;
    consequentialBoundary: "L3-owner-only";
  };
  portfolio: {
    operatingProjects: number;
    incubatingProjects: number;
    pausedProjects: number;
    foundryCandidates: number;
    actionableOpportunities: number;
    tectumOperating: boolean;
    foundryEconomicL2Open: boolean;
  };
  adaptation: {
    mode: "recovery" | "challenge" | "balanced";
    redQueenPressure: number;
    woundHealingPriority: number;
    activePopulation: number;
    activeNiches: number;
    meanFitness: number;
    meanTelomere: number;
    verifiedCanaries: number;
    failedCourts: number;
  };
  invariants: readonly string[];
  proofDigest: string;
}

export function compileSupervisorySnapshot(input: KaironRuntimeSupervisorInput): KaironRuntimeSupervisorSnapshot {
  const schedulerExecutionProved = input.proof.cloudflare_scheduler_verified === true;
  const sensed = input.legacy.sensed as Record<string, unknown> | undefined;
  const preflight = sensed?.preflight as Record<string, unknown> | undefined;
  const runtimeSafetyClean = input.legacy.safetyClean === true || preflight?.safety_clean === true;
  const legacyEconomicL2Allowed = input.legacy.economicL2Allowed === true;

  const latestSuiteFieldsPresent = Object.prototype.hasOwnProperty.call(input.courts, "latest_suite_total");
  const courtSuiteSize = numeric(latestSuiteFieldsPresent ? input.courts.latest_suite_total : input.courts.total_courts);
  const courtSuiteFailed = numeric(latestSuiteFieldsPresent ? input.courts.latest_suite_failed : input.courts.failed_courts);
  const courtEvidenceFresh = latestSuiteFieldsPresent ? input.courts.latest_suite_fresh === true : true;
  const courtSuiteComplete = latestSuiteFieldsPresent ? input.courts.latest_suite_complete === true : courtSuiteSize > 0;
  const verifiedCanaries = numeric(input.courts.verified_canaries);
  const courtEvidenceReady = courtSuiteComplete && courtEvidenceFresh && courtSuiteFailed === 0;

  const openDeadLetters = numeric(input.health.open_job_dead_letters) + numeric(input.health.open_outbox_dead_letters);
  const openCircuits = numeric(input.health.open_handler_circuits);
  const criticalDrift = numeric(input.health.critical_drift);
  const healthyRuntimes = numeric(input.health.healthy_runtime_instances);
  const woundHealingPriority = clamp(
    0.16 * Math.min(openDeadLetters, 4)
      + 0.2 * Math.min(openCircuits, 3)
      + 0.25 * Math.min(criticalDrift, 2)
      + (healthyRuntimes > 0 ? 0 : 0.35),
  );

  const redQueenPressure = clamp(numeric(input.ecology.recent_red_queen_pressure));
  const supervisedEconomicL2Open = legacyEconomicL2Allowed
    && schedulerExecutionProved
    && runtimeSafetyClean
    && courtEvidenceReady
    && woundHealingPriority < 0.8;
  const mode = woundHealingPriority >= 0.5 ? "recovery" : redQueenPressure >= 0.65 ? "challenge" : "balanced";

  const stable = {
    version: "10.0",
    role: "chief-operator",
    executiveAgent: "Kairon",
    autonomyCeiling: "L2",
    truth: { schedulerExecutionProved, runtimeSafetyClean, configurationCountsAsExecution: false },
    authority: {
      legacyEconomicL2Allowed,
      supervisedEconomicL2Open,
      courtEvidenceReady,
      courtEvidenceFresh,
      courtSuiteComplete,
      courtSuiteSize,
      courtSuiteFailed,
      consequentialBoundary: "L3-owner-only",
    },
    portfolio: {
      operatingProjects: numeric(input.portfolio.operating_projects),
      incubatingProjects: numeric(input.portfolio.incubating_projects),
      pausedProjects: numeric(input.portfolio.paused_projects),
      foundryCandidates: numeric(input.portfolio.foundry_candidates),
      actionableOpportunities: numeric(input.portfolio.actionable_opportunities),
      tectumOperating: numeric(input.portfolio.tectum_operating) > 0,
      foundryEconomicL2Open: input.portfolio.supervised_economic_l2_open === true,
    },
    adaptation: {
      mode,
      redQueenPressure,
      woundHealingPriority,
      activePopulation: numeric(input.ecology.active_population),
      activeNiches: numeric(input.ecology.active_niches),
      meanFitness: clamp(numeric(input.ecology.mean_fitness)),
      meanTelomere: clamp(numeric(input.ecology.mean_telomere)),
      verifiedCanaries,
      failedCourts: courtSuiteFailed,
    },
    invariants: [
      "Kairon is chief operator of the Creixement business portfolio",
      "Tectum is a business project, not a parallel top-level authority",
      "future projects originate from evidence-linked opportunities",
      "truth hierarchy is monotonic",
      "configuration is not execution proof",
      "unknown or stale court evidence fails closed",
      "external/consequential authority remains L3 owner-only",
      "evolution cannot mutate rights, consent, secrets, payment, contract, property or irreversible deletion authority",
      "archive lineage and evidence; never silently erase it",
    ],
  } as const;

  return { ...stable, proofDigest: digest(stable) };
}

export async function kaironSupervisedControlCycle(ctx: HandlerContext): Promise<HandlerResult> {
  const legacy = await runLegacyHandler(ctx);

  let proof: Record<string, unknown> = {};
  let ecology: Record<string, unknown> = {};
  let courts: Record<string, unknown> = {};
  let health: Record<string, unknown> = {};
  let portfolio: Record<string, unknown> = {};
  try {
    const [proofRows, ecologyRows, courtRows, healthRows, portfolioRows, recentCourtRuns] = await Promise.all([
      ctx.db.select<Array<Record<string, unknown>>>("v_runtime_proof_summary_v9?select=*&limit=1"),
      ctx.db.select<Array<Record<string, unknown>>>("v_bioecology_dashboard_v9?select=*&limit=1"),
      ctx.db.select<Array<Record<string, unknown>>>("v_conway_court_status_v9?select=*&limit=1"),
      ctx.db.select<Array<Record<string, unknown>>>("v_operating_health_v6?select=*&limit=1"),
      ctx.db.select<Array<Record<string, unknown>>>("v_business_portfolio_summary_v10?select=*&limit=1"),
      ctx.db.select<CourtRunRow[]>("adversarial_court_runs_v9?select=court_key,court_type,passed,created_at&order=created_at.desc&limit=12"),
    ]);
    proof = proofRows.at(0) ?? {};
    ecology = ecologyRows.at(0) ?? {};
    courts = { ...(courtRows.at(0) ?? {}), ...summarizeLatestCourtSuite(recentCourtRuns) };
    health = healthRows.at(0) ?? {};
    portfolio = portfolioRows.at(0) ?? {};
  } catch (error) {
    const unavailable = {
      version: "10.0",
      role: "chief-operator",
      executiveAgent: "Kairon",
      autonomyCeiling: "L2",
      status: "supervisory-evidence-unavailable",
      reason: error instanceof Error ? error.message : String(error),
      failClosed: true,
    };
    return {
      status: legacy.status,
      output: { ...legacy.output, supervisor: unavailable },
      receipt: { ...(legacy.receipt ?? {}), supervisor: unavailable },
    };
  }

  const supervisor = compileSupervisorySnapshot({ legacy: legacy.output, proof, ecology, courts, health, portfolio });

  try {
    await ctx.db.insert("kairon_learning_events_v7", {
      event_key: `${ctx.execution.idempotency_key}:supervisor-v10`,
      niche: "runtime",
      subject_ref: `job_execution:${ctx.execution.id}`,
      truth_level: "governed_source_evidence",
      signal: supervisor.authority.supervisedEconomicL2Open ? 1 : 0,
      observation: supervisor,
      evidence_refs: [
        `job_execution:${ctx.execution.id}`,
        "view:v_runtime_proof_summary_v9",
        "view:v_bioecology_dashboard_v9",
        "view:v_conway_court_status_v9",
        "table:adversarial_court_runs_v9:latest-suite",
        "view:v_operating_health_v6",
        "view:v_business_portfolio_summary_v10",
      ],
    }, "event_key");

    await ctx.db.patch("kairon_state_v7?singleton=eq.true", {
      control_snapshot: {
        legacy: legacy.output.sensed ?? legacy.output,
        supervisor,
      },
    });
  } catch {
    // Supervisory persistence must never turn an otherwise safe maintenance cycle
    // into an unsafe retry loop. The receipt still carries the computed snapshot.
  }

  return {
    status: legacy.status,
    output: {
      ...legacy.output,
      supervisor,
    },
    receipt: {
      ...(legacy.receipt ?? {}),
      supervisorDigest: supervisor.proofDigest,
      supervisorVersion: supervisor.version,
      supervisorRole: supervisor.role,
      operatingProjects: supervisor.portfolio.operatingProjects,
      incubatingProjects: supervisor.portfolio.incubatingProjects,
      foundryCandidates: supervisor.portfolio.foundryCandidates,
      supervisedEconomicL2Open: supervisor.authority.supervisedEconomicL2Open,
      courtEvidenceReady: supervisor.authority.courtEvidenceReady,
      adaptationMode: supervisor.adaptation.mode,
    },
  };
}
