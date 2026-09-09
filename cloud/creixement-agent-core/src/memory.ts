import type { TruthLevel } from "./types.js";

export interface KnowledgeItem {
  id: string;
  namespace: string;
  subject: string;
  predicate: string;
  object: unknown;
  truthLevel: TruthLevel;
  sourceRefs: string[];
  observedAt: string;
  validFrom?: string;
  validUntil?: string;
  authority: number;
  freshness: number;
  confidence: number;
  sensitivity: "public" | "internal" | "restricted";
  rightsStatus: "permitted" | "restricted" | "unknown" | "blocked";
  digest?: string;
  supersedes?: string[];
  contradictionGroup?: string;
}

const TRUTH_RANK: Record<TruthLevel, number> = {
  verified_external_outcome: 7,
  executed_connector_receipt: 6,
  governed_source_evidence: 5,
  human_approved_decision: 4,
  evidence_backed_model_inference: 3,
  hypothesis: 2,
  generated_narrative: 1,
};

const clamp01 = (value: number): number => Math.max(0, Math.min(1, value));

export function knowledgeScore(item: KnowledgeItem, now = new Date()): number {
  if (item.rightsStatus === "blocked") return Number.NEGATIVE_INFINITY;
  if (item.validUntil && new Date(item.validUntil).getTime() <= now.getTime()) return Number.NEGATIVE_INFINITY;
  const ageDays = Math.max((now.getTime() - new Date(item.observedAt).getTime()) / 86_400_000, 0);
  const ageDecay = 1 / (1 + ageDays / 30);
  return (
    TRUTH_RANK[item.truthLevel] * 1.5 +
    clamp01(item.authority) * 1.2 +
    clamp01(item.freshness) * 1.0 +
    clamp01(item.confidence) * 0.8 +
    ageDecay * 0.5
  );
}

export function rankKnowledge(items: KnowledgeItem[], now = new Date()): KnowledgeItem[] {
  return [...items]
    .filter((item) => knowledgeScore(item, now) !== Number.NEGATIVE_INFINITY)
    .sort((a, b) => knowledgeScore(b, now) - knowledgeScore(a, now) || a.id.localeCompare(b.id));
}

export function resolvePreferredKnowledge(items: KnowledgeItem[], now = new Date()): KnowledgeItem | null {
  const ranked = rankKnowledge(items, now);
  return ranked[0] ?? null;
}

export function maySupersede(candidate: KnowledgeItem, existing: KnowledgeItem, now = new Date()): boolean {
  if (candidate.subject !== existing.subject || candidate.predicate !== existing.predicate) return false;
  if (candidate.rightsStatus !== "permitted") return false;
  if (existing.validUntil && new Date(existing.validUntil).getTime() <= now.getTime()) return true;

  const candidateTruth = TRUTH_RANK[candidate.truthLevel];
  const existingTruth = TRUTH_RANK[existing.truthLevel];
  if (candidateTruth < existingTruth) return false;
  if (candidateTruth > existingTruth) return true;

  return knowledgeScore(candidate, now) > knowledgeScore(existing, now);
}

export function contradictionGroups(items: KnowledgeItem[]): Map<string, KnowledgeItem[]> {
  const groups = new Map<string, KnowledgeItem[]>();
  for (const item of items) {
    const key = item.contradictionGroup ?? `${item.namespace}:${item.subject}:${item.predicate}`;
    const current = groups.get(key) ?? [];
    current.push(item);
    groups.set(key, current);
  }
  return groups;
}
