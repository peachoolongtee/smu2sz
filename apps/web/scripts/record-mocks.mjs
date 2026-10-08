// Records apps/web/mocks/*.json from a running API. Run: pnpm mocks:record   (or: node scripts/record-mocks.mjs --api http://localhost:8011)
//
//   cd services/api && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8011
//
// Mock-authoring tooling only (never imported by the app). It resets the books and replays the sequences the demo
// stepper (lib/demo.ts), the pages and the chat (lib/chat-prompts.ts) perform, through the SAME client code the browser
// uses in live mode (lib/api.ts -> lib/live/*.ts, loaded straight from the TypeScript by Node's type stripping through
// scripts/ts-resolve-hook.mjs), so every file holds exactly what the live adapters hand to the pages. Nothing here
// computes, formats or edits money: a mock file is the API's own answer.
//
// Output is deterministic: API key order, 2-space indent, trailing newline. The only values changed after recording are
// listed under NORMALISED below.
//
// NORMALISED (the API returns these differently on every run; everything else, including hashes and ids, is kept):
//   - whatif_presets.json: every entry's `compute_ms` -> 0 and `cached` -> false (timing and cache state of the call).
//   - the commitment id (CMT-<16 hex>) and its nonce, which the API draws at random for every deal: replaced by one fixed
//     id and nonce wherever they appear (negotiation_accept.json, ops.json, home_act.json, home_goahead.json).
//   - nl_script.json and state_after_fund.json: the NL-<16 hex> operation and lot ids, which the API derives from a random
//     per-session nonce, become fixed ids by order of first appearance; nl_script.json, home_reconciliation_day34.json and the two
//     home ledgers (home_ledger_day34.json, home_ledger_approved.json) are
//     chained again by first appearance (entry_hash / prev_hash re-derived, chain_head_hash fixed) for the same reason.
//   - the early-payment alert id (ALERT-EARLYPAY-<12 hex>, derived from the offer's random id; raised on the books where the day-2 receipt
//     never came): one fixed id.
//   - the entry_hash / prev_hash of the operations in negotiation_accept.json, home_act.json, home_goahead.json, home_approve.json
//     and home_approve_chat.json: the
//     server's chain includes that commitment id, so it differs on every run. They are re-derived (sha256 over the op's
//     own seq, id, kind, status and the previous hash) so the chain stays internally consistent and repeatable. Hashes in
//     every other file (the chat script, for one) are deterministic and are kept exactly as recorded.
//   - strategy/*.json (only with --strategy): `computed_in_seconds` -> 0 (the time the call took; a cache hit differs from a miss).
//
// --strategy records ONLY apps/web/mocks/strategy/*.json and exits; no other file is written and the assertions below are not run:
//   price_curve_{day0,day34,day34_after}.json   GET /cash/price-curve         (lang=en)
//   worth_{day0,day34,day34_after}.json         GET /receivables/worth        (lang=en)
//   envelope_{day0,day34,day34_after}.json      GET /buyers/BUYER-1/envelope  (lang=en, zone=1 so the table is present; the mock drops it when not asked)
// at the opening books, at day 34 (the late invoice, the reserve alert open) and at day 34 AFTER the owner has approved the alert's
// cure (the step that reaches home_summary_after.json): the mock serves the "_after" files in the condition the home mock serves its
// post-approval summary (lib/mock/home.ts cureStage() === "approved"; lib/mock/strategy-pick.ts pickByStory). The API needs
// FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 and the other flags as above; the first envelope read of a
// set of books takes several seconds:
//   cd services/api && FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8016
//   node scripts/record-mocks.mjs --api http://localhost:8016 --strategy
//
// Verified by running the recorder twice on the same API and on two fresh APIs: `git status --short apps/web/mocks` is empty.

import { createHash } from "node:crypto";
import { register } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
if (process.argv.includes("--help")) {
  console.log("usage: node scripts/record-mocks.mjs [--api http://localhost:8011] [--out apps/web/mocks] [--strategy]\n(start the API first, see the header of this file; never use port 8000)");
  process.exit(0);
}
const API = arg("--api", "http://localhost:8011").replace(/\/+$/, "");
const OUT = resolve(arg("--out", join(here, "..", "mocks")));
const STRATEGY = process.argv.includes("--strategy");
const OWNER_TOKEN = "demo-owner-token";
const BANK = { "X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key" };

register("./ts-resolve-hook.mjs", import.meta.url);
process.env.NEXT_PUBLIC_API_URL = API;
process.env.NEXT_PUBLIC_API_MODE = "live";
const { setOwnerToken } = await import("../lib/auth.ts");
const { live } = await import("../lib/live/index.ts");
const { DEMO_STEPS } = await import("../lib/demo.ts");
const { demoStore, clearDemo } = await import("../lib/demo-store.ts");
const { promptsFor } = await import("../lib/chat-prompts.ts");
setOwnerToken(OWNER_TOKEN);

mkdirSync(OUT, { recursive: true });
const written = [];
const sha = (t) => createHash("sha256").update(t).digest("hex");
const FIXED_CMT = `CMT-${sha("recorded commitment").slice(0, 16)}`;
const FIXED_NONCE = sha("recorded nonce").slice(0, 32);
const RECHAIN = new Set(["negotiation_accept.json", "home_act.json", "home_act_day0.json", "home_goahead.json", "home_approve.json", "home_approve_chat.json"]);

// Files whose operations are chained by first appearance (every other chained file uses `rechain` below): the chat script, whose
// operation ids and commitment ids come from a per-session random nonce, and the day-34 reconciliation (one receipt).
const RECHAIN_BY_APPEARANCE = new Set(["nl_script.json", "home_reconciliation_day34.json", "home_reconciliation_day34_half.json", "home_ledger_day34.json", "home_ledger_approved.json"]);
const nlIds = new Map(); // NL-<16 hex> operation / lot ids, which the API derives from a random session nonce -> a fixed id by first appearance

function rechainByAppearance(name, root) {
  const memo = new Map();
  const collect = (node) => {
    if (Array.isArray(node)) node.forEach(collect);
    else if (node && typeof node === "object") {
      if (typeof node.entry_hash === "string" && !memo.has(node.entry_hash)) {
        const prev = typeof node.prev_hash === "string" ? memo.get(node.prev_hash) : undefined;
        const before = prev ?? (node.seq === 1 ? "0".repeat(64) : sha(`prev|${node.op_id}`));
        memo.set(node.entry_hash, sha(`${before}|${node.seq}|${node.op_id}|${node.kind}|${node.status}`));
      }
      Object.values(node).forEach(collect);
    }
  };
  collect(root);
  const apply = (node) => {
    if (Array.isArray(node)) node.forEach(apply);
    else if (node && typeof node === "object") {
      for (const k of ["entry_hash", "prev_hash", "chain_head_hash", "head_hash"]) {
        if (typeof node[k] !== "string") continue;
        node[k] = memo.get(node[k]) ?? (k === "prev_hash" ? sha(`prev|${node.op_id}`) : sha(`head|${name}`));
      }
      Object.values(node).forEach(apply);
    }
  };
  apply(root);
}

function normalise(name, value) {
  const text = JSON.stringify(value)
    .replace(/CMT-[0-9a-f]{16}/g, FIXED_CMT)
    .replace(/ALERT-EARLYPAY-[0-9a-f]{12}/g, `ALERT-EARLYPAY-${sha("recorded early-pay alert").slice(0, 12)}`)
    .replace(/NL-[0-9a-f]{16}/g, (id) => {
      if (!nlIds.has(id)) nlIds.set(id, `NL-${sha(`recorded nl id ${nlIds.size}`).slice(0, 16)}`);
      return nlIds.get(id);
    });
  const out = JSON.parse(text, (k, v) => (k === "nonce" && typeof v === "string" && /^[0-9a-f]{32}$/.test(v) ? FIXED_NONCE : v));
  const rechain = (node) => {
    if (Array.isArray(node)) {
      let prev = null;
      for (const op of node) {
        if (op && typeof op === "object" && typeof op.entry_hash === "string") {
          op.prev_hash = prev ?? (op.seq === 1 ? "0".repeat(64) : sha(`prev|${op.op_id}`));
          op.entry_hash = sha(`${op.prev_hash}|${op.seq}|${op.op_id}|${op.kind}|${op.status}`);
          prev = op.entry_hash;
        } else rechain(op);
      }
    } else if (node && typeof node === "object") for (const v of Object.values(node)) rechain(v);
  };
  if (name.startsWith("strategy/")) out.computed_in_seconds = 0;
  if (RECHAIN.has(name)) rechain(out);
  if (RECHAIN_BY_APPEARANCE.has(name)) rechainByAppearance(name, out);
  return out;
}

function write(name, value) {
  writeFileSync(join(OUT, name), JSON.stringify(normalise(name, value), null, 2) + "\n");
  written.push(name);
}
const step = (id) => DEMO_STEPS.find((s) => s.id === id);
const demo = () => demoStore.get();

/** An operation as the mock ledger replays it: what the server said (the executor's sentence and its Business twin), without the position in the chain. */
function template(op) {
  return { kind: op.kind, status: op.status, tier: op.tier, requested_by: op.requested_by, message: op.message, summary: op.summary, message_when: op.message_when ?? null, event_text: op.event_text ?? null, event_detail: op.event_detail ?? null };
}
async function ledgerTail(n) {
  return (await live.getLedger()).operations.slice(-n);
}
/** GET /receivables/{id}/chase for every open invoice of the books just read, in both languages ({ en: { id: view }, zh: { id: view } }). */
async function chaseAll(recon) {
  const out = { en: {}, zh: {} };
  for (const o of recon.outstanding) for (const lang of ["en", "zh"]) out[lang][o.receivable_id] = await live.getChase(o.receivable_id, lang);
  return out;
}
async function reset() {
  await live.demoReset();
  clearDemo();
}

// ------------------------------------------------------------------ the demo stepper, in order, snapshotting after each step
const ops = {};
const files = {};

// --strategy: the nine strategy recordings and nothing else (see the header). The recorder's own day-0, day-34 and day-34-approved states.
if (STRATEGY) {
  const BUYER = "BUYER-1";
  const strategyReads = async (lang) => {
    const [curve, worth] = [await live.getPriceCurve(lang), await live.getReceivablesWorth(lang)];
    const envelope = await live.getEnvelope(BUYER, lang, true);
    if (!curve || !worth || !envelope) throw new Error("a strategy route is off: start the API with FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1");
    // The adapter falls back to the plain answer when the server refuses ?zone=1; the mock needs the table.
    if (!envelope.zone.length) throw new Error("the envelope came back without its zone: the server refused ?zone=1");
    return { curve, worth, envelope };
  };
  const keep = (suffix, reads) => {
    files[`strategy/price_curve_${suffix}.json`] = reads.curve;
    files[`strategy/worth_${suffix}.json`] = reads.worth;
    files[`strategy/envelope_${suffix}.json`] = reads.envelope;
  };
  mkdirSync(join(OUT, "strategy"), { recursive: true });
  await reset();
  keep("day0", await strategyReads("en"));
  await toDay34();
  keep("day34", await strategyReads("en"));
  // The owner's approval of day 34's cure, as the home's recording does it: the act queues it, the approval executes it.
  {
    const alerts = await live.getAlerts();
    const reserve = alerts.alerts.find((a) => a.id.startsWith("ALERT-RESERVE") && a.actionable);
    if (!reserve) throw new Error("no actionable reserve alert on day 34: the demo path has changed");
    const act = await live.actOnAlert(reserve.id, {
      state_version: alerts.state_version,
      suggestions: reserve.suggested.map((x) => ({ operation_kind: x.operation_kind, facility_id: x.facility_id, receivable_id: x.receivable_id, amount_fen: x.amount_fen })),
    });
    if (act.results[0]?.status !== "PENDING_APPROVAL") throw new Error("the day-34 cure no longer waits for approval: the demo path has changed");
    await live.decideApproval((await live.getApprovals())[0].id, "APPROVE");
  }
  keep("day34_after", await strategyReads("en"));
  await live.demoReset();
  for (const name of Object.keys(files).sort()) write(name, files[name]);
  console.log(`recorded ${written.length} strategy files into ${join(OUT, "strategy")} from ${API}`);
  process.exit(0);
}

await reset();
files["state.json"] = await live.getState();
files["mandate.json"] = await live.getMandate();
// Opening books: the alerts and reconciliation the owner sees before anything happens, and the home summary (GET /home).
files["alerts.json"] = await live.getAlerts();
files["reconciliation.json"] = await live.getReconciliation();
files["chase_day0.json"] = await chaseAll(files["reconciliation.json"]); // the collection handoff on the opening books (nothing due yet)
files["home_summary_day0.json"] = await live.getHome("en");
files["home_summary_day0_zh.json"] = await live.getHome("zh");
files["trajectory_conservative_day0.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
// The day-0 fix runs alone (Tier 1): the home's "Go ahead" on the opening books, bound to what the home showed.
{
  const a = files["home_summary_day0.json"].next_action;
  files["home_act_day0.json"] = await live.actOnAlert(a.alert_id, { state_version: a.state_version, suggestions: a.suggestions });
  if (files["home_act_day0.json"].executed !== 2) throw new Error("the day-0 fix no longer runs alone: the demo path has changed");
  files["home_summary_after_fund.json"] = await live.getHome("en");
  files["home_summary_after_fund_zh.json"] = await live.getHome("zh");
  files["trajectory_conservative_after_fund.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
}

let verdictEx01 = null;
for (const s of DEMO_STEPS) {
  await s.run();
  const d = demo();
  if (s.id === "inbox") files["offer_ex01.json"] = d.offers[d.offerId];
  if (s.id === "trajectory") {
    verdictEx01 = d.verdicts[d.offerId];
    files["verdict_ex01.json"] = verdictEx01;
    // The trajectory page: the position with the offer applied (conservative decides) and the position today (expected).
    files["trajectory_conservative.json"] = await live.getTrajectory("CONSERVATIVE", verdictEx01);
    files["trajectory_expected.json"] = await live.getTrajectory("EXPECTED", verdictEx01);
  }
  if (s.id === "funding") files["funding.json"] = d.funding;
  if (s.id === "negotiate") {
    files["negotiation_accept.json"] = d.negotiations[d.offerId];
    const [accept, draw] = await ledgerTail(2);
    ops.accept_a = template(accept);
    ops.draw_line = template(draw);
  }
  if (s.id === "walk") {
    files["offer_ex01b.json"] = d.offers[d.rewordedId];
    files["verdict_ex01b.json"] = d.verdicts[d.rewordedId];
    files["negotiation_nodeal.json"] = d.negotiations[d.offerId];
    const [draw, invoice] = await ledgerTail(2);
    ops.draw_line_hard_line = template(draw);
    ops.submit_invoice = template(invoice);
  }
  // The capex evaluation writes nothing; the approval step is the owner's explicit application (POST /capex/apply, one
  // Tier-2 operation waiting in the queue) and the read-only borrower file (no operation, no approval).
  if (s.id === "capex") files["capex.json"] = d.capex;
  if (s.id === "approval") {
    files["capex_apply.json"] = d.capexApplication;
    ops.request_approval = template((await ledgerTail(1))[0]);
    files["approvals_seed.json"] = { apply_loan: (await live.getApprovals())[0] };
    files["borrower_file.json"] = d.borrowerFile;
  }
  if (s.id === "fastcapital") {
    const sec = Object.values(d.offers).find((o) => o.offer.counterparty_id !== "BUYER-1");
    files["offer_sec.json"] = sec;
    files["verdict_sec.json"] = d.verdicts[sec.offer.offer_id];
    files["audit_sec.json"] = await live.getAudit();
  }
}

// ------------------------------------------------------------------ the owner's decisions in the approval queue (ledger rows)
// The decision is recorded on the same books as the stepper's approval step (the stepper replayed up to it), so the
// approved application names the structure the queued one does (the 36-month loan); on untouched books the evaluation
// would select the lease and the approved row would disagree with the queued request.
async function queueOne() {
  await reset();
  for (const s of DEMO_STEPS) {
    await s.run();
    if (s.id === "approval") break;
  }
  return live.getApprovals();
}
let q = await queueOne();
await live.decideApproval(q[0].id, "APPROVE");
ops.approve_apply_loan = template((await ledgerTail(1))[0]);
q = await queueOne();
await live.decideApproval(q[0].id, "REJECT");
ops.reject_apply_loan = template((await ledgerTail(1))[0]);
files["ops.json"] = ops;

// ------------------------------------------------------------------ a typed offer (no server fixture): early payment inside every limit
await reset();
const typed = await live.submitOffer({
  counterparty_id: "BUYER-1",
  documents: [
    { doc_id: "ACC-msg", channel: "chat", sender_id: "BUYER-1", received_day: 0, text: "We will pay the full ¥420,000 invoice early at 0.5%." },
  ],
});
files["offer_accept.json"] = typed;
files["verdict_accept.json"] = await live.evaluateOffer(typed.offer.offer_id);

// ------------------------------------------------------------------ what-if: the presets and a coarse grid, on the opening books
await reset();
{
  const first = await live.whatIf({ terms_days: 60, discount_bp: 120, rebate_bp: 100, price_adjustment_bp: 0, settle_face_fen: null });
  const controls = first.controls;
  const asked = [];
  const seen = new Set();
  const add = (id, params) => {
    const k = JSON.stringify(params);
    if (!seen.has(k)) {
      seen.add(k);
      asked.push({ id, params });
    }
  };
  for (const [key, p] of Object.entries(controls.presets)) {
    add(key, { terms_days: p.terms_days, discount_bp: p.discount_bp, rebate_bp: p.rebate_bp, price_adjustment_bp: p.price_adjustment_bp, settle_face_fen: p.settle_face_fen });
  }
  for (const t of [30, 45, 60, 90]) for (const d of [0, 120]) for (const r of [0, 100]) add(`t${t}_d${d}_r${r}`, { terms_days: t, discount_bp: d, rebate_bp: r, price_adjustment_bp: 0, settle_face_fen: null });
  const entries = [];
  for (const a of asked) {
    const { controls: _c, ...result } = await live.whatIf(a.params);
    void _c;
    entries.push({ id: a.id, params: result.params ?? a.params, result: { ...result, compute_ms: 0, cached: false } });
  }
  files["whatif_presets.json"] = { source: "recorded from POST /whatif on the opening books (scripts/record-mocks.mjs)", controls, entries };
}

// ------------------------------------------------------------------ the home: deal, receipt on day 2, clock to day 34 (as scripts/demo_run.py)
async function bankReceipt(half = false) {
  const recon = await live.getReconciliation();
  const promised = recon.promised[0];
  const mandate = await live.getMandate();
  const res = await fetch(`${API}/operations`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Owner-Token": OWNER_TOKEN, ...BANK },
    body: JSON.stringify({
      kind: "RECEIVE_PAYMENT",
      op_id: "rec-receipt-1",
      idempotency_key: "rec-receipt-1",
      mandate_version: mandate.mandate.version,
      requested_by: "SYSTEM",
      receivable_id: promised.receivable_id,
      amount_fen: half ? Math.floor(promised.expected_fen / 2) : promised.expected_fen, // half: the buyer part-keeps the promise (bank-feed setup, not a displayed figure)
      bank_reference: "DEMO-RCPT-1", // the demo's bank feed carries the bank's own reference on every receipt
    }),
  });
  if (!res.ok) throw new Error(`bank receipt failed: ${res.status} ${await res.text()}`);
}
async function toDay34(atDay0 = async () => {}) {
  await reset();
  await step("inbox").run();
  await step("trajectory").run();
  await step("negotiate").run();
  await atDay0();
  await live.advanceClock(2);
  await bankReceipt();
  await live.advanceClock(28);
  await live.advanceClock(4);
}

// Day 0 after the deal the cure is committed, so "nothing needs you": the quiet opener in both languages.
await toDay34(async () => {
  files["home_opener_quiet.json"] = await live.nlOpener("rec-quiet-en", "en");
  files["home_opener_quiet_zh.json"] = await live.nlOpener("rec-quiet-zh", "zh");
  files["home_summary_quiet.json"] = await live.getHome("en");
  files["home_summary_quiet_zh.json"] = await live.getHome("zh");
  files["trajectory_conservative_quiet.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
});
files["home_alerts_day34.json"] = await live.getAlerts();
files["home_summary_day34.json"] = await live.getHome("en");
files["home_summary_day34_zh.json"] = await live.getHome("zh");
files["trajectory_conservative_day34.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
files["home_state_day34.json"] = await live.getState();
// The books' history at day 34 (the deal, the funding, the day-2 receipt): the mock replays it when the clock is moved to day 34 without the walk.
files["home_ledger_day34.json"] = await live.getLedger();
// The router's comparison for day 34's gap (the Cash page shows a fresh plan while a gap is open, never the day-0 one).
files["funding_day34.json"] = await live.planFunding({});
// The reconciliation after the day-2 bank receipt (it carries the bank's reference).
files["home_reconciliation_day34.json"] = await live.getReconciliation();
files["chase_day34.json"] = await chaseAll(files["home_reconciliation_day34.json"]); // the collection handoff for the late invoice and the two coming
const reserve = files["home_alerts_day34.json"].alerts.find((a) => a.id.startsWith("ALERT-RESERVE") && a.actionable);
if (!reserve) throw new Error("no actionable reserve alert on day 34: the demo path has changed");
files["home_opener_day34.json"] = await live.nlOpener("rec-home-en", "en");
files["home_opener_day34_zh.json"] = await live.nlOpener("rec-home-zh", "zh");
// "Let the agent fix this": the cure is above the yearly cost ceiling (¥1,782.19 for 10 days = 32.5% a year), so the executor
// does not run it: it answers PENDING_APPROVAL with an approval id, and the alert stays open.
// The act is bound to what the owner was shown: the state_version of the alerts read and the alert's suggestions.
files["home_act.json"] = await live.actOnAlert(reserve.id, {
  state_version: files["home_alerts_day34.json"].state_version,
  suggestions: reserve.suggested.map((x) => ({ operation_kind: x.operation_kind, facility_id: x.facility_id, receivable_id: x.receivable_id, amount_fen: x.amount_fen })),
});
if (files["home_act.json"].results[0]?.status !== "PENDING_APPROVAL") throw new Error("the day-34 cure no longer waits for approval: the demo path has changed");
files["home_opener_pending.json"] = await live.nlOpener("rec-home-pending", "en");
files["home_summary_pending.json"] = await live.getHome("en");
files["home_summary_pending_zh.json"] = await live.getHome("zh");
files["trajectory_conservative_pending.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
files["home_approval_pending.json"] = (await live.getApprovals())[0];
// The owner approves on the approval card: the same operation executes (EXECUTED, the cash lands on day 37) and the alert clears.
files["home_approval_approved.json"] = await live.decideApproval(files["home_approval_pending.json"].id, "APPROVE");
files["home_approve.json"] = { operations: await ledgerTail(1) };
// The log after the decision: the earlier "waiting" entry now reads in the past, beside "You approved ..." (the mock replays that).
files["home_ledger_approved.json"] = await live.getLedger();
files["home_alerts_after.json"] = await live.getAlerts();
files["home_state_after_approve.json"] = await live.getState();
files["home_opener_after_approve.json"] = await live.nlOpener("rec-home-after", "en");
files["home_summary_after.json"] = await live.getHome("en");
files["home_summary_after_zh.json"] = await live.getHome("zh");
files["trajectory_conservative_after.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
// The mandate's last day is 90: MANDATE_EXPIRING is a WARNING 14 days before (recorded at day 80) and CRITICAL once it has passed (day 95).
await live.advanceClock(80 - 34);
files["home_alerts_mandate_warning.json"] = await live.getAlerts();
await live.advanceClock(95 - 80);
files["home_alerts_mandate_expired.json"] = await live.getAlerts();

// The same cure through the chat: "go ahead" queues it (PENDING_APPROVAL), then the owner types "approve APR-…".
await toDay34();
await live.nlOpener("rec-home-go", "en");
files["home_goahead.json"] = await live.nl({ session_id: "rec-home-go", actor: "OWNER", text: "go ahead" });
const queued = files["home_goahead.json"].operations[0]?.approval_id;
if (!queued) throw new Error("go ahead on day 34 queued no approval: the demo path has changed");
files["home_approve_chat.json"] = await live.nl({ session_id: "rec-home-go", actor: "OWNER", text: `approve ${queued}` });

// ------------------------------------------------------------------ Wave 1 stories (map #65): three states the main walk does not reach
// 1. Day 34 with NO bank receipt on day 2: the books are already under the reserve today (cash.below_reserve_today). The mock serves it
//    when sessionStorage "tl-mock-no-receipt" is "1" (lib/mock/home.ts).
await reset();
await step("inbox").run();
await step("trajectory").run();
await step("negotiate").run();
await live.advanceClock(2);
await live.advanceClock(28);
await live.advanceClock(4);
files["home_summary_day34_noreceipt.json"] = await live.getHome("en");
files["home_summary_day34_noreceipt_zh.json"] = await live.getHome("zh");
files["trajectory_conservative_day34_noreceipt.json"] = await live.getTrajectory("CONSERVATIVE");
if (files["home_summary_day34_noreceipt.json"].cash.below_reserve_today !== true) throw new Error("day 34 without a receipt should be below the reserve today: the API has changed");

// 1b. Day 34 after a HALF receipt on day 2: the part-paid promise's change row carries the four named facts and the window (F25).
//     The mock serves it when "tl-mock-no-receipt" is "half".
await reset();
await step("inbox").run();
await step("trajectory").run();
await step("negotiate").run();
await live.advanceClock(2);
await bankReceipt(true);
await live.advanceClock(28);
await live.advanceClock(4);
files["home_summary_day34_half.json"] = await live.getHome("en");
files["home_summary_day34_half_zh.json"] = await live.getHome("zh");
files["trajectory_conservative_day34_half.json"] = await live.getTrajectory("CONSERVATIVE");
if (!files["home_summary_day34_half.json"].changes.some((c) => c.window_state)) throw new Error("a half receipt should give a change row with the part-paid facts: the API has changed");
// The Receivables page on the same books: the receipt row carries the four facts (F25) and the late invoice has its handoff (F15).
files["home_reconciliation_day34_half.json"] = await live.getReconciliation();
if (!files["home_reconciliation_day34_half.json"].receipts.some((r) => r.window_state === "ended" && r.remaining_display)) throw new Error("the half receipt's row should carry the four facts and the window: the API has changed");
files["chase_day34_half.json"] = await chaseAll(files["home_reconciliation_day34_half.json"]);

// 2. A buyer's early-payment message queues an agreement for the owner: its approval row carries the terms (terms_available true);
//    once the agreement has expired the same row says the terms cannot be shown (terms_available false, with the server's reason).
//    3. The day-34 cure approved after the mandate has expired: the executor refuses to run it, the approval stays APPROVED.
//    The mock serves these when sessionStorage "tl-mock-approval-story" is "agreement", "expired" or "refused" (lib/mock/handlers.ts).
const stories = {};
await reset();
{
  // The buyer's own channel carries the buyer's key; the owner-side client does not send it.
  const res = await fetch(`${API}/nl`, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Counterparty-Key": "demo-buyer-1-key" },
    body: JSON.stringify({ session_id: "rec-agreement", actor: "COUNTERPARTY", counterparty_id: "BUYER-1", text: "We can pay the invoice early at 0.5%.", request_id: "rec-agreement-1" }),
  });
  if (!res.ok) throw new Error(`the buyer's message failed: ${res.status} ${await res.text()}`);
}
stories.agreement = (await live.getApprovals()).find((a) => a.operation_kind === "ACCEPT_OFFER" || a.operation_kind === "RECORD_COMMITMENT");
if (!stories.agreement?.presentation?.terms_available) throw new Error("the buyer's message queued no agreement with terms: the demo path has changed");
await live.advanceClock(60);
stories.expired = (await live.getApprovals()).find((a) => a.id === stories.agreement.id);
if (stories.expired?.presentation?.terms_available !== false) throw new Error("an expired agreement should have no terms: the API has changed");
await toDay34();
{
  const alerts = await live.getAlerts();
  const reserve = alerts.alerts.find((a) => a.id.startsWith("ALERT-RESERVE") && a.actionable);
  if (!reserve) throw new Error("no actionable reserve alert on day 34: the demo path has changed");
  await live.actOnAlert(reserve.id, {
    state_version: alerts.state_version,
    suggestions: reserve.suggested.map((x) => ({ operation_kind: x.operation_kind, facility_id: x.facility_id, receivable_id: x.receivable_id, amount_fen: x.amount_fen })),
  });
}
const cure = (await live.getApprovals())[0];
await live.advanceClock(91 - 34);
const refused = await live.decideApproval(cure.id, "APPROVE");
if (refused.presentation?.execution_status !== "REFUSED") throw new Error("approving after the mandate expired should be refused: the API has changed");
stories.refused = { pending: cure, decided: refused };
files["w1_approval_stories.json"] = stories;

// ------------------------------------------------------------------ the chat: every scripted text the mock knows, one conversation each
const P = (role, lang, id) => promptsFor(role, lang).find((p) => p.id === id);
const o = (lang, id) => P("OWNER", lang, id).text;
const b = (lang, id) => P("COUNTERPARTY", lang, id);

/** [conversation, role, counterparty, turns: [script key or null (setup only), text]] */
const CONVERSATIONS = [
  ["ex01-go", "OWNER", null, [["evaluate_ex01", o("en", "evaluate")], ["negotiate_ex01", "go ahead"]]],
  ["ex01-cancel", "OWNER", null, [[null, o("en", "evaluate")], ["cancel", "cancel"]]],
  ["ex01-why", "OWNER", null, [[null, o("en", "evaluate")], ["explain_en", o("en", "why")]]],
  ["ex01-why-zh", "OWNER", null, [[null, o("zh", "evaluate")], ["explain_zh", o("zh", "why")]]],
  ["goal-go", "OWNER", null, [["goal", o("en", "goal")], ["goal_go", "go ahead"]]],
  ["goal-08", "OWNER", null, [[null, o("en", "goal")], ["amend_08", o("en", "amend")]]],
  ["goal-1", "OWNER", null, [[null, o("en", "goal")], ["amend_1_refused", "actually make it 1%"]]],
  ["goal-fin", "OWNER", null, [[null, o("en", "goal")], ["amend_fin", "actually use invoice financing instead"]]],
  ["goal-go-zh", "OWNER", null, [["goal_zh", o("zh", "goal")], ["goal_go_zh", "执行"]]],
  ["goal-08-zh", "OWNER", null, [[null, o("zh", "goal")], ["amend_08_zh", o("zh", "amend")]]],
  ["ex01-go-zh", "OWNER", null, [["evaluate_ex01_zh", o("zh", "evaluate")], ["negotiate_ex01_zh", "执行"]]],
  // "Fund the cash gap" only PROPOSES; "go ahead" runs it: the draw is cash now, the invoice advance lands on day 3.
  ["fund", "OWNER", null, [["fund_gap", o("en", "fund")], ["fund_gap_go", "go ahead"]]],
  ["fund-zh", "OWNER", null, [["fund_gap_zh", o("zh", "fund")], ["fund_gap_go_zh", "执行"]]],
  ["status", "OWNER", null, [["status", o("en", "status")]]],
  ["status-zh", "OWNER", null, [["status_zh", o("zh", "status")]]],
  ["vague", "OWNER", null, [["clarify_cash", o("en", "vague")]]],
  ["vague-zh", "OWNER", null, [["clarify_cash_zh", o("zh", "vague")]]],
  ["approve", "OWNER", null, [["approve_none", o("en", "approve")]]],
  ["approve-zh", "OWNER", null, [["approve_none_zh", o("zh", "approve")]]],
  ["scope", "OWNER", null, [["out_of_scope", "Tell me a joke about the weather."]]],
  ["tier3", "OWNER", null, [["tier3", "Sign a personal guarantee for the bank loan."]]],
  ["buyer-fastcapital", "COUNTERPARTY", b("en", "fastcapital").counterparty, [["fastcapital", b("en", "fastcapital").text]]],
  ["buyer-ex02", "COUNTERPARTY", b("en", "ex02").counterparty, [["buyer_ex02", b("en", "ex02").text]]],
  ["buyer-rebate", "COUNTERPARTY", b("en", "rebate").counterparty, [["buyer_rebate", b("en", "rebate").text]]],
  ["buyer-extraction", "COUNTERPARTY", b("en", "extraction").counterparty, [["buyer_extraction", b("en", "extraction").text]]],
  ["buyer-extraction-zh", "COUNTERPARTY", b("zh", "extraction").counterparty, [["buyer_extraction_zh", b("zh", "extraction").text]]],
  ["buyer-injection-zh", "COUNTERPARTY", b("zh", "injection").counterparty, [["buyer_injection_zh", b("zh", "injection").text]]],
];
// The order of the keys in the file (the mock looks them up by name; the order only keeps the file diffable).
const KEY_ORDER = [
  "evaluate_ex01", "negotiate_ex01", "cancel", "explain_en", "explain_zh", "goal", "goal_go", "amend_08", "amend_1_refused", "amend_fin",
  "fund_gap", "fund_gap_go", "status", "clarify_cash", "clarify_cash_zh", "amend_08_zh", "goal_zh", "goal_go_zh", "evaluate_ex01_zh", "negotiate_ex01_zh",
  "fund_gap_zh", "fund_gap_go_zh", "status_zh", "approve_none_zh", "approve_none", "out_of_scope", "tier3", "fastcapital", "buyer_ex02", "buyer_extraction",
  "buyer_extraction_zh", "buyer_injection_zh", "buyer_rebate",
];
const script = {};
for (const [conv, role, counterparty, turns] of CONVERSATIONS) {
  await live.demoReset();
  for (const [key, text] of turns) {
    const r = await live.nl({
      session_id: `rec-${conv}`,
      actor: role,
      counterparty_id: role === "COUNTERPARTY" ? counterparty : undefined,
      text,
    });
    if (key) script[key] = r;
  }
  // The books right after the day-0 plan ran: cash in hand, and the advance still on its way (lots).
  if (conv === "fund") files["state_after_fund.json"] = await live.getState();
}
const missing = KEY_ORDER.filter((k) => !(k in script));
if (missing.length || Object.keys(script).length !== KEY_ORDER.length) throw new Error(`nl script keys do not match: missing ${missing.join(", ")}`);
files["nl_script.json"] = Object.fromEntries(KEY_ORDER.map((k) => [k, script[k]]));

// ------------------------------------------------------------------ Ask FLOW bound to the page (map #65, wave 4 part A): mocks/nl_page.json
// The questions the Business pages suggest (lib/chat-prompts.ts), asked as the browser asks them: the page, the deal the page
// evaluated (an id), and the last-visit marker. The deal questions are recorded once on the day-0 books with EX01 evaluated over
// REST (the Deals page's own path); the others at each point of the story the mock can be at (lib/mock/home.ts readPoint()).
const pageAsk = (session, text, context) => live.nl({ session_id: `rec-page-${session}`, actor: "OWNER", text, context });
const POINT_QUESTIONS = {
  changes: ["What changed today?", "/"],
  waiting: ["What are we waiting for?", "/deals"],
  arrival: ["When does the money arrive?", "/cash"],
  overdue: ["What is overdue?", "/receivables"],
  late: ["What happens if this payment is late?", "/cash"],
  plan: ["Why did FLOW choose this plan?", "/cash"],
};
async function pointReads(point, since) {
  const out = {};
  for (const [key, [text, pg]] of Object.entries(POINT_QUESTIONS)) {
    out[key] = await pageAsk(`${point}-${key}`, text, { page: pg, ...(since === null ? {} : { since_day: since }) });
  }
  return out;
}
const nlPage = {};
await reset();
await step("inbox").run();
await step("trajectory").run();
{
  const offerId = demo().offerId;
  const ctx = { page: "/deals", offer_id: offerId };
  nlPage.deals = {
    explain: await pageAsk("deal-explain", "Why are we countering this?", ctx),
    original: await pageAsk("deal-original", "What if I accept their original terms?", ctx),
    option: await pageAsk("deal-option", "Why is Option A cheaper?", ctx),
  };
  if (!nlPage.deals.explain.context_echo?.decision_id) throw new Error("the page's deal was not bound: the API has changed");
}
await reset();
nlPage.day0 = await pointReads("day0", null);
await toDay34();
nlPage.day34 = await pointReads("day34", 0);
{
  const alerts = await live.getAlerts();
  const reserve = alerts.alerts.find((a) => a.id.startsWith("ALERT-RESERVE") && a.actionable);
  if (!reserve) throw new Error("no actionable reserve alert on day 34: the demo path has changed");
  await live.actOnAlert(reserve.id, {
    state_version: alerts.state_version,
    suggestions: reserve.suggested.map((x) => ({ operation_kind: x.operation_kind, facility_id: x.facility_id, receivable_id: x.receivable_id, amount_fen: x.amount_fen })),
  });
}
nlPage.pending = await pointReads("pending", 0);
await live.decideApproval((await live.getApprovals())[0].id, "APPROVE");
nlPage.after = await pointReads("after", 0);
if (nlPage.pending.changes.intent !== "CHANGES" || !nlPage.pending.changes.reply.includes("Waiting for your approval")) throw new Error("the queued cure is not in 'what changed': the API has changed");
files["nl_page.json"] = nlPage;

await live.demoReset();

for (const name of Object.keys(files).sort()) write(name, files[name]);
console.log(`recorded ${written.length} files into ${OUT} from ${API}`);
