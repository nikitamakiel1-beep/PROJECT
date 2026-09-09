import test from "node:test";
import assert from "node:assert/strict";
import { authorizeBearer, bearerToken } from "./auth.js";

test("extracts bearer token", () => {
  assert.equal(bearerToken("Bearer abc123"), "abc123");
  assert.equal(bearerToken(undefined), null);
  assert.equal(bearerToken("Basic abc123"), null);
});

test("authorizes only exact bearer token", () => {
  assert.equal(authorizeBearer("Bearer secret", "secret"), true);
  assert.equal(authorizeBearer("Bearer secreT", "secret"), false);
  assert.equal(authorizeBearer(undefined, "secret"), false);
});
