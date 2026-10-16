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
//   - the SEC-<KIND>-<16 hex> security event ids (SEC-OPS, SEC-AUTH, ...) (random per event) and the chat's recorded decision ids (nl:<topic>:t<n>:<12 hex>, from a random
//     session nonce): fixed ids by order of first appearance.
//   - nl_script.json and state_after_fund.json: the NL-<16 hex> operation and lot ids, which the API derives from a random
//     per-session nonce, become fixed ids by order of first appearance; nl_script.json, home_reconciliation_day34.json and the two
//     home ledgers (home_ledger_day34.json, home_ledger_approved.json) and the receipts inside decisions.json are
//     chained again by first appearance (entry_hash / prev_hash re-derived, chain_head_hash fixed) for the same reason.
//   - the early-payment alert id (ALERT-EARLYPAY-<12 hex>, derived from the offer's random id; raised on the books where the day-2 receipt
//     never came): one fixed id.
//   - the entry_hash / prev_hash of the operations in negotiation_accept.json, home_act.json, home_goahead.json, home_approve.json
//     and home_approve_chat.json: the
//     server's chain includes that commitment id, so it differs on every run. They are re-derived (sha256 over the op's
//     own seq, id, kind, status and the previous hash) so the chain stays internally consistent and repeatable. Hashes in
//     every other file (the chat script, for one) are deterministic and are kept exactly as recorded.
//   - offer_exposure_ex01.json (only with --exposure): `computed_in_seconds` and each `capacity[*].spare.seconds` -> 0 (timings).
//   - slice_d/*.json (only with --slice-d): every `loss_token` (a fingerprint of the books, which includes the restore history the API accumulates) becomes a fixed token by order of first appearance; the books' state version at the end of a funding decision's id (alert:ALERT-RESERVE-42:v<n>) becomes v7, the id the
//     mock's decision recordings use for the same record; `alternate.history` is trimmed (see trimRestoreHistory).
//   - strategy/*.json (only with --strategy): `computed_in_seconds` -> 0 (the time the call took; a cache hit differs from a miss).
//
// The decision record (Wave 2, ADR-0011) is recorded as snapshots in decisions.json, { name: { en, zh } }, each one GET /decisions/{id} read at
// the moment the story names (received, ready, agreed_day0, fulfilled_day34, expired_day34 / missed_day34 on the receipt variants, nodeal,
// cure_pending, cure_approved, cure_failed, cure_residual, and so on). lib/mock/decisions.ts chooses among them by the mock's story state.
// w2_counter_changed.json holds the two 409 COUNTER_CHANGED answers (the books moved: no counters, re-evaluate; the verdict was replaced: the
// current counters). home_summary_day34_residual*.json is the home after a cure that did not restore the reserve, once the cash landed (the
// remaining task), with its trajectory.
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
// --slice-d records ONLY apps/web/mocks/slice_d/{activity,story,restore,audit}.json and exits (Slice D, ticket #145): GET /activity and GET /demo/story in both
// languages, and POST /demo/restore, at the moments the mock walks through. The walk is the Demo's own: lib/demo.ts DEMO_STEPS run in order through the
// live adapters (the stepper section above records the same walk for the pages), the owner's approval pressed by this recorder between `queue` and
// `approve` exactly as the section above does (the product never presses it). The story is read with `seen` = the last view step shown (cash, outcome or proof), as the Demo page sends it.
//   story.json    { fresh, ask, decide, agree, cash, bank, time, queue, approve, settle, outcome, proof, busy, short }: each { en, zh } of GET /demo/story
//   activity.json { fresh, ask, decide, agree, bank, time, queue, approve, settle, security, busy, short }: each { en, zh } of GET /activity; `security` is the
//                 settled books after two refused sign-ins and the FastCapital scene (benign sign-ins beside a real alert); `busy` is the busy company
//   restore.json  { en, zh } of POST /demo/restore, made on the busy books
//   guard.json    { loss_not_confirmed, loss_changed, books_changed }: { en, zh } of the message words of the 409s of POST /demo/reset?from_scenario= (work on the books not confirmed; books that are another)
//   audit.json    GET /audit at the `security` moment (the same events the Activity rows link to), served by the mock for the security view
// lib/mock/handlers.ts picks among them by the mock's own state (cure stage, clock day, offers, receipt) and serves `busy` (or `short`) once those books are loaded.
//   cd services/api && TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8221
//   node scripts/record-mocks.mjs --api http://localhost:8221 --slice-d
//
// home_summary_day0_counter[_zh].json is GET /home on the opening books with the package offer read and no reply sent (cash.pending and its legend; ticket #116).
//
// --exposure records ONLY apps/web/mocks/offer_exposure_ex01.json, offer_picture_ex01_exposure.json and offer_scenarios_ex01.json (the scenarios of the Business consequences) and deals_day0_evaluated_back.json (the deals read opened with a customer: `open_offer.context.back`) and exits: { en, zh } of GET /offers/{id}/exposure?lang= for the package offer (EX01) after
// FLOW has read it, on the opening books. One read carries every path (the sentences of every path are in `band.by_path`), so there is no per-response file. The API needs
// FEATURE_EXPOSURE=1 (and FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 as above):
//   node scripts/record-mocks.mjs --api http://localhost:8193 --exposure
//
// receivables/<point>[_zh].json   GET /receivables (the Receivables page's rows and summary) at each point of the home's story: day0, quiet,
// day2, after_fund, day34 (and its noreceipt / half / residual books), pending, after, settled, in both languages; receivables/offer[_zh].json is
// the opening books with the buyer's early-payment message open (the row carries pending_counter) and receivables/exposure_offer[_zh].json the
// exposure of that deal's decision (the aside's late-payment test). buyer_exposure[_zh] and buyer_exposure_day34[_zh] are GET /buyers/BUYER-1/exposure on
// the opening books and on day 34 (the same test with no deal). The API needs FEATURE_EXPOSURE=1 for these.
// buyer_exposure[_zh].json alone: --buyer-exposure (the same GET /buyers/BUYER-1/exposure, on the opening books; the API needs FEATURE_EXPOSURE=1).
//
// --no-exposure skips the three exposure reads (buyer_exposure*, exposure_offer*): run it against an API WITHOUT FEATURE_EXPOSURE to record the home reads the specs
// expect (stress_available false); run again with the flag on for the exposure files and the receivables reads, and keep each run's own files.
//
// --overview records ONLY apps/web/mocks/customer_overview.json and exits (GET /customers/BUYER-1/overview, ticket #108): for each moment the
// mock chooses among (lib/mock/handlers.ts overviewMoment), { en, zh } of { view, backs }, where `backs` holds the back link the server builds for
// each query the specs open the page with (a deal; a deal and its path; an invoice). The moments: quiet (the opening books), offer_received and
// offer_evaluated (the package offer waiting, unread and read), after_fund (the day-0 plan ran: the financing arranged), day34 and day34_after (the
// late invoice, then the approved cure). The API needs FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_EXPOSURE=1
// and the other flags as above:
//   cd services/api && FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_EXPOSURE=1 SKIP_PERF_BENCH=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8016
//   node scripts/record-mocks.mjs --api http://localhost:8016 --overview
// and, against an API started WITHOUT FEATURE_EXPOSURE, `--overview --exposure-off` records customer_overview_exposure_off.json ({ en, zh }: the opening
// books' overview with the exposure panel off and the server's note for it), which the mock serves while the spec's hook key is set.
//
// --inputs records ONLY apps/web/mocks/buyer_inputs.json and exits (the owner's Inputs sheet, ticket #97): { en, zh } of the opening sheet
// (GET /buyers/BUYER-1/inputs, read without a context: the mock serves it for any query, its back link the plain one to the customer),
// the firm read (GET /firm/inputs; kept as the server's answer, the page itself shows the sheet's own firm rows), the overview before and
// after, the 422 a margin of 150% gets, the answer to saving a margin of 25% (POST /buyers/BUYER-1/inputs, `value_text`), and the sheet
// after that save. The API needs FEATURE_EXPOSURE=1 FEATURE_CUSTOMER_ECONOMICS=1 and the other flags as above:
//   cd services/api && FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_EXPOSURE=1 FEATURE_CUSTOMER_ECONOMICS=1 SKIP_PERF_BENCH=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8197
//   node scripts/record-mocks.mjs --api http://localhost:8197 --inputs
// and, against an API started WITHOUT FEATURE_CUSTOMER_ECONOMICS, `--inputs --economics-off` records buyer_inputs_off.json ({ en, zh }: the sheet
// with the economics fields refused and the server's sentence for it), which the mock serves while the spec's hook key is set.
// --home-v2 records ONLY apps/web/mocks/home_v2/*.json and exits (Home V2 wave 2; the existing Home recordings stay for the flag-off page): for each of seven
// moments the mock chooses among (lib/mock/home-v2.ts), { en, zh } of GET /home (the full read, with its `home_v2` block), GET /worklist and GET /customers:
//   day0        the opening books, nothing read, the plan ready and not run (worklist: the alert, no rows, two customers)
//   offer       the opening books with the package offer received and read by FLOW (Needs you holds the Foshan decision; the plan still ready)
//   deal        the deal made on day 0 (FLOW's counter sent and Foshan accepted it), nothing else moved yet: the books the Home shows once Foshan has agreed
//   after_fund  the day-0 plan has run (FUNDING ARRANGED; Waiting holds the invoice financing not yet landed)
//   day34       the deal made, the day-2 receipt, the clock at day 34 (the late invoice; the reserve alert open with its cure)
//   pending     the day-34 cure queued for the owner's approval
//   after       the cure approved
// and receivables_<point>.json = { en, zh } of GET /receivables (the invoice rows with their breakdown, net after repayment and collection words) at each moment.
// and, for the focus panels (slice 2; deal_title_offer.json = { en, zh } of GET /home?decision= `chart.scenario_title_text`; picture_offer.json = { en, zh } of GET /offers/<EX01>/picture, for the paths' words), focus_<point>.json = { en, zh } of { customers: { <id>: GET /customers/<id>/overview }, deals: { none | asked | counter:0:
// the same read with the open decision and that scenario, so `context` echoes them } } (deals only at `offer`), and exposure_offer.json = { en, zh } of GET /offers/<EX01>/exposure?customer=.
// The API needs the flags above (Home V2 has none):
//   cd services/api && FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_EXPOSURE=1 SKIP_PERF_BENCH=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8182
//   node scripts/record-mocks.mjs --api http://localhost:8182 --home-v2
//
// Verified by running the recorder twice on the same API and on two fresh APIs: `git status --short apps/web/mocks` is empty.
//
// --tracker records ONLY apps/web/mocks/tracker/<moment>.json, { en, zh } of GET /decisions/{id}/tracker for the story's deal (Deal tracker, map #148), and exits.
// The moments are walked with the stepper's own calls: offer (the offer read and evaluated, not agreed: the `available: false` answer), agreed (day 0, right
// after the agreement), receipt (day 2, after the bank receipt), late (day 34), pending (the cure queued for approval), approved (the owner approved it) and
// settled (day 38) and ended (the rest of the invoice paid through the bank feed, so every invoice on the deal is paid: the close-out). lib/mock/tracker.ts chooses among them by the mock's own story state. The API needs the recording environment above:
//   cd services/api && SKIP_PERF_BENCH=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8241
//   node scripts/record-mocks.mjs --api http://localhost:8241 --tracker

// --buyer-message records ONLY apps/web/mocks/buyer_message.json and exits (the message the owner sends the buyer outside FLOW, ADR-0011 addendum). Each walk starts
// on fresh books with the package offer (EX01) read and evaluated, and runs once with the page in each language (`en`, `zh`); every entry is { en, zh } by the page's language:
//   message            { <counter>: { <page>: { en, zh } } }  GET .../counters/<counter>/message?lang=<buyer>&ui_lang=<page> for every reply, before anything is marked sent
//   ready              GET /decisions/deal:<id> before anything is marked sent (the deal's history so far)
//   message_changed    the 409 MESSAGE_CHANGED of a mark with a hash that is not the message's
//   offered            POST .../offered for the recommended reply (the message in English)
//   awaiting           { decision, deals, worklist, message }: the reads once it is marked sent (`message` is the offered reply's, with `offered`)
//   offer_sent_outside the 409 OFFER_SENT_OUTSIDE of the simulated send once the offer is out
//   buyer_accepted     POST .../buyer-accepted; accepted { decision, deals, worklist, tracker }: the reads after it
//   buyer_declined     POST .../buyer-declined with reason DISCOUNT_TOO_LOW; declined { decision, deals, worklist }
//   no_terms           the 409 NO_TERMS_IN_REPLY of a reply with no terms in it
//   buyer_reply        POST /offers/<id>/buyer-reply with the section's REPLY_TEXT; replied { decision, deals, worklist, reply_decision, reply_offer }
//   no_answer          { decision, deals, worklist } once the clock is past the day the offer was open until; offer_expired: the 409 OFFER_EXPIRED of a no recorded then
//   no_simulated_buyer the 409 NO_SIMULATED_BUYER of the simulated send for a buyer with no simulated profile (EX09, BUYER-3)
// The API needs the recording environment above:
//   cd services/api && SKIP_PERF_BENCH=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 PYTHONUTF8=1 uv run uvicorn app.main:app --port 8531
//   node scripts/record-mocks.mjs --api http://localhost:8531 --buyer-message

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
  console.log("usage: node scripts/record-mocks.mjs [--api http://localhost:8011] [--out apps/web/mocks] [--strategy | --overview | --buyer-exposure | --exposure | --home-v2 | --slice-d | --tracker | --buyer-message]\n(start the API first, see the header of this file; never use port 8000)");
  process.exit(0);
}
const API = arg("--api", "http://localhost:8011").replace(/\/+$/, "");
const OUT = resolve(arg("--out", join(here, "..", "mocks")));
const STRATEGY = process.argv.includes("--strategy");
const EXPOSURE = process.argv.includes("--exposure");
const OVERVIEW = process.argv.includes("--overview");
const BUYER_EXPOSURE = process.argv.includes("--buyer-exposure");
const HOME_V2 = process.argv.includes("--home-v2");
const TRACKER = process.argv.includes("--tracker");
const NO_EXPOSURE = process.argv.includes("--no-exposure");
const INPUTS = process.argv.includes("--inputs");
const SLICE_D = process.argv.includes("--slice-d");
const BUYER_MESSAGE = process.argv.includes("--buyer-message");
const OWNER_TOKEN = "demo-owner-token";
const BANK = { "X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key" };

register("./ts-resolve-hook.mjs", import.meta.url);
process.env.NEXT_PUBLIC_API_URL = API;
process.env.NEXT_PUBLIC_API_MODE = "live";
const { setOwnerToken } = await import("../lib/auth.ts");
const { live } = await import("../lib/live/index.ts");
const { setLang } = await import("../lib/i18n.ts");
const demoModule = await import("../lib/demo.ts");
const { demoStore, clearDemo, recordFunding, recordNegotiation, selectOffer, bump } = await import("../lib/demo-store.ts");
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
/** Runs `read` with the UI language set to `lang` (the adapters add it to every route that takes one), then puts English back. */
async function inLang(lang, read) {
  setLang(lang);
  try {
    return await read();
  } finally {
    setLang("en");
  }
}

const RECHAIN_BY_APPEARANCE = new Set(["slice_d/activity.json", "slice_d/story.json", "slice_d/restore.json", "nl_script.json", "home_reconciliation_day2.json", "bank_receipt.json", "home_reconciliation_day34.json", "home_reconciliation_day34_half.json", "home_ledger_day34.json", "home_ledger_approved.json", "decisions.json"]);
const lossTokens = new Map(); // slice_d file -> its loss tokens, by order of first appearance
const nlIds = new Map(); // NL-<16 hex> operation / lot ids, which the API derives from a random session nonce -> a fixed id by first appearance
const secIds = new Map(); // SEC-<KIND>-<16 hex> security event ids, random per event since the security fixes -> a fixed id by first appearance
const nlDecisionIds = new Map(); // nl:<topic>:t<n>:<12 hex> recorded chat decisions, keyed by a random session nonce -> a fixed id by first appearance

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

/**
 * The restore history (`alternate.history`) is a list the API keeps in memory for as long as it runs, so it grows with every recording made against the same process:
 * its entries also carry relative times ("21 minutes ago"), so the recording keeps none (the mock shows no history) and a second run on the same API changes nothing.
 */
function trimRestoreHistory(name, root) {
  const visit = (node) => {
    if (Array.isArray(node)) node.forEach(visit);
    else if (node && typeof node === "object") {
      if (Array.isArray(node.history) && node.history.every((h) => h && typeof h.text === "string")) node.history = [];
      Object.values(node).forEach(visit);
    }
  };
  visit(root);
}

function normalise(name, value) {
  const text = JSON.stringify(value)
    // slice_d/*: a funding decision's id ends in the books' state version (alert:ALERT-RESERVE-42:v6), which depends on how many reads came before it; the mock's decision
    // recordings (decisions.json) name the same record as v7, so the walk's id is made the same one.
    .replace(/alert:(ALERT-[A-Z]+-\d+):v\d+/g, (m, id) => (name.startsWith("slice_d/") ? `alert:${id}:v7` : m))
    // slice_d/*: a loss token is a fingerprint of the books the API holds, including the restore history it accumulates for as long as it runs; it is made a fixed token by
    // order of first appearance (the mock compares a confirmation with the token of the same recording, so only which books share a token matters).
    .replace(/"loss_token":"([0-9a-f]+)"/g, (m, tok) => {
      if (!name.startsWith("slice_d/")) return m;
      if (!lossTokens.has(name)) lossTokens.set(name, new Map());
      const seen = lossTokens.get(name);
      if (!seen.has(tok)) seen.set(tok, sha(`recorded loss token ${seen.size}`).slice(0, 16));
      return `"loss_token":"${seen.get(tok)}"`;
    })
    .replace(/CMT-[0-9a-f]{16}/g, FIXED_CMT)
    .replace(/ALERT-EARLYPAY-[0-9a-f]{12}/g, `ALERT-EARLYPAY-${sha("recorded early-pay alert").slice(0, 12)}`)
    .replace(/NL-[0-9a-f]{16}/g, (id) => {
      if (!nlIds.has(id)) nlIds.set(id, `NL-${sha(`recorded nl id ${nlIds.size}`).slice(0, 16)}`);
      return nlIds.get(id);
    })
    .replace(/SEC-([A-Z]+)-([0-9a-f]{16})/g, (id, kind) => {
      if (!secIds.has(id)) secIds.set(id, `SEC-${kind}-${sha(`recorded security event ${secIds.size}`).slice(0, 16)}`);
      return secIds.get(id);
    })
    .replace(/(nl:[a-z0-9-]+:t\d+:)([0-9a-f]{12})/g, (m, head) => {
      if (!nlDecisionIds.has(m)) nlDecisionIds.set(m, `${head}${sha(`recorded nl decision ${nlDecisionIds.size}`).slice(0, 12)}`);
      return nlDecisionIds.get(m);
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
  if (name.startsWith("strategy/") || name.startsWith("receivables/") || name.startsWith("buyer_exposure")) out.computed_in_seconds = 0;
  if (RECHAIN.has(name)) rechain(out);
  if (RECHAIN_BY_APPEARANCE.has(name)) rechainByAppearance(name, out);
  if (name.startsWith("slice_d/")) trimRestoreHistory(name, out);
  return out;
}

function write(name, value) {
  writeFileSync(join(OUT, name), JSON.stringify(normalise(name, value), null, 2) + "\n");
  written.push(name);
}
// The recorder walks the engine's own sequences, not the six scenes the Demo tells (lib/demo.ts DEMO_STEPS): the mocks hold every screen the
// engine has, so each of its steps is run here in the order docs/DEMO_FLOW.md gives, through the same helpers the Demo's optional scenes use.
const { submitSample, evaluate, runCapex, runCapexApply, runBorrowerFile, runSecurityScene, runWalkAway } = demoModule;
const { planFunding, negotiate } = live;
const noop = async () => {};
const ENGINE_STEPS = [
  { id: "mandate", run: async () => { await live.demoReset(); clearDemo(); } },
  { id: "inbox", run: async () => void (await submitSample("EX01")) },
  { id: "trajectory", run: async () => { const id = demoStore.get().offerId; if (id) await evaluate(id); } },
  { id: "funding", run: async () => recordFunding(await planFunding({})) },
  { id: "verdict", run: noop },
  { id: "negotiate", run: async () => { const id = demoStore.get().offerId; if (id) recordNegotiation(await negotiate(id, { buyer_profile: "cooperative" })); } },
  { id: "ledger1", run: async () => bump() },
  { id: "walk", run: runWalkAway },
  { id: "router", run: noop },
  { id: "ledger2", run: async () => bump() },
  {
    id: "reworded",
    run: async () => {
      const prepared = demoStore.get().rewordedId;
      if (prepared) return selectOffer(prepared);
      await evaluate(await submitSample("EX01B"));
    },
  },
  { id: "capex", run: runCapex },
  { id: "approval", run: async () => { await runCapexApply(); await runBorrowerFile(); } },
  { id: "fastcapital", run: runSecurityScene },
  { id: "evidence", run: async () => bump() },
];
const step = (id) => ENGINE_STEPS.find((s) => s.id === id);

// ------------------------------------------------------------------ the decision record: named snapshots in both languages
const decisions = {};
const dealId = (offerId) => `deal:${offerId}`;
async function snap(name, id) {
  if (!id) throw new Error(`snapshot ${name}: no decision id`);
  decisions[name] = { en: await live.getDecision(id, "en"), zh: await live.getDecision(id, "zh") };
}
/** The 409 COUNTER_CHANGED detail a bound send gets, or a failure when the API accepted it. */
async function refusedSend(offerId, body) {
  try {
    await live.negotiate(offerId, body);
  } catch (e) {
    if (e?.status === 409 && e.detail?.code === "COUNTER_CHANGED") return e.detail;
    throw e;
  }
  throw new Error("the bound send was accepted: the story needs a send the API refuses");
}
const demo = () => demoStore.get();

/** An operation as the mock ledger replays it: what the server said (the executor's sentence and its Business twin), without the position in the chain. */
function template(op) {
  return { kind: op.kind, status: op.status, tier: op.tier, requested_by: op.requested_by, message: op.message, summary: op.summary, message_when: op.message_when ?? null, event_text: op.event_text ?? null, event_detail: op.event_detail ?? null, decision_id: op.decision_id ?? null };
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
mkdirSync(join(OUT, "receivables"), { recursive: true });
/** GET /buyers/BUYER-1/exposure (the aside's late-payment test with no deal), in both languages, at the opening books and at day 34. */
async function buyerExposure(name) {
  if (NO_EXPOSURE) return; // the home is recorded with the exposure flag off (its stress is then absent, as the specs expect); the exposure files come from a run with it on
  for (const [suffix, lang] of [["", "en"], ["_zh", "zh"]]) {
    const view = await live.getBuyerExposure("BUYER-1", lang);
    if (!view) throw new Error("GET /buyers/{id}/exposure is off: start the API with FEATURE_EXPOSURE=1 from a branch that carries it (feat/connected-words)");
    files[`${name}${suffix}.json`] = view;
  }
}
/** GET /receivables at this point of the story, in both languages (the mock chooses among them as it chooses the home summary). */
async function recvRead(point) {
  for (const [suffix, lang] of [["", "en"], ["_zh", "zh"]]) {
    const view = await live.getReceivables(lang);
    if (!view || !Array.isArray(view.rows)) throw new Error("GET /receivables is absent: start the API from a branch that carries it (feat/net-collection)");
    files[`receivables/${point}${suffix}.json`] = view;
  }
}

// --buyer-exposure: buyer_exposure[_zh].json and nothing else, on the opening books.
if (BUYER_EXPOSURE) {
  await live.demoReset();
  await buyerExposure("buyer_exposure");
  for (const name of Object.keys(files).sort()) write(name, files[name]);
  console.log(`recorded ${written.length} buyer-exposure files into ${OUT} from ${API}`);
  process.exit(0);
}
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

// --exposure: the one exposure recording and nothing else (see the header).
if (EXPOSURE) {
  await reset();
  const id = await submitSample("EX01");
  await evaluate(id);
  const [en, zh] = [await live.getOfferExposure(id, "en"), await live.getOfferExposure(id, "zh")];
  if (!en || !zh) throw new Error("the exposure route is off: start the API with FEATURE_EXPOSURE=1");
  // The seconds the call and each spare-capacity search took are timings, not answers.
  const stamp = (v) => {
    const out = JSON.parse(JSON.stringify(v));
    out.computed_in_seconds = 0;
    for (const c of Object.values(out.capacity ?? {})) if (c?.spare) c.spare.seconds = 0;
    return out;
  };
  files["offer_exposure_ex01.json"] = { en: stamp(en), zh: stamp(zh) };
  // The deals read opened with a customer (`GET /deals?customer=BUYER-1&path=<the recommended counter>`): the open offer then carries `context.back`.
  const pic = await live.getOfferPicture(id, "en");
  const recommended = pic.paths?.find((p) => p.recommended)?.key;
  files["deals_day0_evaluated_back.json"] = await live.getDeals("en", { customer: "BUYER-1", path: recommended });
  // The same offer's picture with the exposure read on (round three: its `scenarios[]` are composed from the exposure and compare reads); the mock serves it while the exposure is on.
  files["offer_picture_ex01_exposure.json"] = { en: pic, zh: await live.getOfferPicture(id, "zh") };
  // The scenarios behind Cash impact's Business consequences are their own read now (GET /offers/{id}/scenarios).
  files["offer_scenarios_ex01.json"] = { en: await live.getOfferScenarios(id, "en"), zh: await live.getOfferScenarios(id, "zh") };
  await live.demoReset();
  for (const name of Object.keys(files)) write(name, files[name]);
  console.log(`recorded ${written.join(", ")} into ${OUT} from ${API}`);
  process.exit(0);
}

// --inputs: the owner's Inputs sheet for the demo's first buyer and nothing else (see the header).
if (INPUTS) {
  const BUYER = "BUYER-1";
  const both = async (read) => ({ en: await read("en"), zh: await read("zh") });
  if (process.argv.includes("--economics-off")) {
    await reset();
    const off = await both((lang) => live.getBuyerInputs(BUYER, lang));
    if (off.en.economics_on !== false) throw new Error("the economics fields are on: start the API without FEATURE_CUSTOMER_ECONOMICS");
    await live.demoReset();
    write("buyer_inputs_off.json", off);
    console.log(`recorded buyer_inputs_off.json into ${OUT} from ${API}`);
    process.exit(0);
  }
  const refused = async (lang) => {
    try {
      await live.saveInput(BUYER, { field: "margin_bp", value_text: "150%", provenance: "OWNER_ENTERED" }, lang);
    } catch (e) {
      if (e?.status === 422) return { status: 422, detail: e.detail };
      throw e;
    }
    throw new Error("a margin of 150% was accepted: the sheet needs the API to refuse it");
  };
  await reset();
  const out = {};
  out.opening = await both((lang) => live.getBuyerInputs(BUYER, lang));
  if (!out.opening.en.economics_on) throw new Error("the economics fields are off: start the API with FEATURE_CUSTOMER_ECONOMICS=1");
  out.firm = await both(async (lang) => {
    const r = await fetch(`${API}/firm/inputs?lang=${lang}`, { headers: { "X-Owner-Token": OWNER_TOKEN } });
    if (!r.ok) throw new Error(`GET /firm/inputs answered ${r.status}`);
    return r.json();
  });
  out.overview_before = await both((lang) => live.getCustomerOverview(BUYER, lang));
  out.rejected = await both(refused);
  out.saved_margin = await both(async (lang) => {
    await reset();
    return live.saveInput(BUYER, { field: "margin_bp", value_text: "25%", provenance: "OWNER_ENTERED" }, lang);
  });
  out.after_margin = await both((lang) => live.getBuyerInputs(BUYER, lang));
  out.overview_after = await both((lang) => live.getCustomerOverview(BUYER, lang));
  await live.demoReset();
  write("buyer_inputs.json", out);
  console.log(`recorded buyer_inputs.json into ${OUT} from ${API}`);
  process.exit(0);
}

// --overview: the customer overview of the demo's first buyer and nothing else (see the header).
if (OVERVIEW) {
  const BUYER = "BUYER-1";
  // --exposure-off (the API started without FEATURE_EXPOSURE): the opening books' overview with its exposure panel off and the server's note for it.
  if (process.argv.includes("--exposure-off")) {
    await reset();
    const off = { en: await live.getCustomerOverview(BUYER, "en"), zh: await live.getCustomerOverview(BUYER, "zh") };
    if (off.en.exposure || !off.en.note) throw new Error("the exposure is on: start the API without FEATURE_EXPOSURE");
    await live.demoReset();
    write("customer_overview_exposure_off.json", off);
    console.log(`recorded customer_overview_exposure_off.json into ${OUT} from ${API}`);
    process.exit(0);
  }
  const queryOf = (href) => Object.fromEntries(new URL(href, "http://flow.local").searchParams);
  const read = async (lang) => {
    const view = await live.getCustomerOverview(BUYER, lang);
    if (!view.exposure) throw new Error("the exposure panel is off: start the API with FEATURE_EXPOSURE=1");
    const backs = [];
    const ask = async (query) => backs.push({ query, back: (await live.getCustomerOverview(BUYER, lang, query)).context.back });
    if (view.decision) {
      const { decision, path } = queryOf(view.decision.primary.href);
      await ask({ decision });
      if (path) await ask({ decision, path });
    }
    const invoices = view.actions.find((a) => a.key === "invoices");
    if (invoices && queryOf(invoices.href).invoice) await ask({ invoice: queryOf(invoices.href).invoice });
    return { view, backs };
  };
  const moment = async () => ({ en: await read("en"), zh: await read("zh") });
  const moments = {};
  await reset();
  moments.quiet = await moment();
  await step("inbox").run();
  moments.offer_received = await moment();
  await step("trajectory").run();
  moments.offer_evaluated = await moment();
  // The day-0 plan, as the home's "Go ahead" runs it on the opening books: the financing is arranged.
  await reset();
  {
    const a = (await live.getHome("en")).next_action;
    await live.actOnAlert(a.alert_id, { state_version: a.state_version, suggestions: a.suggestions });
    moments.after_fund = await moment();
  }
  await toDay34();
  moments.day34 = await moment();
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
  moments.day34_after = await moment();
  await live.demoReset();
  write("customer_overview.json", moments);
  console.log(`recorded customer_overview.json into ${OUT} from ${API}`);
  process.exit(0);
}

// --slice-d: GET /activity, GET /demo/story and POST /demo/restore at the moments the mock walks through, and nothing else (see the header).
if (SLICE_D) {
  mkdirSync(join(OUT, "slice_d"), { recursive: true });
  const both = async (read) => ({ en: await read("en"), zh: await read("zh") });
  const story = {};
  const activity = {};
  const takeActivity = async (key) => void (activity[key] = await both((lang) => live.getActivity(lang)));
  const takeStory = async (key, seen) => void (story[key] = await both((lang) => live.getDemoStory(lang, seen)));
  await reset();
  await takeStory("fresh");
  await takeActivity("fresh");
  const refuse = async () => {
    const res = await fetch(`${API}/ledger`, { headers: { "X-Owner-Token": "not-the-owner-key" } });
    if (res.status !== 401 && res.status !== 403) throw new Error(`a wrong owner key was not refused (${res.status})`);
  };
  let seenView;
  for (const [i, st] of demoModule.DEMO_STEPS.entries()) {
    if (st.owner) {
      // The owner's own click, pressed here by the recorder (authoring tooling), exactly as the stepper section above does.
      const row = (await live.getApprovals()).find((a) => a.status === "PENDING");
      if (!row) throw new Error("the cure is not waiting for the owner: the demo path has changed");
      await live.decideApproval(row.id, "APPROVE");
    } else {
      const values = await st.run();
      void values;
    }
    // `seen` is the last view step (cash, outcome, proof) the browser has shown, which is all the Demo page sends.
    if (["cash", "outcome", "proof"].includes(st.id)) seenView = st.id;
    await takeStory(st.id, seenView);
    if (["ask", "decide", "agree", "bank", "time", "queue", "approve", "settle"].includes(st.id)) await takeActivity(st.id);
    void i;
  }
  // Settled books plus two refused sign-ins and the FastCapital scene: the benign summary beside a real alert.
  await refuse();
  await refuse();
  await runSecurityScene();
  await takeActivity("security");
  const audit = await live.getAudit(); // the security view of the same moment: its event ids are the ones the Activity rows link to
  // The stale-page guard's two refusals, as the API words them (the mock answers the same two from its own state): work on the books not confirmed, and books that are another.
  const refusal = async (query, lang) => {
    const res = await fetch(`${API}/demo/reset?${query}&lang=${lang}`, { method: "POST", headers: { "X-Owner-Token": OWNER_TOKEN, "Content-Type": "application/json" }, body: "{}" });
    if (res.status !== 409) throw new Error(`the guard did not refuse (${res.status}): ${query}`);
    const { detail } = await res.json();
    return { message: detail.message, message_when: detail.message_when };
  };
  const guard = { loss_not_confirmed: await both((lang) => refusal("from_scenario=golden_sme", lang)), loss_changed: await both((lang) => refusal("from_scenario=golden_sme&confirm_loss=1", lang)) };
  // The busy company, and the one-click restore made on it.
  await live.demoReset("busy");
  clearDemo();
  await takeStory("busy");
  await takeActivity("busy");
  const restore = await both((lang) => live.restoreDemo(lang));
  // The short-facilities books (the third card of "Which books?"): the story and Activity reads on them, like the busy company's.
  await live.demoReset("short_facilities");
  clearDemo();
  await takeStory("short");
  await takeActivity("short");
  await live.demoReset();
  guard.books_changed = await both((lang) => refusal("from_scenario=busy", lang));
  write("slice_d/story.json", story);
  write("slice_d/activity.json", activity);
  write("slice_d/restore.json", restore);
  write("slice_d/audit.json", audit);
  write("slice_d/guard.json", guard);
  console.log(`recorded ${written.length} files into ${join(OUT, "slice_d")} from ${API}`);
  process.exit(0);
}

// --tracker: the deal tracker at eight moments of the golden story and nothing else (see the header).
if (TRACKER) {
  mkdirSync(join(OUT, "tracker"), { recursive: true });
  const { getTracker } = await import("../lib/tracker.ts");
  let deal = null;
  const keep = async (moment) => {
    const en = await getTracker(deal, "en");
    const zh = await getTracker(deal, "zh");
    if (!en || !zh) throw new Error(`the tracker read is absent at ${moment}: the API is older than the deal tracker`);
    write(`tracker/${moment}.json`, { en, zh });
  };
  await reset();
  await step("inbox").run();
  await step("trajectory").run();
  deal = dealId(demoStore.get().offerId);
  await keep("offer");
  await step("negotiate").run();
  await keep("agreed");
  await live.advanceClock(2);
  await bankReceipt();
  await keep("receipt");
  await live.advanceClock(28);
  await live.advanceClock(4);
  await keep("late");
  {
    const alerts = await live.getAlerts();
    const reserve = alerts.alerts.find((x) => x.id.startsWith("ALERT-RESERVE") && x.actionable);
    if (!reserve) throw new Error("no actionable reserve alert on day 34: the demo path has changed");
    await live.actOnAlert(reserve.id, {
      state_version: alerts.state_version,
      suggestions: reserve.suggested.map((x) => ({ operation_kind: x.operation_kind, facility_id: x.facility_id, receivable_id: x.receivable_id, amount_fen: x.amount_fen })),
    });
    await keep("pending");
    await live.decideApproval((await live.getApprovals())[0].id, "APPROVE");
    await keep("approved");
  }
  await live.advanceClock(38 - 34);
  await keep("settled");
  {
    // The rest of the invoice, paid through the bank feed's own route (as the server's test does): every invoice on the deal is paid, so the deal has ended.
    const rest = (await live.getState()).state.receivables.find((r) => r.id === "RCV-A");
    const version = (await live.getMandate()).mandate.version;
    const res = await fetch(`${API}/operations`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Owner-Token": OWNER_TOKEN, ...BANK },
      body: JSON.stringify({ kind: "RECEIVE_PAYMENT", op_id: "rec-rest", idempotency_key: "rec-rest", mandate_version: version, requested_by: "SYSTEM", receivable_id: "RCV-A", amount_fen: rest.face_fen - (rest.settled_fen ?? 0), bank_reference: "DEMO-RCPT-REST" }),
    });
    if (!res.ok) throw new Error(`the rest of the invoice was not paid: ${res.status} ${await res.text()}`);
    await keep("ended");
  }
  await live.demoReset();
  console.log(`recorded ${written.length} tracker files into ${join(OUT, "tracker")} from ${API}`);
  process.exit(0);
}

// --buyer-message: the message to the buyer, marked sent, and each way the offer can end, and nothing else (see the header).
if (BUYER_MESSAGE) {
  const { getTracker } = await import("../lib/tracker.ts");
  const REPLY_TEXT = "We can pay the 420,000 invoice early, but only with a 1.2% discount, and we need 60-day terms on future invoices.";
  const LANGS = ["en", "zh"];
  /** The 409 detail of a call the story needs refused, with its code; a failure when the API accepted it. */
  const refused = async (code, call) => {
    try {
      await call();
    } catch (e) {
      if (e?.status === 409 && e.detail?.code === code) return e.detail;
      throw e;
    }
    throw new Error(`the API accepted a call the story needs refused with ${code}`);
  };
  /** Fresh books with the package offer read and evaluated: its id, the verdict, and the reply FLOW recommends. */
  const fresh = async () => {
    await reset();
    const offerId = await submitSample("EX01");
    await evaluate(offerId);
    const verdict = demoStore.get().verdicts[offerId];
    const picture = await live.getOfferPicture(offerId, "en");
    const replies = picture.paths.filter((p) => p.kind === "reply");
    const rec = replies.find((p) => p.recommended) ?? replies[0];
    if (!verdict || !rec) throw new Error("the package offer has no verdict or no reply: the demo path has changed");
    return { offerId, verdict, replies, rec };
  };
  /** Fresh books with the recommended reply marked sent (the message in English), the page in `lang`. */
  const sentOne = async (lang) => {
    const f = await fresh();
    const msg = await live.getBuyerMessage(f.offerId, f.rec.key, "en", "en");
    if (!msg.message_hash) throw new Error(`no message for ${f.rec.key}: ${msg.blocked?.code}`);
    const offered = await inLang(lang, () =>
      live.markOffered(f.offerId, f.rec.key, { verdict_id: f.verdict.id, state_version: f.verdict.state_version, message_hash: msg.message_hash, lang: "en" }),
    );
    return { ...f, offered, hash: msg.message_hash };
  };
  const reads = async (offerId, lang, more = {}) => ({
    decision: await live.getDecision(dealId(offerId), lang),
    deals: await inLang(lang, () => live.getDeals(lang)),
    worklist: await inLang(lang, () => live.getWorklist(lang)),
    ...more,
  });
  const out = {
    message: {}, ready: {}, message_changed: {}, offered: {}, awaiting: {}, offer_sent_outside: {}, buyer_accepted: {}, accepted: {}, buyer_declined: {}, declined: {},
    no_terms: {}, buyer_reply: {}, replied: {}, no_answer: {}, offer_expired: {}, no_simulated_buyer: {},
  };
  for (const lang of LANGS) {
    // The send review: the message of every reply, the page in `lang`, the buyer in either language; a mark with a hash that is not the message's is refused.
    const { offerId, verdict, replies, rec } = await fresh();
    for (const p of replies) {
      out.message[p.key] ??= {};
      out.message[p.key][lang] = { en: await live.getBuyerMessage(offerId, p.key, "en", lang), zh: await live.getBuyerMessage(offerId, p.key, "zh", lang) };
    }
    out.ready[lang] = await live.getDecision(dealId(offerId), lang);
    out.message_changed[lang] = await refused("MESSAGE_CHANGED", () =>
      inLang(lang, () => live.markOffered(offerId, rec.key, { verdict_id: verdict.id, state_version: verdict.state_version, message_hash: "0".repeat(64), lang: "en" })),
    );
  }
  for (const lang of LANGS) {
    // Marked sent, then the buyer's yes. A simulated send once the offer is out is refused.
    const { offerId, verdict, rec, offered, hash } = await sentOne(lang);
    out.offered[lang] = offered;
    out.awaiting[lang] = await reads(offerId, lang, { message: await live.getBuyerMessage(offerId, rec.key, "en", lang) });
    out.offer_sent_outside[lang] = await refused("OFFER_SENT_OUTSIDE", () => inLang(lang, () => live.negotiate(offerId, { buyer_profile: "cooperative" })));
    out.buyer_accepted[lang] = await inLang(lang, () => live.buyerAccepted(offerId, rec.key, { verdict_id: verdict.id, state_version: out.awaiting[lang].message.state_version, message_hash: hash }));
    out.accepted[lang] = await reads(offerId, lang, { tracker: await getTracker(dealId(offerId), lang) });
  }
  for (const lang of LANGS) {
    // Marked sent, then the buyer's no, with a reason.
    const { offerId, verdict, rec, hash } = await sentOne(lang);
    out.buyer_declined[lang] = await inLang(lang, () => live.buyerDeclined(offerId, rec.key, { verdict_id: verdict.id, message_hash: hash, reason: "DISCOUNT_TOO_LOW" }));
    out.declined[lang] = await reads(offerId, lang);
  }
  for (const lang of LANGS) {
    // Marked sent, then the buyer's reply: refused with no terms in it, then read as a request of its own.
    const { offerId, verdict, rec } = await sentOne(lang);
    out.no_terms[lang] = await refused("NO_TERMS_IN_REPLY", () => inLang(lang, () => live.buyerReply(offerId, { verdict_id: verdict.id, counter_id: rec.key, text: "Thanks, sounds good." })));
    out.buyer_reply[lang] = await inLang(lang, () => live.buyerReply(offerId, { verdict_id: verdict.id, counter_id: rec.key, text: REPLY_TEXT }));
    const reply = out.buyer_reply[lang];
    out.replied[lang] = await reads(offerId, lang, { reply_decision: await live.getDecision(reply.reply_decision_id, lang), reply_offer: await live.getOffer(reply.reply_offer_id, lang) });
  }
  for (const lang of LANGS) {
    // Marked sent and never answered: the clock moves past the day the offer is open until, and the offer closes as no deal; a no recorded after it is refused.
    const { offerId, verdict, rec, offered, hash } = await sentOne(lang);
    await live.advanceClock(offered.offered.valid_until_day + 1);
    out.no_answer[lang] = await reads(offerId, lang);
    out.offer_expired[lang] = await refused("OFFER_EXPIRED", () => inLang(lang, () => live.buyerDeclined(offerId, rec.key, { verdict_id: verdict.id, message_hash: hash, reason: "NO_REASON" })));
  }
  {
    // A buyer with no simulated profile (EX09 is BUYER-3's): the simulated send is refused and nothing is sent.
    await reset();
    const other = (await live.submitOffer({ fixture_id: "EX09_TERMS_BUYER3" })).offer.offer_id;
    await live.evaluateOffer(other, "EX09_TERMS_BUYER3", "en");
    for (const lang of LANGS) out.no_simulated_buyer[lang] = await refused("NO_SIMULATED_BUYER", () => inLang(lang, () => live.negotiate(other, { buyer_profile: "cooperative" })));
  }
  write("buyer_message.json", out);
  await live.demoReset();
  console.log(`recorded ${written.join(", ")} into ${OUT} from ${API}`);
  process.exit(0);
}

// --home-v2: the Home V2 reads at six moments and nothing else (see the header).
if (HOME_V2) {
  mkdirSync(join(OUT, "home_v2"), { recursive: true });
  const reads = async () => {
    const both = async (read) => ({ en: await inLang("en", () => read("en")), zh: await inLang("zh", () => read("zh")) });
    const home = await both((lang) => live.getHome(lang));
    if (!home.en.home_v2) throw new Error("the Home read carries no home_v2: the API is older than Home V2");
    const receivables = await both((lang) => live.getReceivables(lang)); // the invoice rows: the breakdown, the net after repayment and the collection words the Home's invoice card shows
    const worklist = await both((lang) => live.getWorklist(lang));
    const customers = await both((lang) => live.getCustomers(lang));
    if (!worklist.en || !customers.en) throw new Error("GET /worklist or /customers is absent: the API is older than Home V2");
    // The focus panels' reads: every customer's overview, and at the point where an offer is open its deal under each scenario and its exposure.
    const decisionRow = worklist.en.needs_you.find((r) => r.kind === "DECISION");
    const focusOf = async (lang) => {
      const customers = {};
      for (const c of worklist[lang].customers) customers[c.customer_id] = await live.getCustomerFocus(c.customer_id, lang);
      const deals = {};
      if (decisionRow) for (const scenario of [null, "asked", "counter:0"]) deals[scenario ?? "none"] = await live.getCustomerFocus(decisionRow.customer_id, lang, { decision: decisionRow.key, scenario });
      return { customers, deals };
    };
    const focus = { en: await focusOf("en"), zh: await focusOf("zh") };
    const exposure = decisionRow
      ? { en: await live.getDealExposure(decisionRow.key.slice("deal:".length), "en", decisionRow.customer_id), zh: await live.getDealExposure(decisionRow.key.slice("deal:".length), "zh", decisionRow.customer_id) }
      : null;
    const picture = decisionRow ? { en: await live.getOfferPicture(decisionRow.key.slice("deal:".length), "en"), zh: await live.getOfferPicture(decisionRow.key.slice("deal:".length), "zh") } : null;
    const title = decisionRow ? { en: await live.getDealTitle(decisionRow.key, "en"), zh: await live.getDealTitle(decisionRow.key, "zh") } : null;
    return { home, worklist, customers, focus, exposure, picture, title, receivables };
  };
  const keep = (point, got) => {
    for (const kind of ["home", "worklist", "customers", "focus", "receivables"]) write(`home_v2/${kind}_${point}.json`, got[kind]);
    if (point !== "offer") return; // the deal's own reads belong to the moment its offer is open
    if (got.exposure) write("home_v2/exposure_offer.json", got.exposure);
    if (got.picture) write("home_v2/picture_offer.json", got.picture);
    if (got.title) write("home_v2/deal_title_offer.json", got.title);
  };
  await reset();
  keep("day0", await reads());
  await step("inbox").run();
  await step("trajectory").run();
  keep("offer", await reads());
  // The deal made on day 0: the counter sent and accepted (the same step the day-34 walk takes), read before the clock moves.
  await step("negotiate").run();
  keep("deal", await reads());
  // The day-0 plan, as the home's "Go ahead" runs it on the opening books.
  await reset();
  {
    const a = (await live.getHome("en")).next_action;
    await live.actOnAlert(a.alert_id, { state_version: a.state_version, suggestions: a.suggestions });
    keep("after_fund", await reads());
  }
  // Day 34 (the deal, the day-2 receipt, the clock to day 34: the late invoice and the reserve alert open), then the cure queued for the owner's approval, then approved.
  await toDay34();
  keep("day34", await reads());
  {
    const alerts = await live.getAlerts();
    const reserve = alerts.alerts.find((x) => x.id.startsWith("ALERT-RESERVE") && x.actionable);
    if (!reserve) throw new Error("no actionable reserve alert on day 34: the demo path has changed");
    await live.actOnAlert(reserve.id, {
      state_version: alerts.state_version,
      suggestions: reserve.suggested.map((x) => ({ operation_kind: x.operation_kind, facility_id: x.facility_id, receivable_id: x.receivable_id, amount_fen: x.amount_fen })),
    });
    keep("pending", await reads());
    await live.decideApproval((await live.getApprovals())[0].id, "APPROVE");
    keep("after", await reads());
  }
  await live.demoReset();
  console.log(`recorded ${written.length} Home V2 files into ${join(OUT, "home_v2")} from ${API}`);
  process.exit(0);
}

await reset();
files["state.json"] = await live.getState();
const navCounts = {}; // GET /nav/counts at the moments the sidebar shows (the mock chooses among them by its story state)
navCounts.quiet = await live.getNavCounts("en");
files["mandate.json"] = await live.getMandate();
// Opening books: the alerts and reconciliation the owner sees before anything happens, and the home summary (GET /home).
files["alerts.json"] = await live.getAlerts();
files["reconciliation.json"] = await live.getReconciliation();
files["chase_day0.json"] = await chaseAll(files["reconciliation.json"]); // the collection handoff on the opening books (nothing due yet)
files["home_summary_day0.json"] = await live.getHome("en");
files["home_summary_day0_zh.json"] = await live.getHome("zh");
await recvRead("day0");
await buyerExposure("buyer_exposure");
files["trajectory_conservative_day0.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
// The day-0 fix runs alone (Tier 1): the home's "Go ahead" on the opening books, bound to what the home showed.
{
  const a = files["home_summary_day0.json"].next_action;
  files["home_act_day0.json"] = await live.actOnAlert(a.alert_id, { state_version: a.state_version, suggestions: a.suggestions });
  if (files["home_act_day0.json"].executed !== 2) throw new Error("the day-0 fix no longer runs alone: the demo path has changed");
  await snap("cure_day0", files["home_act_day0.json"].decision_id);
  files["home_summary_after_fund.json"] = await live.getHome("en");
  files["home_summary_after_fund_zh.json"] = await live.getHome("zh");
  await recvRead("after_fund");
  files["trajectory_conservative_after_fund.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
}

let verdictEx01 = null;
for (const s of ENGINE_STEPS) {
  await s.run();
  const d = demo();
  if (s.id === "inbox") {
    files["offer_ex01.json"] = d.offers[d.offerId];
    await snap("received.ex01", dealId(d.offerId));
    // The deals read with the offer waiting and FLOW has not read it yet; the sidebar counts that deal.
    files["deals_day0_received.json"] = await live.getDeals();
    navCounts.offer_received = await live.getNavCounts("en");
  }
  if (s.id === "trajectory") {
    verdictEx01 = d.verdicts[d.offerId];
    files["verdict_ex01.json"] = verdictEx01;
    await snap("ready.ex01", dealId(d.offerId));
    // FLOW's read of the package offer, before any reply is sent: the deal's open offer, the sidebar count and the offer's cash picture.
    files["deals_day0_evaluated.json"] = await live.getDeals();
    navCounts.offer_evaluated = await live.getNavCounts("en");
    files["offer_picture_ex01.json"] = { en: await live.getOfferPicture(d.offerId, "en"), zh: await live.getOfferPicture(d.offerId, "zh") };
    // The trajectory page: the position with the offer applied (conservative decides) and the position today (expected).
    files["trajectory_conservative.json"] = await live.getTrajectory("CONSERVATIVE", verdictEx01);
    files["trajectory_expected.json"] = await live.getTrajectory("EXPECTED", verdictEx01);
  }
  if (s.id === "funding") files["funding.json"] = d.funding;
  if (s.id === "negotiate") {
    files["negotiation_accept.json"] = d.negotiations[d.offerId];
    await snap("agreed_day0.ex01", dealId(d.offerId));
    const [accept, draw] = await ledgerTail(2);
    ops.accept_a = template(accept);
    ops.draw_line = template(draw);
  }
  if (s.id === "walk") {
    files["offer_ex01b.json"] = d.offers[d.rewordedId];
    files["verdict_ex01b.json"] = d.verdicts[d.rewordedId];
    files["negotiation_nodeal.json"] = d.negotiations[d.offerId];
    await snap("nodeal.ex01", dealId(d.offerId));
    await snap("ready.ex01b", dealId(d.rewordedId));
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
    await snap("ready.sec", dealId(sec.offer.offer_id));
    files["audit_sec.json"] = await live.getAudit();
  }
}

// ------------------------------------------------------------------ the owner's decisions in the approval queue (ledger rows)
// The decision is recorded on the same books as the stepper's approval step (the stepper replayed up to it), so the
// approved application names the structure the queued one does (the 36-month loan); on untouched books the evaluation
// would select the lease and the approved row would disagree with the queued request.
async function queueOne() {
  await reset();
  for (const s of ENGINE_STEPS) {
    await s.run();
    if (s.id === "approval") break;
  }
  return live.getApprovals();
}
let q = await queueOne();
await snap("apply_pending", q[0].decision_id);
// The decided rows too (their state word and tone come from the server): the mock swaps them in when the owner decides.
files["approvals_seed.json"].apply_loan_approved = await live.decideApproval(q[0].id, "APPROVE");
await snap("apply_approved", q[0].decision_id);
ops.approve_apply_loan = template((await ledgerTail(1))[0]);
q = await queueOne();
files["approvals_seed.json"].apply_loan_rejected = await live.decideApproval(q[0].id, "REJECT");
await snap("apply_rejected", q[0].decision_id);
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
await snap("received.accept", dealId(typed.offer.offer_id));
files["verdict_accept.json"] = await live.evaluateOffer(typed.offer.offer_id);
await snap("ready.accept", dealId(typed.offer.offer_id));
// The other two demo messages, read but not yet checked (the Deals page opens them in this state).
for (const [key, fixture] of [["ex01b", "EX01B_REWORDED"], ["sec", "SEC_DEMO_FASTCAPITAL"]]) {
  const read = await live.submitOffer({ fixture_id: fixture });
  await snap(`received.${key}`, dealId(read.offer.offer_id));
}

// ------------------------------------------------------------------ Wave 2: a bound send the API refuses (409 COUNTER_CHANGED), two ways
// Replaced: the verdict the owner read is no longer the latest (the current counters come back). Moved: the books moved after the evaluation
// (the day-0 fix ran), so the counters are no longer safe to show and the answer says to evaluate again.
await reset();
{
  const read = await live.submitOffer({ fixture_id: "EX01_PACKAGE" });
  const verdict = await live.evaluateOffer(read.offer.offer_id, "EX01_PACKAGE");
  const replaced = await refusedSend(read.offer.offer_id, { buyer_profile: "cooperative", verdict_id: "VER-replaced", counter_id: verdict.counters[0].id, state_version: verdict.state_version });
  if (replaced.reason !== "VERDICT_CHANGED" || !replaced.counters.length) throw new Error("the replaced-verdict story changed: the API has changed");
  const home = await live.getHome("en");
  await live.actOnAlert(home.next_action.alert_id, { state_version: home.next_action.state_version, suggestions: home.next_action.suggestions });
  const moved = await refusedSend(read.offer.offer_id, { buyer_profile: "cooperative", verdict_id: verdict.id, counter_id: verdict.counters[0].id, state_version: verdict.state_version });
  if (moved.reason !== "BOOKS_CHANGED" || moved.counters.length || !moved.reevaluate) throw new Error("the moved-books story changed: the API has changed");
  files["w2_counter_changed.json"] = { replaced, moved };
}

// ------------------------------------------------------------------ Receivables in three layers: the opening books with the buyer's message open
// The row carries pending_counter (the Option A counter would apply to part of the invoice), and the deal's decision answers the exposure read the
// aside shows: the 30-day late-payment test, the concentration and the payment history. The mock serves these when "tl-mock-receivables-offer" is "1".
await reset();
{
  const read = await live.submitOffer({ fixture_id: "EX01_PACKAGE" });
  await live.evaluateOffer(read.offer.offer_id, "EX01_PACKAGE");
  await recvRead("offer");
  // The home with the counter ready (the offer read, no reply sent): the pending alternative, drawn dashed (ticket #116). The mock serves it while the package offer is evaluated and unanswered.
  files["home_summary_day0_counter.json"] = await live.getHome("en");
  files["home_summary_day0_counter_zh.json"] = await live.getHome("zh");
  if (!files["home_summary_day0_counter.json"].cash.pending?.receipt_rows?.length) throw new Error("the ready counter should reach the home as cash.pending: the API has changed");
  if (!files["receivables/offer.json"].rows.some((r) => r.pending_counter?.decision_id)) throw new Error("the open offer's counter should reach the invoice row as pending_counter: the API has changed");
  for (const [suffix, lang] of NO_EXPOSURE ? [] : [["", "en"], ["_zh", "zh"]]) {
    const exposure = await live.getDecisionExposure(dealId(read.offer.offer_id), lang);
    if (!exposure) throw new Error("GET /decisions/{id}/exposure is off: start the API with FEATURE_EXPOSURE=1");
    files[`receivables/exposure_offer${suffix}.json`] = exposure;
  }
}

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
  // The bank feed's own call (the op id the mock specs read is "rec-receipt-1"); the route the Demo's stepper calls is recorded once, below.
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
async function toDay34(atDay0 = async () => {}, atDay2 = async () => {}) {
  await reset();
  await step("inbox").run();
  await step("trajectory").run();
  await step("negotiate").run();
  await atDay0();
  await live.advanceClock(2);
  await bankReceipt();
  await atDay2();
  await live.advanceClock(28);
  await live.advanceClock(4);
}

// Day 0 after the deal the cure is committed, so "nothing needs you": the quiet opener in both languages.
await toDay34(async () => {
  files["home_opener_quiet.json"] = await live.nlOpener("rec-quiet-en", "en");
  files["home_opener_quiet_zh.json"] = await live.nlOpener("rec-quiet-zh", "zh");
  files["home_summary_quiet.json"] = await live.getHome("en");
  files["home_summary_quiet_zh.json"] = await live.getHome("zh");
  await recvRead("quiet");
  files["trajectory_conservative_quiet.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
}, async () => {
  // Day 2, right after the synthetic bank event (the Demo's scene 4 shows the Receivables page here): the receipt is booked and nothing is late yet.
  files["home_reconciliation_day2.json"] = await live.getReconciliation();
  files["chase_day2.json"] = await chaseAll(files["home_reconciliation_day2.json"]);
  files["home_summary_day2.json"] = await live.getHome("en");
  files["home_summary_day2_zh.json"] = await live.getHome("zh");
  await recvRead("day2");
  files["trajectory_conservative_day2.json"] = await live.getTrajectory("CONSERVATIVE");
  files["home_state_day2.json"] = await live.getState();
  const receipt = (await live.getLedger()).operations.filter((o) => o.kind === "RECEIVE_PAYMENT").at(-1);
  if (!receipt?.event_detail?.includes("Synthetic bank event")) throw new Error("the receipt should say it is a synthetic bank event in the activity words: the API has changed");
  ops.receive_payment = template(receipt);
});
files["home_alerts_day34.json"] = await live.getAlerts();
navCounts.day34 = await live.getNavCounts("en"); // the late invoice, the reserve alert open
files["home_summary_day34.json"] = await live.getHome("en");
files["home_summary_day34_zh.json"] = await live.getHome("zh");
await recvRead("day34");
await buyerExposure("buyer_exposure_day34");
files["trajectory_conservative_day34.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
files["home_state_day34.json"] = await live.getState();
// The books' history at day 34 (the deal, the funding, the day-2 receipt): the mock replays it when the clock is moved to day 34 without the walk.
files["home_ledger_day34.json"] = await live.getLedger();
// The router's comparison for day 34's gap (the Cash page shows a fresh plan while a gap is open, never the day-0 one).
files["funding_day34.json"] = await live.planFunding({});
// The reconciliation after the day-2 bank receipt (it carries the bank's reference).
files["home_reconciliation_day34.json"] = await live.getReconciliation();
// The deal's record on the main walk at day 34: the day-2 receipt came, so it is fulfilled.
await snap("fulfilled_day34.ex01", dealId(demoStore.get().offerId));
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
navCounts.pending = await live.getNavCounts("en"); // the cure waits for the owner's approval
files["home_opener_pending.json"] = await live.nlOpener("rec-home-pending", "en");
files["home_summary_pending.json"] = await live.getHome("en");
files["home_summary_pending_zh.json"] = await live.getHome("zh");
await recvRead("pending");
files["trajectory_conservative_pending.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
files["home_approval_pending.json"] = (await live.getApprovals())[0];
// The same row in Chinese (the queue takes ?lang=zh): the zh mock serves it with the same amounts.
files["home_approval_pending_zh.json"] = (await inLang("zh", () => live.getApprovals()))[0];
await snap("cure_pending", files["home_approval_pending.json"].decision_id);
// The owner approves on the approval card: the same operation executes (EXECUTED, the cash lands on day 37) and the alert clears.
files["home_approval_approved.json"] = await live.decideApproval(files["home_approval_pending.json"].id, "APPROVE");
files["home_approval_approved_zh.json"] = (await inLang("zh", () => live.getApprovals())).find((a) => a.id === files["home_approval_pending.json"].id);
files["home_approve.json"] = { operations: await ledgerTail(1) };
await snap("cure_approved", files["home_approval_pending.json"].decision_id);
// The log after the decision: the earlier "waiting" entry now reads in the past, beside "You approved ..." (the mock replays that).
files["home_ledger_approved.json"] = await live.getLedger();
files["home_alerts_after.json"] = await live.getAlerts();
navCounts.approved = await live.getNavCounts("en");
files["nav_counts.json"] = navCounts;
files["home_state_after_approve.json"] = await live.getState();
files["home_opener_after_approve.json"] = await live.nlOpener("rec-home-after", "en");
files["home_summary_after.json"] = await live.getHome("en");
files["home_summary_after_zh.json"] = await live.getHome("zh");
await recvRead("after");
files["trajectory_conservative_after.json"] = await live.getTrajectory("CONSERVATIVE"); // the Cash page's readings, on the books this home was read on
// Day 38: the advance landed on day 37 and settled the day after. The Demo's "the funding settles" step shows these books.
await live.advanceClock(38 - 34);
// The optional capex scene run after the story reads the books as they stand on day 38: "Computed today", not "38 days ago".
files["capex_day38.json"] = await live.capexEvaluate({ label: "¥600k machine", price_fen: 60000000 });
files["home_alerts_settled.json"] = await live.getAlerts();
files["home_state_settled.json"] = await live.getState();
files["home_summary_settled.json"] = await live.getHome("en");
files["home_summary_settled_zh.json"] = await live.getHome("zh");
await recvRead("settled");
files["trajectory_conservative_settled.json"] = await live.getTrajectory("CONSERVATIVE");
await snap("cure_settled", files["home_approval_pending.json"].decision_id);
if (decisions.cure_settled.en.state !== "SETTLED") throw new Error("the landed cure should read SETTLED: the API has changed");
// The mandate's last day is 90: MANDATE_EXPIRING is a WARNING 14 days before (recorded at day 80) and CRITICAL once it has passed (day 95).
await live.advanceClock(80 - 38);
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

// ------------------------------------------------------------------ contract ingestion (brief 03): the demo documents and the deal summary
// The demo reset opens on the three demo documents read by the agent and confirmed by the owner (DOC-000001..3, the first three
// ledger entries), so the deal summary is ready once a deal is agreed. Recorded: each as the reset leaves it with its ledger row, then read
// again on fresh demo books (a new reading, DOC-000004) and confirmed (a lender agreement linked to its facility) or rejected.
// Confirming writes no books.
files["contracts_fixtures.json"] = await live.getContractFixtures();
const CONTRACT_FIXTURES = files["contracts_fixtures.json"];
const documentsRecorded = {};
await reset();
{
  const seeded = (await live.getDocuments()).documents;
  const ledger = (await live.getLedger()).operations;
  for (const f of CONTRACT_FIXTURES) {
    const row = seeded.find((d) => d.source === `fixture:${f.id}`);
    const op = ledger.find((x) => x.seq === row?.decided_seq);
    if (!row || row.status !== "CONFIRMED" || !op) throw new Error(`the demo reset did not confirm ${f.id}`);
    documentsRecorded[f.id] = { seeded: await live.getDocument(row.id), seeded_operation: { op_id: op.op_id, ...template(op) } };
  }
}
files["deals_day0.json"] = await live.getDeals();
for (const decision of ["confirm", "reject"]) {
  for (const f of CONTRACT_FIXTURES) {
    await reset();
    const again = await live.submitDocument({ fixture_id: f.id });
    if (again.id !== "DOC-000004") throw new Error(`${f.id} read again as ${again.id}, not DOC-000004`);
    documentsRecorded[f.id].reread = again;
    const decided = await live.decideDocument(again.id, decision, again.doc_hash, decision === "confirm" ? f.link_facility_id : null);
    if (decided.result.status !== "EXECUTED") throw new Error(`${f.id} read again was not ${decision}ed: ${decided.result.message}`);
    documentsRecorded[f.id][decision === "confirm" ? "confirmed" : "rejected"] = decided;
    // The deal follows the supply agreement confirmed last: record it once, after the new reading is confirmed.
    if (decision === "confirm" && f.kind === "BUYER_CONTRACT") files["deals_day0_reconfirmed.json"] = await live.getDeals();
  }
}
files["documents.json"] = documentsRecorded;
// The deal on the home path (as above) from the demo's starting point: on day 0 right after the buyer agreed (the Deals page shows
// the summary from then on), then the receipt on day 2 and the clock to day 34; then the cure queued for approval, then approved.
await toDay34(async () => {
  files["deals_day0_agreed.json"] = await live.getDeals();
});
files["deals_day34_open.json"] = await live.getDeals();
{
  const alerts = await live.getAlerts();
  const cure = alerts.alerts.find((a) => a.id.startsWith("ALERT-RESERVE") && a.actionable);
  if (!cure) throw new Error("no actionable reserve alert on day 34 with the contract confirmed: the demo path has changed");
  await live.actOnAlert(cure.id, {
    state_version: alerts.state_version,
    suggestions: cure.suggested.map((x) => ({ operation_kind: x.operation_kind, facility_id: x.facility_id, receivable_id: x.receivable_id, amount_fen: x.amount_fen })),
  });
  files["deals_day34_pending.json"] = await live.getDeals();
  const waiting = (await live.getApprovals()).find((a) => a.status === "PENDING");
  if (!waiting) throw new Error("the day-34 cure did not wait for approval: the demo path has changed");
  await live.decideApproval(waiting.id, "APPROVE");
  files["deals_day34_approved.json"] = await live.getDeals();
}


// The guided Demo's synthetic bank event, as the stepper calls it: POST /demo/bank-receipt on the books where the deal is made and day 2 has come.
await reset();
await step("inbox").run();
await step("trajectory").run();
await step("negotiate").run();
await live.advanceClock(2);
{
  const result = await live.demoBankReceipt();
  if (!result.synthetic || result.result.status !== "EXECUTED") throw new Error("the synthetic bank event did not post: the API has changed");
  files["bank_receipt.json"] = result;
}

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
await recvRead("day34_noreceipt");
files["trajectory_conservative_day34_noreceipt.json"] = await live.getTrajectory("CONSERVATIVE");
if (files["home_summary_day34_noreceipt.json"].cash.below_reserve_today !== true) throw new Error("day 34 without a receipt should be below the reserve today: the API has changed");
await snap("noreceipt_day34.ex01", dealId(demoStore.get().offerId));

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
await recvRead("day34_half");
files["trajectory_conservative_day34_half.json"] = await live.getTrajectory("CONSERVATIVE");
if (!files["home_summary_day34_half.json"].changes.some((c) => c.window_state)) throw new Error("a half receipt should give a change row with the part-paid facts: the API has changed");
// The Receivables page on the same books: the receipt row carries the four facts (F25) and the late invoice has its handoff (F15).
files["home_reconciliation_day34_half.json"] = await live.getReconciliation();
if (!files["home_reconciliation_day34_half.json"].receipts.some((r) => r.window_state === "ended" && r.remaining_display)) throw new Error("the half receipt's row should carry the four facts and the window: the API has changed");
files["chase_day34_half.json"] = await chaseAll(files["home_reconciliation_day34_half.json"]);
await snap("half_day34.ex01", dealId(demoStore.get().offerId));

// 1c. A cure that does not restore the reserve (no receipt on day 2), approved and landed: the cash is back but the reserve is still short, so the
//     home carries the remaining task (F17) and the record is settled with a residual. The mock serves it when "tl-mock-no-receipt" is "residual".
await reset();
await step("inbox").run();
await step("trajectory").run();
await step("negotiate").run();
await live.advanceClock(2);
await live.advanceClock(28);
await live.advanceClock(4);
{
  const alerts = await live.getAlerts();
  const reserve = alerts.alerts.find((a) => a.id.startsWith("ALERT-RESERVE") && a.actionable);
  if (!reserve) throw new Error("no actionable reserve alert on the no-receipt books: the demo path has changed");
  await live.actOnAlert(reserve.id, {
    state_version: alerts.state_version,
    suggestions: reserve.suggested.map((x) => ({ operation_kind: x.operation_kind, facility_id: x.facility_id, receivable_id: x.receivable_id, amount_fen: x.amount_fen })),
  });
  await live.decideApproval((await live.getApprovals())[0].id, "APPROVE");
  await live.advanceClock(4); // the advance lands on day 37 and settles the day after
  files["home_summary_day34_residual.json"] = await live.getHome("en");
  files["home_summary_day34_residual_zh.json"] = await live.getHome("zh");
  await recvRead("day34_residual");
  files["trajectory_conservative_day34_residual.json"] = await live.getTrajectory("CONSERVATIVE");
  if (!files["home_summary_day34_residual.json"].remaining_task) throw new Error("the cure that leaves the reserve short should give a remaining task: the API has changed");
  await snap("cure_residual", files["home_summary_day34_residual.json"].remaining_task_decision_id);
}

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
await snap("cure_failed", cure.decision_id);
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

files["decisions.json"] = Object.fromEntries(Object.keys(decisions).sort().map((k) => [k, decisions[k]]));
for (const name of Object.keys(files).sort()) write(name, files[name]);
console.log(`recorded ${written.length} files into ${OUT} from ${API}`);
