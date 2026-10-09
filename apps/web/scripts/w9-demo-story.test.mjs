// Map #65 debt (tickets #82): the Demo story never approves for the owner, and Next after a Back shows what was finished instead of
// running it again. These run the real steps and the real stepper controls against the mock API in this process.
// Run: pnpm test:unit  (the --import flag in package.json lets node resolve the app's extensionless and "@/" imports)
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

process.env.NEXT_PUBLIC_API_MODE = "mock";
process.env.NEXT_PUBLIC_MOCK_LATENCY_MS = "0";
globalThis.requestAnimationFrame = () => 0;

const { setOwnerToken } = await import("../lib/auth.ts");
const { decideApproval, getApprovals, getLedger, getClock } = await import("../lib/api.ts");
const { DEMO_STEPS, OwnerDecisionPending } = await import("../lib/demo.ts");
const { backStep, goToStep, nextStep } = await import("../lib/demo-control.ts");
const { demoStore, reachedOf, resetSession } = await import("../lib/demo-store.ts");

const stepIndex = (id) => DEMO_STEPS.findIndex((s) => s.id === id);
const opened = [];
const push = (route) => opened.push(route);
const pending = async () => (await getApprovals()).filter((a) => a.status === "PENDING");

async function freshStory() {
  setOwnerToken("test-owner-token");
  resetSession();
  opened.length = 0;
}

test("the approve step never decides for the owner: invoked while the cure waits it approves nothing", async () => {
  await freshStory();
  for (let i = 0; i < stepIndex("approve"); i++) assert.equal(await goToStep(i, push), "done");
  assert.equal((await pending()).length, 1, "the queue row is waiting");
  const approve = DEMO_STEPS[stepIndex("approve")];
  assert.ok(approve.owner);

  await assert.rejects(() => approve.run(), OwnerDecisionPending);
  assert.equal((await pending()).length, 1, "still one PENDING row after the step ran");
  assert.equal((await getApprovals()).filter((a) => a.status === "APPROVED").length, 0);

  // Through the stepper's own entry point: the card is opened, the step is not finished and the pointer stays.
  const before = demoStore.get().step;
  opened.length = 0;
  assert.equal(await goToStep(stepIndex("approve"), push), "done");
  assert.match(opened[0], /^\/approvals#approval-/);
  assert.equal(demoStore.get().step, before);
  assert.equal(demoStore.get().error, null);
  assert.equal((await pending()).length, 1);
  assert.equal(await goToStep(stepIndex("approve") + 1, push), "ignored", "the story does not move on while the owner has not decided");
  assert.equal((await pending()).length, 1);
});

test("once the owner has decided, the approve step reads the decision and changes nothing", async () => {
  const row = (await pending())[0];
  await decideApproval(row.id, "APPROVE");
  const entries = (await getLedger()).chain_length;
  const approve = DEMO_STEPS[stepIndex("approve")];
  const facts = await approve.run();
  assert.ok(facts && typeof facts.result === "string");
  assert.equal((await getLedger()).chain_length, entries);
  assert.equal((await pending()).length, 0);
});

test("Back then Next shows the steps already finished: nothing runs again, the ledger and the clock do not move", async () => {
  await freshStory();
  for (let i = 0; i < 5; i++) assert.equal(await goToStep(i, push), "done");
  assert.equal(demoStore.get().step, 4);
  const entries = (await getLedger()).chain_length;
  const day = (await getClock()).day;

  backStep(push);
  backStep(push);
  assert.equal(demoStore.get().step, 2);
  assert.equal(reachedOf(demoStore.get()), 4, "Back lowers the pointer, not the highest finished step");

  assert.equal(await nextStep(push), "done");
  assert.equal(await nextStep(push), "done");
  assert.equal(demoStore.get().step, 4);
  assert.equal(opened.at(-1), DEMO_STEPS[4].route);
  assert.equal((await getLedger()).chain_length, entries, "the ledger did not grow");
  assert.equal((await getClock()).day, day, "the clock did not move");

  // Beyond the highest finished step Next runs: the clock moves to the late day.
  assert.equal(await nextStep(push), "done");
  assert.equal(demoStore.get().step, 5);
  assert.equal(reachedOf(demoStore.get()), 5);
  assert.ok((await getClock()).day > day);
});

test("Show is allowed up to the highest finished step, and a step beyond it only runs after the one before it", async () => {
  await freshStory();
  for (let i = 0; i < 4; i++) await goToStep(i, push);
  backStep(push);
  backStep(push);
  assert.equal(await goToStep(3, push, { mode: "show" }), "done");
  assert.equal(demoStore.get().step, 1, "Show does not move the pointer");
  assert.equal(await goToStep(4, push, { mode: "show" }), "ignored");
  assert.equal(await goToStep(5, push), "ignored");
});

// ---------------------------------------------------------------- #85: the Home change rows that repeat a part-paid invoice

const { withoutSuperseded } = await import("../lib/home-changes.ts");
const recorded = (name) => JSON.parse(readFileSync(fileURLToPath(new URL(`../mocks/${name}`, import.meta.url)), "utf8"));

test("a row whose superseded_by names another row on the page is dropped; one that names a row not on the page stays", () => {
  const four = { kind: "LATE", seq: 12, day: 34, when: "today", text: "Received ¥127,506.90 ...", remaining_display: "¥291,400.00", receivable_id: "RCV-A" };
  const plain = { kind: "LATE", seq: null, day: 32, when: "2 days ago", text: "¥291,400.00 outstanding ...", receivable_id: "RCV-A", superseded_by: 12 };
  assert.deepEqual(withoutSuperseded([four, plain]), [four]);
  assert.deepEqual(withoutSuperseded([plain]), [plain], "the row it names is not on the page, so it is the only one that says it");
  assert.deepEqual(withoutSuperseded([four, { ...plain, superseded_by: "12" }]), [four], "a string id names the same row");
  const byDecision = { ...plain, superseded_by: "deal:OFFER-1" };
  assert.deepEqual(withoutSuperseded([{ ...four, seq: null, decision_id: "deal:OFFER-1" }, byDecision]).length, 1);
});

test("a row never supersedes itself, and rows with no ids are all kept", () => {
  const own = { kind: "OPERATION", seq: 3, day: 1, when: "today", text: "x", superseded_by: 3 };
  assert.deepEqual(withoutSuperseded([own]), [own]);
  const rows = [{ kind: "RECEIPT", seq: null, day: 1, when: "today", text: "a" }, { kind: "LATE", seq: null, day: 2, when: "today", text: "b" }];
  assert.deepEqual(withoutSuperseded(rows), rows);
});

test("with only the invoice id named, the plain LATE row of a part-paid invoice goes; another invoice's LATE row stays", () => {
  const four = { kind: "LATE", seq: null, day: 34, when: "today", text: "Received", remaining_display: "¥291,400.00", receivable_id: "RCV-A" };
  const plain = { kind: "LATE", seq: null, day: 32, when: "2 days ago", text: "outstanding", receivable_id: "RCV-A" };
  const other = { kind: "LATE", seq: null, day: 32, when: "2 days ago", text: "outstanding", receivable_id: "RCV-B" };
  assert.deepEqual(withoutSuperseded([four, plain, other]), [four, other]);
});

test("the recorded day-34 half-receipt Home holds the part-paid row and, until the API names it, its plain repeat", () => {
  const rows = recorded("home_summary_day34_half.json").changes.filter((c) => c.kind === "LATE");
  assert.ok(rows.some((c) => c.remaining_display), "the four-fact row is there");
  // Rows from an API that carries the ids: the repeat leaves, the four-fact row stays.
  const four = { ...rows.find((c) => c.remaining_display), receivable_id: "RCV-A", seq: 7 };
  const repeat = { ...rows.find((c) => !c.remaining_display), receivable_id: "RCV-A", superseded_by: 7 };
  const left = withoutSuperseded([four, repeat]);
  assert.deepEqual(left, [four]);
});

// ---------------------------------------------------------------- #86: overdue invoices are pinned above the savings ranking

const { orderInvoices, isOverdue } = await import("../lib/receivables-order.ts");

test("overdue invoices come first whatever the savings ranking says; inside each group the server's rank leads", () => {
  const inv = (id, past_due, due_day) => ({ receivable_id: id, past_due, due_day });
  const outstanding = [inv("ON-TIME-1", false, 40), inv("LATE-LOW", true, 30), inv("ON-TIME-2", false, 38), inv("LATE-HIGH", true, 31), inv("UNRANKED", false, 36)];
  // The server ranks by what collecting saves: the on-time invoices are worth more than the late one, and one invoice is not ranked at all.
  const worthRows = [{ receivable_id: "ON-TIME-1" }, { receivable_id: "LATE-HIGH" }, { receivable_id: "ON-TIME-2" }, { receivable_id: "LATE-LOW" }];
  assert.deepEqual(orderInvoices(outstanding, worthRows).map((o) => o.receivable_id), ["LATE-HIGH", "LATE-LOW", "ON-TIME-1", "ON-TIME-2", "UNRANKED"]);
  // Without a ranking the due day orders each group.
  assert.deepEqual(orderInvoices(outstanding, []).map((o) => o.receivable_id), ["LATE-LOW", "LATE-HIGH", "UNRANKED", "ON-TIME-2", "ON-TIME-1"]);
});

test("the server's overdue word on the worth row also pins an invoice; nothing is decided from a date", () => {
  assert.equal(isOverdue({ past_due: false }, { overdue_text: "Overdue" }), true);
  assert.equal(isOverdue({ past_due: false }, { overdue_text: null }), false);
  assert.equal(isOverdue({ past_due: true }), true);
  const outstanding = [{ receivable_id: "A", past_due: false, due_day: 1 }, { receivable_id: "B", past_due: false, due_day: 99 }];
  assert.deepEqual(orderInvoices(outstanding, [{ receivable_id: "A" }, { receivable_id: "B", overdue_text: "Overdue" }]).map((o) => o.receivable_id), ["B", "A"]);
});
