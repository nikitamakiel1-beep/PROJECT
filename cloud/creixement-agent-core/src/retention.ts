export type RetentionClassification = "ephemeral" | "operational" | "commercial" | "financial" | "legal" | "evidence";

export interface RetentionPolicy {
  classification: RetentionClassification;
  retainDays: number | null;
  archiveAfterDays?: number;
  deleteAllowed: boolean;
  requireApprovalForDeletion: boolean;
}

export interface RetainedRecord {
  id: string;
  classification: RetentionClassification;
  createdAt: string;
  lastUsedAt?: string;
  legalHold: boolean;
  governedEvidence: boolean;
}

export interface RetentionDecision {
  action: "keep" | "archive" | "delete_candidate" | "hold";
  requiresApproval: boolean;
  reason: string;
}

export function decideRetention(
  record: RetainedRecord,
  policy: RetentionPolicy,
  now = new Date(),
): RetentionDecision {
  if (record.classification !== policy.classification) throw new Error("Retention policy classification mismatch");
  if (record.legalHold || record.governedEvidence && !policy.deleteAllowed) {
    return { action: "hold", requiresApproval: false, reason: "Record is protected by legal hold or governed-evidence policy." };
  }

  const referenceMs = Date.parse(record.lastUsedAt ?? record.createdAt);
  if (!Number.isFinite(referenceMs)) throw new Error("Invalid retention timestamp");
  const ageDays = Math.max((now.getTime() - referenceMs) / 86_400_000, 0);

  if (policy.archiveAfterDays !== undefined && ageDays >= policy.archiveAfterDays) {
    if (policy.retainDays === null || ageDays < policy.retainDays) {
      return { action: "archive", requiresApproval: false, reason: "Record crossed archive threshold but remains within retention period." };
    }
  }

  if (policy.retainDays !== null && ageDays >= policy.retainDays) {
    if (!policy.deleteAllowed) return { action: "hold", requiresApproval: false, reason: "Retention threshold reached but deletion is prohibited." };
    return {
      action: "delete_candidate",
      requiresApproval: policy.requireApprovalForDeletion,
      reason: "Retention threshold reached; deletion candidate created rather than deleting silently.",
    };
  }

  return { action: "keep", requiresApproval: false, reason: "Record remains inside the active retention window." };
}
