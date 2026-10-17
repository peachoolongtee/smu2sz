// "You're covered!" on the Home is the server's decision (17 Oct: day 77 of a take said "All clear" beside cash ¥145k under the minimum).
// Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { homeCovered } from "../lib/home-covered.ts";

const here = dirname(fileURLToPath(import.meta.url));
const rec = (name) => JSON.parse(readFileSync(join(here, "..", "mocks", "home_v2", name), "utf8")).en;

// The day-77 state as the server used to send it: no plan to run, no unsafe day ahead (the ¥420k due today closes the day above the
// minimum), yet the bank holds less than the minimum.
const day77 = { next_action: null, cash: { first_breach_day: null, below_reserve_today: false } };

test("the server's word wins over every flag the page could read", () => {
  assert.equal(homeCovered({ ...day77, cash: { ...day77.cash, covered: true } }, { covered: false }), false);
  assert.equal(homeCovered(day77, { covered: false }), false);
  assert.equal(homeCovered({ next_action: { alert_id: "A" }, cash: { first_breach_day: 12, below_reserve_today: false } }, { covered: true }), true);
});

test("without the action's word, the cash block's own `covered` decides", () => {
  assert.equal(homeCovered({ ...day77, cash: { ...day77.cash, covered: false } }, {}), false);
  assert.equal(homeCovered({ ...day77, cash: { ...day77.cash, covered: true } }, {}), true);
});

test("an older recording without either word: no plan, no unsafe day and not under the minimum today", () => {
  assert.equal(homeCovered(day77, {}), true); // what such a server said: why it now sends its own word
  assert.equal(homeCovered({ ...day77, cash: { ...day77.cash, below_reserve_today: true } }, {}), false);
  assert.equal(homeCovered({ ...day77, cash: { ...day77.cash, first_breach_day: 42 } }, {}), false);
  assert.equal(homeCovered({ ...day77, next_action: { alert_id: "A" } }, {}), false);
});

test("the recorded Home states decide as they did: covered only once nothing needs funding", () => {
  const covered = Object.fromEntries(
    ["day0", "offer", "deal", "after_fund", "after", "day34", "pending"].map((n) => {
      const h = rec(`home_${n}.json`);
      return [n, homeCovered(h, h.home_v2.action)];
    }),
  );
  assert.deepEqual(covered, { day0: false, offer: false, deal: true, after_fund: true, after: true, day34: false, pending: false });
});
