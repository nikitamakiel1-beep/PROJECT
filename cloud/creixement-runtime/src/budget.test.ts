import test from "node:test";
import assert from "node:assert/strict";
import { startOfDayInTimeZone } from "./budget.js";

test("Madrid summer budget day starts at 22:00 UTC on previous date", () => {
  const now = new Date("2026-07-15T12:00:00Z");
  assert.equal(startOfDayInTimeZone(now, "Europe/Madrid").toISOString(), "2026-07-14T22:00:00.000Z");
});

test("Madrid winter budget day starts at 23:00 UTC on previous date", () => {
  const now = new Date("2026-12-15T12:00:00Z");
  assert.equal(startOfDayInTimeZone(now, "Europe/Madrid").toISOString(), "2026-12-14T23:00:00.000Z");
});
