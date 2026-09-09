import { createHash } from "node:crypto";

export type LineageNodeKind = "source" | "normalized" | "analysis" | "action" | "receipt" | "deliverable" | "outcome";

export interface LineageNode {
  id: string;
  kind: LineageNodeKind;
  contentDigest: string;
  createdAt: string;
  sourceRef?: string;
  truthLevel?: string;
  metadata?: Record<string, unknown>;
}

export interface LineageEdge {
  parentId: string;
  childId: string;
  relation: "derived_from" | "executed_as" | "verified_by" | "rendered_as" | "supersedes";
}

export function sha256(value: unknown): string {
  return createHash("sha256").update(typeof value === "string" ? value : JSON.stringify(value)).digest("hex");
}

export function validateLineage(nodes: LineageNode[], edges: LineageEdge[]): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  const ids = new Set(nodes.map((node) => node.id));
  if (ids.size !== nodes.length) errors.push("duplicate lineage node id");

  for (const node of nodes) {
    if (!/^[0-9a-f]{64}$/i.test(node.contentDigest)) errors.push(`invalid content digest: ${node.id}`);
  }
  for (const edge of edges) {
    if (!ids.has(edge.parentId)) errors.push(`unknown parent node: ${edge.parentId}`);
    if (!ids.has(edge.childId)) errors.push(`unknown child node: ${edge.childId}`);
    if (edge.parentId === edge.childId) errors.push(`self lineage edge: ${edge.parentId}`);
  }

  const children = new Map<string, string[]>();
  for (const edge of edges) {
    const list = children.get(edge.parentId) ?? [];
    list.push(edge.childId);
    children.set(edge.parentId, list);
  }
  const visiting = new Set<string>();
  const visited = new Set<string>();
  const visit = (id: string): void => {
    if (visited.has(id)) return;
    if (visiting.has(id)) {
      errors.push(`lineage cycle detected at ${id}`);
      return;
    }
    visiting.add(id);
    for (const child of children.get(id) ?? []) visit(child);
    visiting.delete(id);
    visited.add(id);
  };
  for (const id of ids) visit(id);

  return { valid: errors.length === 0, errors };
}

export function lineageRoots(nodes: LineageNode[], edges: LineageEdge[]): LineageNode[] {
  const childIds = new Set(edges.map((edge) => edge.childId));
  return nodes.filter((node) => !childIds.has(node.id));
}
