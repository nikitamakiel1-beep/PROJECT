import test from "node:test";
import assert from "node:assert/strict";
import { authorizeBearer, bearerToken } from "./auth.js";

test("extracts bearer token", () => {
  assert.equal(bearerToken("Bearer secret"), "secret");
  assert.equal(bearerToken(["Bearer abc"]), "abc");
});

test("rejects malformed authorization", () => {
  assert.equal(bearerToken("Basic abc"), null);
  assert.equal(bearerToken(undefined), null);
  assert.equal(authorizeBearer("Bearer wrong", "right"), false);
});

test("accepts exact bearer secret", () => {
  assert.equal(authorizeBearer("Bearer right", "right"), true);
});
