// Slice B (map #121, ticket #143), the web half: the canonical selection, the scope Ask FLOW sends, the queue model and the commitment receipt, as plain functions.
// The components are TSX (node cannot strip JSX), so what is tested is their model. Run: pnpm test:unit
import assert from "node:assert/strict";
import { register } from "node:module";
import test from "node:test";

register("./ts-resolve-hook.mjs", import.meta.url);
const sel = await import("../lib/selection.ts");
const scopeLib = await import("../lib/chat-scope-model.ts");
const queue = await import("../components/deals/flow/queue-model.ts");
const receiptModel = await import("../components/ui/commitment-receipt-model.ts");
const receipt = await import("../lib/receipt.ts");
const href = await import("../lib/customer-href.ts");
const { en, zh } = await import("../lib/dictionary.ts");

test("the six keys are the selection: read in the keys' order, only when set", () => {
  const s = sel.readSelection(new URLSearchParams("from=deal&decision=deal%3AOFF-1&other=x&customer=BUYER-1&invoice=&scenario=late&path=CTR-1"));
  assert.deepEqual(s, { customer: "BUYER-1", decision: "deal:OFF-1", path: "CTR-1", scenario: "late", from: "deal" });
  assert.equal(sel.selectionQuery(s), "customer=BUYER-1&decision=deal%3AOFF-1&path=CTR-1&scenario=late&from=deal");
  assert.equal(sel.selectionHref("/deals", { customer: "A B" }), "/deals?customer=A%20B");
  assert.equal(sel.selectionHref("/deals", {}), "/deals");
});

test("changing one key keeps the others and the path; a null removes it", () => {
  assert.equal(sel.patchedHref("/deals", "customer=B1&tab=waiting", { decision: "deal:O", tab: null }), "/deals?customer=B1&decision=deal%3AO");
  assert.equal(sel.patchedHref("/deals", "decision=deal%3AO", { decision: null }), "/deals");
});

test("an origin is named for the pages that can be one, and a decision names its offer", () => {
  assert.equal(sel.originOf("/deals"), "deal");
  assert.equal(sel.originOf("/receivables"), "invoice");
  assert.equal(sel.originOf("/customers/BUYER-1"), "customer");
  assert.equal(sel.originOf("/activity"), "activity");
  assert.equal(sel.originOf("/"), "home");
  assert.equal(sel.originOf("/documents"), null);
  assert.equal(sel.offerOf("deal:OFF-1"), "OFF-1");
  assert.equal(sel.offerOf("funding:ALERT-1"), null);
  assert.equal(sel.offerOf(null), null);
});

test("a customer link carries the row's own context and the origin: decision, path, invoice, scenario, from, in that order", () => {
  assert.equal(href.customerHref("BUYER-2", { invoice: "RCV-B", from: "invoice" }), "/customers/BUYER-2?invoice=RCV-B&from=invoice");
  assert.equal(href.customerHref("BUYER-1", { decision: "deal:O", path: "CTR-1", invoice: "RCV-A", scenario: "late", from: "deal" }), "/customers/BUYER-1?decision=deal%3AO&path=CTR-1&invoice=RCV-A&scenario=late&from=deal");
  assert.equal(href.customerHref("BUYER-1"), "/customers/BUYER-1");
});

test("the scope is the narrowest the route's own keys name; a key the route does not use is not a scope", () => {
  const p = (q) => new URLSearchParams(q);
  assert.deepEqual(sel.scopeOf("/", p("")), { kind: "company" });
  assert.deepEqual(sel.scopeOf("/deals", p("customer=B1&decision=deal%3AO&scenario=late")), { kind: "decision", customer: "B1", decision: "deal:O", scenario: "late" });
  assert.deepEqual(sel.scopeOf("/customers/B1", p("decision=deal%3AO&from=deal"), "B1"), { kind: "decision", customer: "B1", decision: "deal:O" });
  assert.deepEqual(sel.scopeOf("/customers/B1", p(""), "B1"), { kind: "customer", customer: "B1" });
  assert.deepEqual(sel.scopeOf("/receivables", p("invoice=RCV-A&customer=B1&decision=deal%3AO")), { kind: "invoice", customer: "B1", invoice: "RCV-A" }, "a decision is not Receivables' selection");
  assert.deepEqual(sel.scopeOf("/activity", p("customer=B1&invoice=RCV-A&decision=deal%3AO")), { kind: "company" }, "Activity holds no selection");
});

test("the chip offers the kinds the address holds, narrowest first, Company always; the owner's narrowing is for its route only", () => {
  const params = new URLSearchParams("customer=B1&decision=deal%3AO");
  const { choices } = scopeLib.resolveScope("/deals", params);
  assert.deepEqual(choices.map((c) => c.kind), ["decision", "customer", "company"]);
  assert.deepEqual(scopeLib.scopeChoices({ kind: "company" }).map((c) => c.kind), ["company"]);
  // what the request carries: only the keys that are set, and nothing for the company
  assert.deepEqual(scopeLib.toNlScope(choices[0].scope), { customer: "B1", decision: "deal:O" });
  assert.deepEqual(scopeLib.toNlScope(choices[1].scope), { customer: "B1" });
  assert.equal(scopeLib.toNlScope(choices[2].scope), undefined);
  // today's server reads the scope as two ids, derived from it
  assert.deepEqual(scopeLib.legacyContextOf(choices[0].scope), { offer_id: "O" });
  assert.deepEqual(scopeLib.legacyContextOf(choices[2].scope), {});
  assert.equal(scopeLib.customerOfPath("/customers/BUYER%201/inputs"), "BUYER 1");
  assert.equal(scopeLib.customerOfPath("/deals"), null);
});

const worklist = {
  lang: "en", day: 0, state_version: 1, alert: null, counts: { needs_you: 2, waiting: 1, customers: 2 }, partial: null,
  needs_you: [
    { key: "deal:OFF-1", kind: "DECISION", customer_id: "B1", customer_short: "Foshan", subject_text: "Foshan · Payment terms", status_text: "Counter ready · Reply needed", consequence_text: "As asked: below your minimum.", owner: "NEEDS_YOU", severity: "CAUTION", href: "/?customer=B1&deal=deal%3AOFF-1" },
    { key: "deal:OFF-2", kind: "DECISION", customer_id: "B1", customer_short: "Foshan", subject_text: "Foshan · Early payment", differentiator_text: "invoice RCV-B", status_text: "Counter ready · Reply needed", consequence_text: "x", owner: "NEEDS_YOU", severity: "NORMAL", href: "/?customer=B1&deal=deal%3AOFF-2" },
  ],
  waiting: [{ key: "buyer-reply:OFF-3", kind: "BUYER_REPLY", customer_id: "B2", subject_text: "Dongguan · Terms", status_text: "Buyer reviewing · Buyer's turn", consequence_text: "y", owner: "WAITING", severity: "NORMAL", href: "/?customer=B2" }],
  customers: [{ customer_id: "B1", short: "Foshan", name: "Foshan Home Retail Co.", tone: "warn", status_text: "2 open", detail_text: "d", negotiations_count: 2, needs_you_count: 2, outstanding_display: "¥1", share_text: null, href: "/?customer=B1" }, { customer_id: "B2", short: "Dongguan", name: "Dongguan", tone: "neutral", status_text: "1 open", detail_text: "d", negotiations_count: 1, needs_you_count: 0, outstanding_display: "¥0", share_text: null, href: "/?customer=B2" }],
};
const words = { agreedTerms: (t) => `Supply terms: ${t}`, agreedRef: (r) => `contract ${r}` };

test("the queue has one row per negotiation, never one per customer; the counts are the server's; All is the tasks", () => {
  const deals = { day: 0, deals: [{ counterparty_id: "B1", counterparty_name: "Foshan Home Retail Co.", has_contract: true, contract: { reference: "FHR-1", title: "Supply" }, in_force: [{ key: "payment_terms", label: "Payment terms", value_display: "45 days" }], pills: [{ label: "On track", tone: "ok" }] }] };
  const q = queue.buildQueue(deals, worklist, words);
  assert.equal(q.fallback, true);
  assert.deepEqual(q.needs_you.map((r) => r.key), ["deal:OFF-1", "deal:OFF-2"], "two negotiations with one customer are two rows");
  assert.equal(q.agreements.length, 1);
  assert.equal(q.agreements[0].consequence_text, "Supply terms: Payment terms: 45 days · contract FHR-1");
  assert.deepEqual(queue.tabCounts(q), { all: 4, needs_you: 2, waiting: 1, agreements: 1, customers: 2 });
  // the server's own queue is used as it is
  const own = { ...q, fallback: undefined, counts: { needs_you: 9, waiting: 0, agreements: 0, customers: 3 } };
  assert.equal(queue.buildQueue({ day: 0, deals: [], queue: own }, null, words).counts.needs_you, 9);
  assert.equal(queue.buildQueue(undefined, null, words), null);
});

test("a row selects its negotiation in place, any other task leads where it is done, and every id comes from the row itself", () => {
  const [a, b] = worklist.needs_you;
  assert.equal(queue.rowDecision(a), "deal:OFF-1");
  assert.equal(queue.rowDecision(worklist.waiting[0]), "deal:OFF-3");
  assert.deepEqual(queue.rowTarget(b), { kind: "select", customer: "B1", decision: "deal:OFF-2" });
  const collection = { key: "collection:B1", kind: "COLLECTION", customer_id: "B1", invoice: "RCV-A", subject_text: "s", status_text: "Overdue", consequence_text: "", href: "/?customer=B1" };
  assert.deepEqual(queue.rowTarget(collection), { kind: "go", href: "/receivables?customer=B1&invoice=RCV-A&from=deal" });
  const approval = { key: "approval:A1", kind: "APPROVAL", customer_id: null, subject_text: "s", status_text: "Waiting", consequence_text: "", href: "/approvals#approval-A1" };
  assert.deepEqual(queue.rowTarget(approval), { kind: "go", href: "/approvals#approval-A1" });
  const contract = { key: "agreement:B1", kind: "AGREEMENT", customer_id: "B1", subject_text: "s", status_text: "On track", consequence_text: "", href: "/customers/B1" };
  assert.deepEqual(queue.rowTarget(contract), { kind: "go", href: "/customers/B1" });
});

test("the status pill and the next step are the server's words, split at its own separator unless it sends them apart", () => {
  assert.deepEqual(queue.statusCells({ status_text: "Counter ready · Reply needed", consequence_text: "" }), { state: "Counter ready", next: "Reply needed" });
  assert.deepEqual(queue.statusCells({ status_text: "On track", consequence_text: "" }), { state: "On track", next: null });
  assert.deepEqual(queue.statusCells({ status_text: "a · b", state_text: "A", next_step_text: "Reply today", consequence_text: "" }), { state: "A", next: "Reply today" });
  assert.equal(queue.pillTone("needs_you", { severity: "CRITICAL" }), "bad");
  assert.equal(queue.pillTone("needs_you", { severity: "CAUTION" }), "warn");
  assert.equal(queue.pillTone("waiting", {}), "info");
  assert.equal(queue.pillTone("agreements", {}), "ok");
});

test("the search filters the words the server wrote, and the tab named in the address is the only one that is read", () => {
  const [a] = worklist.needs_you;
  assert.ok(queue.matchesRow(a, "payment", ""));
  assert.ok(queue.matchesRow(a, "  FOSHAN ", ""));
  assert.ok(!queue.matchesRow(a, "dongguan", ""));
  assert.ok(queue.matchesRow(a, "foshan home", "foshan home retail co."));
  assert.equal(queue.tabOf("waiting"), "waiting");
  assert.equal(queue.tabOf("bogus"), null);
  assert.equal(queue.tabOf(null), null);
});

test("the commitment receipt is eleven lines in the ticket's order, and a line the server has no value for is omitted", () => {
  assert.deepEqual(receiptModel.RECEIPT_LINES.map((l) => l.key), ["authorizes", "executes_now", "others_must_agree", "in_hand_vs_future", "gross", "fees", "net", "when", "assumptions", "authority", "remaining"]);
  const full = Object.fromEntries(receiptModel.RECEIPT_LINES.map((l) => [l.field, `v-${l.key}`]));
  assert.deepEqual(receiptModel.receiptLines(full).map((l) => l.key), receiptModel.RECEIPT_LINES.map((l) => l.key));
  const partial = { ...full, gross_display: null, when_text: "  ", remaining_text: undefined };
  assert.deepEqual(receiptModel.receiptLines(partial).map((l) => l.key), ["authorizes", "executes_now", "others_must_agree", "in_hand_vs_future", "fees", "net", "assumptions", "authority"]);
  assert.deepEqual(receiptModel.receiptLines(null), []);
  for (const l of receiptModel.RECEIPT_LINES) assert.ok(en[`receipt.${l.key === "executes_now" ? "executesNow" : l.key === "others_must_agree" ? "othersMustAgree" : l.key === "in_hand_vs_future" ? "inHandVsFuture" : l.key}`], l.key);
});

test("a server's receipt is used as it is; without one the path's own words stand, and the session's three lines only for the very verdict the picture was drawn from", () => {
  const path = { key: "CTR-1", reply_text: "Terms stay at 45 days.", decides_text: "FLOW can send it. Your approval is not needed.", authority_text: "FLOW can send it", cost_once_display: "¥3,027.77", cost_basis_text: "once, nothing ongoing", scenario_assumption_text: "Assumes the buyer accepts." };
  const own = { authorizes_text: "Sends it", net_display: "¥1" };
  assert.equal(receipt.receiptOfPath({ ...path, receipt: own }, null, "V1"), own);
  const fallback = receipt.receiptOfPath(path, null, "V1");
  assert.deepEqual(fallback, { authorizes_text: "Terms stay at 45 days.", executes_now_text: null, fees_display: "¥3,027.77\nonce, nothing ongoing", assumptions_text: "Assumes the buyer accepts.", authority_text: "FLOW can send it. Your approval is not needed." });
  const verdict = { id: "V1", workspace: { priced_response: { counter_id: "CTR-1", send_scope_lines: ["Records the agreement", "Draws ¥149,986.20 today", "Funding cost ¥841.57"] } } };
  const withLines = receipt.receiptOfPath(path, verdict, "V1");
  assert.equal(withLines.authorizes_text, "Records the agreement");
  assert.equal(withLines.executes_now_text, "Draws ¥149,986.20 today\nFunding cost ¥841.57");
  assert.equal(withLines.fees_display, null);
  assert.equal(receipt.receiptOfPath(path, verdict, "V2").authorizes_text, "Terms stay at 45 days.", "another verdict's lines are never shown");
});

test("every word the slice owns exists in both languages", () => {
  for (const key of Object.keys(en).filter((k) => /^(deals|receipt|chat\.scope|customer\.(fig|outstanding|allTasks)|whatif\.scope|appr\.receipt)/.test(k))) assert.ok(zh[key], key);
});
