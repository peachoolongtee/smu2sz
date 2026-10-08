// The strategy MVP's build-time flag and its mock recordings (lib/config.ts, lib/mock/strategy-pick.ts, mocks/strategy/*.json). Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { pickByDay } from "../lib/mock/strategy-pick.ts";

const web = (p) => fileURLToPath(new URL(`../${p}`, import.meta.url));
const source = (p) => readFileSync(web(p), "utf8");
const recording = (name) => JSON.parse(source(`mocks/strategy/${name}.json`));

async function flagWith(value) {
  const before = process.env.NEXT_PUBLIC_STRATEGY_MVP;
  if (value === undefined) delete process.env.NEXT_PUBLIC_STRATEGY_MVP;
  else process.env.NEXT_PUBLIC_STRATEGY_MVP = value;
  try {
    return (await import(`../lib/config.ts?flag=${String(value)}`)).STRATEGY_MVP;
  } finally {
    if (before === undefined) delete process.env.NEXT_PUBLIC_STRATEGY_MVP;
    else process.env.NEXT_PUBLIC_STRATEGY_MVP = before;
  }
}

test("STRATEGY_MVP is on only for NEXT_PUBLIC_STRATEGY_MVP=1 (unset, 0 and true are off)", async () => {
  assert.equal(await flagWith(undefined), false);
  assert.equal(await flagWith("0"), false);
  assert.equal(await flagWith("true"), false);
  assert.equal(await flagWith("1"), true);
});

test("every new client call is behind the flag at its call site, so the default build never reads the routes", () => {
  for (const [file, call] of [
    ["app/cash/page.tsx", "getPriceCurve"],
    ["app/receivables/page.tsx", "getReceivablesWorth"],
    ["app/page.tsx", "getReceivablesWorth"],
  ]) {
    const uses = source(file).split("\n").filter((line) => line.includes(`${call}(`));
    assert.ok(uses.length > 0, `${file} no longer calls ${call}`);
    for (const line of uses) assert.match(line, /STRATEGY_MVP \? await /, `${file}: ${call} must be called behind STRATEGY_MVP: ${line.trim()}`);
  }
});

test("the recordings are chosen by the clock's day: the opening books before the news day, day 34's from it", () => {
  assert.equal(pickByDay(0, 34, "day0", "day34"), "day0");
  assert.equal(pickByDay(33, 34, "day0", "day34"), "day0");
  assert.equal(pickByDay(34, 34, "day0", "day34"), "day34");
  assert.equal(pickByDay(80, 34, "day0", "day34"), "day34");
});

test("the mock handlers choose with the same day as the funding plan (home.NEWS_DAY) and the four recordings are the right days", () => {
  const handlers = source("lib/mock/handlers.ts");
  assert.match(handlers, /getPriceCurve[\s\S]*?pickByDay\(home\.mockClock\(\)\.day, home\.NEWS_DAY, priceCurveDay0Json, priceCurveDay34Json\)/);
  assert.match(handlers, /getReceivablesWorth[\s\S]*?pickByDay\(home\.mockClock\(\)\.day, home\.NEWS_DAY, worthDay0Json, worthDay34Json\)/);
  assert.equal(recording("price_curve_day0").day, 0);
  assert.equal(recording("price_curve_day34").day, 34);
  assert.equal(recording("worth_day0").day, 0);
  assert.equal(recording("worth_day34").day, 34);
});

test("the recordings carry the server's strings the pages show, and no 'day N' in them", () => {
  for (const name of ["price_curve_day0", "price_curve_day34"]) {
    const curve = recording(name);
    assert.match(curve.sentence, /%/);
    assert.doesNotMatch(curve.sentence, /\bday \d/i);
  }
  for (const name of ["worth_day0", "worth_day34"]) {
    const worth = recording(name);
    assert.ok(worth.rows.length > 0);
    assert.ok(worth.ranking_note && worth.top_action);
    for (const row of worth.rows) {
      for (const text of [row.action_sentence, row.net_saving_text, row.gross_saving_display]) assert.doesNotMatch(text, /\bday \d/i);
      assert.ok(["call_now", "escalate", "reminder", "offer_early_pay", "finance", "wait"].includes(row.action));
    }
  }
  assert.equal(recording("worth_day34").rows[0].action, "call_now");
});
