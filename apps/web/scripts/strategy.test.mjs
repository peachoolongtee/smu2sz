// The strategy MVP's build-time flag and its mock recordings (lib/config.ts, lib/mock/strategy-pick.ts, mocks/strategy/*.json). Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { pickByDay, pickByStory } from "../lib/mock/strategy-pick.ts";

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

test("after the day-34 cure is approved the post-approval recording is served; before it, day 34's; before day 34, the opening books'", () => {
  const pick = (day, approved) => pickByStory(day, 34, approved, "day0", "day34", "after");
  assert.equal(pick(0, false), "day0");
  assert.equal(pick(33, false), "day0");
  assert.equal(pick(34, false), "day34");
  assert.equal(pick(34, true), "after");
  assert.equal(pick(80, true), "after");
  // An approval cannot predate the news: the cure exists only from day 34.
  assert.equal(pick(10, true), "day0");
});

test("the mock handlers choose with the home mock's own condition (the clock's day and cureStage() === 'approved') and the recordings are the right days", () => {
  const handlers = source("lib/mock/handlers.ts");
  assert.match(handlers, /pickByStory\(home\.mockClock\(\)\.day, home\.NEWS_DAY, home\.cureStage\(\) === "approved", atDay0, atNews, afterApproval\)/);
  assert.match(handlers, /getPriceCurve[\s\S]*?strategyRecording<PriceCurveView>\(priceCurveDay0Json, priceCurveDay34Json, priceCurveDay34AfterJson\)/);
  assert.match(handlers, /getReceivablesWorth[\s\S]*?strategyRecording<ReceivablesWorthView>\(worthDay0Json, worthDay34Json, worthDay34AfterJson\)/);
  assert.match(handlers, /getEnvelope[\s\S]*?strategyRecording<EnvelopeView>\(envelopeDay0Json, envelopeDay34Json, envelopeDay34AfterJson\)/);
  assert.match(source("lib/mock/home.ts"), /s\.stage === "approved" \? "after"/);
  for (const name of ["price_curve", "worth", "envelope"]) {
    assert.equal(recording(`${name}_day0`).day, 0);
    assert.equal(recording(`${name}_day34`).day, 34);
    assert.equal(recording(`${name}_day34_after`).day, 34);
  }
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

test("the envelope recordings are BUYER-1's, carry the server's sentences and the zone, and say no 'day N'", () => {
  for (const name of ["envelope_day0", "envelope_day34", "envelope_day34_after"]) {
    const e = recording(name);
    assert.equal(e.buyer_id, "BUYER-1");
    assert.equal(e.refused, null);
    assert.ok(e.packages.length > 0 && e.levers.length > 0 && e.zone.length === 13, name);
    for (const text of [e.primary, e.reason, e.money]) assert.doesNotMatch(text, /\bday \d/i);
    assert.equal(e.computed_in_seconds, 0);
  }
  const day0 = recording("envelope_day0");
  assert.match(day0.primary, /55-day/);
  assert.match(day0.primary, /0\.85%/);
  assert.equal(day0.levers.length, 6);
  // The lever table, the package lines and the zone rows are the server's strings: the card composes none of them.
  assert.deepEqual(day0.levers.map((l) => l.maximum_display), ["45 days", "55 days", "55 days, price up 0.30%", "0.70% on ¥420,000.00", "0.85% on ¥257,200.00", "1.25%"]);
  assert.equal(day0.levers[0].next_step_sentence, "50 days: not approved; its funding cannot run today");
  assert.equal(day0.levers[0].wall_words, "your budget for what you give buyers");
  assert.ok(day0.packages.some((p) => p.summary === "55-day terms · price up 0.25% · rebate 0.60%"));
  assert.deepEqual(day0.zone.slice(0, 5).map((z) => z.lowest_price_words), ["no price step needed", "no price step needed", "no price step needed", "no price step needed", "0.10%"]);
  assert.equal(day0.zone.at(-1).lowest_price_words, "none works");
  for (const name of ["envelope_day0", "envelope_day34", "envelope_day34_after"]) {
    const e = recording(name);
    for (const l of e.levers) for (const text of [l.maximum_display, l.wall_words ?? "", l.next_step_sentence]) assert.doesNotMatch(text, /\bday \d|[A-Z]{2,}_[A-Z]+/);
    for (const p of e.packages) assert.doesNotMatch(p.summary, /\bday \d/);
  }
  // The approval changes the answer: the post-approval sentence is not day 34's.
  assert.notEqual(recording("envelope_day34_after").primary, recording("envelope_day34").primary);
  assert.notEqual(recording("price_curve_day34_after").sentence, recording("price_curve_day34").sentence);
});

test("the Deals card renders the server's lever, package and zone strings and composes none", () => {
  const card = source("components/deals/before-they-ask.tsx");
  for (const field of ["maximum_display", "wall_words", "next_step_sentence", "summary", "lowest_price_words"]) assert.match(card, new RegExp(`\\.${field}\\b`), field);
  assert.doesNotMatch(card, /biz\.strategy\.envelope\.(days|terms|maxWithPrice|priceUp|earlyPay|earlyOn|rebate|notApproved|noStep)\b/);
  assert.doesNotMatch(source("lib/live/index.ts"), /status === 422/);
});

test("the envelope call is behind the flag at its call site", () => {
  const uses = source("components/deals/before-they-ask.tsx").split("\n").filter((line) => line.includes("getEnvelope("));
  assert.ok(uses.length > 0);
  for (const line of uses) assert.match(line, /STRATEGY_MVP/, line.trim());
});
