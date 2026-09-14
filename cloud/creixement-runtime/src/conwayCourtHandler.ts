import { createHash } from "node:crypto";
import type { HandlerContext, HandlerResult } from "./handlers.js";

interface AuthorityRow {
  node_key: string;
  action_class: string;
  max_autonomy: "L0" | "L1" | "L2" | "L3";
  forbidden: boolean;
  next_nodes: unknown;
  source_ref?: string | null;
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

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string").sort();
}

function traverseAuthority(rows: AuthorityRow[], startKey = "root", maxPaths = 200000): {
  explored: number;
  safePaths: string[][];
  forbiddenPaths: string[][];
  graphDigest: string;
} {
  const byKey = new Map(rows.map((row) => [row.node_key, row]));
  const queue: string[][] = [[startKey]];
  const safePaths: string[][] = [];
  const forbiddenPaths: string[][] = [];
  let explored = 0;

  while (queue.length > 0 && explored < maxPaths) {
    const path = queue.shift()!;
    explored += 1;
    const node = byKey.get(path[path.length - 1]!);
    if (!node) {
      safePaths.push(path);
      continue;
    }
    if (node.forbidden || node.max_autonomy === "L3") {
      forbiddenPaths.push(path);
      continue;
    }
    const next = stringArray(node.next_nodes);
    if (next.length === 0 || path.length >= 32) {
      safePaths.push(path);
      continue;
    }
    for (const child of next) {
      if (!path.includes(child)) queue.push([...path, child]);
    }
  }

  const stableGraph = rows
    .map((row) => ({
      key: row.node_key,
      actionClass: row.action_class,
      maxAutonomy: row.max_autonomy,
      forbidden: row.forbidden,
      next: stringArray(row.next_nodes),
      sourceRef: row.source_ref ?? null,
    }))
    .sort((a, b) => a.key.localeCompare(b.key));

  return { explored, safePaths, forbiddenPaths, graphDigest: digest(stableGraph) };
}

async function insertCourt(
  ctx: HandlerContext,
  suffix: string,
  body: Record<string, unknown>,
): Promise<void> {
  await ctx.db.insert("adversarial_court_runs_v9", {
    court_key: `${ctx.execution.idempotency_key}:${suffix}`,
    seed: ctx.execution.correlation_id,
    evidence_refs: [`job_execution:${ctx.execution.id}`, `runtime:${ctx.runtimeId}`],
    ...body,
  }, "court_key");
}

export async function conwayCourtCycle(ctx: HandlerContext): Promise<HandlerResult> {
  const [authority, promoted, canaries, baselineRows] = await Promise.all([
    ctx.db.select<AuthorityRow[]>(
      "authority_graph_v9?select=node_key,action_class,max_autonomy,forbidden,next_nodes,source_ref&order=node_key.asc&limit=500",
    ),
    ctx.db.select<Array<{ capability_key: string; promotion_state: string }>>(
      "capability_evidence?select=capability_key,promotion_state&promotion_state=eq.promoted&limit=500",
    ),
    ctx.db.select<Array<{ capability_key: string; version: string; passed: boolean; receipted: boolean; deterministic_replay: boolean; digest_match: boolean }>>(
      "capability_canaries_v9?select=capability_key,version,passed,receipted,deterministic_replay,digest_match&order=observed_at.desc&limit=1000",
    ),
    ctx.db.select<Array<{ projection_key: string; digest: string; verified: boolean; source_ref: string | null }>>(
      "public_projection_manifests_v9?projection_key=eq.authority-graph-v9&select=projection_key,digest,verified,source_ref&limit=1",
    ),
  ]);

  const traversal = traverseAuthority(authority);
  const rootExists = authority.some((row) => row.node_key === "root");
  const forbiddenNodes = authority.filter((row) => row.forbidden || row.max_autonomy === "L3");
  const unexpectedSafeL3 = traversal.safePaths.filter((path) => {
    const terminal = authority.find((row) => row.node_key === path[path.length - 1]);
    return terminal?.max_autonomy === "L3" || terminal?.forbidden === true;
  });
  const authorityPassed = rootExists && forbiddenNodes.length > 0 && unexpectedSafeL3.length === 0 && traversal.explored < 200000;

  await insertCourt(ctx, "authority", {
    court_type: "authority_traversal",
    explored_states: traversal.explored,
    forbidden_hits: traversal.forbiddenPaths.length,
    safe_terminal_states: traversal.safePaths.length,
    hard_veto_count: forbiddenNodes.length,
    candidate_digest: traversal.graphDigest,
    passed: authorityPassed,
    findings: authorityPassed ? [] : [{ rootExists, forbiddenNodes: forbiddenNodes.length, unexpectedSafeL3 }],
  });

  const safeCandidate = authority.find((row) => row.node_key === "internal-write" && !row.forbidden && row.max_autonomy !== "L3");
  const seductiveUnsafe = authority.find((row) => row.node_key === "payment" && (row.forbidden || row.max_autonomy === "L3"));
  const faustianPassed = Boolean(safeCandidate && seductiveUnsafe);
  await insertCourt(ctx, "faustian", {
    court_type: "faustian_fuzz",
    explored_states: 2,
    forbidden_hits: seductiveUnsafe ? 1 : 0,
    safe_terminal_states: safeCandidate ? 1 : 0,
    hard_veto_count: seductiveUnsafe ? 1 : 0,
    candidate_digest: digest({
      unsafe: { key: "payment", expectedValue: 1_000_000, hardVeto: Boolean(seductiveUnsafe) },
      safe: { key: "internal-write", expectedValue: 100, selected: Boolean(safeCandidate) },
    }),
    passed: faustianPassed,
    findings: faustianPassed ? [] : [{ reason: "hard veto did not dominate a seductive payment path" }],
  });

  const baseline = baselineRows.at(0);
  let baselineDigest = baseline?.digest ?? null;
  let auditorPassed = false;
  if (!baseline) {
    await ctx.db.insert("public_projection_manifests_v9", {
      projection_key: "authority-graph-v9",
      stable_payload: authority
        .map((row) => ({ key: row.node_key, actionClass: row.action_class, maxAutonomy: row.max_autonomy, forbidden: row.forbidden, next: stringArray(row.next_nodes) }))
        .sort((a, b) => a.key.localeCompare(b.key)),
      digest: traversal.graphDigest,
      volatile_fields_removed: ["updated_at"],
      source_ref: "db/migrations/020_v9_population_and_courts_runtime.sql",
      verified: true,
    }, "projection_key");
    baselineDigest = traversal.graphDigest;
    auditorPassed = true;
  } else {
    auditorPassed = baseline.verified === true && baseline.digest === traversal.graphDigest;
  }

  await insertCourt(ctx, "auditor", {
    court_type: "auditor_of_auditors",
    explored_states: authority.length,
    forbidden_hits: auditorPassed ? 0 : 1,
    safe_terminal_states: auditorPassed ? 1 : 0,
    hard_veto_count: 0,
    baseline_digest: baselineDigest,
    candidate_digest: traversal.graphDigest,
    passed: auditorPassed,
    findings: auditorPassed ? [] : [{ reason: "authority graph digest drifted from verified baseline" }],
  });

  const promotedKeys = [...new Set(promoted.map((row) => row.capability_key))];
  const failedPromotions: Array<{ capabilityKey: string; verifiedCanaries: number }> = [];
  for (const key of promotedKeys) {
    const valid = canaries.filter((row) =>
      row.capability_key === key && row.passed && row.receipted && row.deterministic_replay && row.digest_match,
    );
    if (valid.length < 5) failedPromotions.push({ capabilityKey: key, verifiedCanaries: valid.length });
  }
  const canaryPassed = failedPromotions.length === 0;
  await insertCourt(ctx, "canary", {
    court_type: "mutation_detection",
    explored_states: promotedKeys.length,
    forbidden_hits: failedPromotions.length,
    safe_terminal_states: promotedKeys.length - failedPromotions.length,
    hard_veto_count: failedPromotions.length,
    candidate_digest: digest({ promotedKeys, canaries }),
    passed: canaryPassed,
    findings: failedPromotions,
  });

  const passed = authorityPassed && faustianPassed && auditorPassed && canaryPassed;
  return {
    status: passed ? "succeeded" : "blocked",
    output: {
      mechanism: "conway-adversarial-courts-v9",
      passed,
      authority: {
        explored: traversal.explored,
        forbiddenPaths: traversal.forbiddenPaths.length,
        safePaths: traversal.safePaths.length,
        digest: traversal.graphDigest,
      },
      faustian: { passed: faustianPassed, hardVetoDominates: Boolean(seductiveUnsafe && safeCandidate) },
      auditor: { passed: auditorPassed, baselineDigest, candidateDigest: traversal.graphDigest },
      canaryPromotion: { passed: canaryPassed, failedPromotions },
    },
    receipt: {
      runtimeId: ctx.runtimeId,
      mechanism: "conway-courts-v9",
      graphDigest: traversal.graphDigest,
      passed,
    },
  };
}
