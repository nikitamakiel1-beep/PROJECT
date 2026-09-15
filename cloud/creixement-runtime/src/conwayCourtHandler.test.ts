import test from "node:test";
import assert from "node:assert/strict";
import { traverseAuthority, type AuthorityRow } from "./conwayCourtHandler.js";

const baseGraph: AuthorityRow[] = [
  { node_key: "root", action_class: "sense_and_decide", max_autonomy: "L0", forbidden: false, next_nodes: ["internal-write", "external-boundary"] },
  { node_key: "internal-write", action_class: "internal_reversible_write", max_autonomy: "L2", forbidden: false, next_nodes: [] },
  { node_key: "external-boundary", action_class: "external_boundary", max_autonomy: "L1", forbidden: false, next_nodes: ["payment"] },
  { node_key: "payment", action_class: "payment_authority", max_autonomy: "L3", forbidden: true, next_nodes: [] },
];

test("authority traversal classifies known L3 paths as forbidden", () => {
  const result = traverseAuthority(baseGraph);
  assert.equal(result.unknownPaths.length, 0);
  assert.equal(result.forbiddenPaths.length, 1);
  assert.deepEqual(result.forbiddenPaths[0], ["root", "external-boundary", "payment"]);
  assert.deepEqual(result.safePaths[0], ["root", "internal-write"]);
});

test("dangling authority edges are unknown, never safe terminals", () => {
  const graph = baseGraph.map((row) => ({ ...row }));
  graph[0] = { ...graph[0]!, next_nodes: ["internal-write", "missing-boundary"] };
  const result = traverseAuthority(graph);
  assert.equal(result.unknownPaths.length, 1);
  assert.deepEqual(result.unknownPaths[0], ["root", "missing-boundary"]);
  assert.equal(result.safePaths.some((path) => path.includes("missing-boundary")), false);
});

test("missing root is represented as an unknown path", () => {
  const result = traverseAuthority(baseGraph.filter((row) => row.node_key !== "root"));
  assert.deepEqual(result.unknownPaths, [["root"]]);
  assert.equal(result.safePaths.length, 0);
});
