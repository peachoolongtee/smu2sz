import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { STORY_STEPS, stripOf, walkStory } from "./helpers";

/** Since Wave 3 the Inbox folds to one row once a deal is selected: open it before reading which message is current. */
async function expectSelectedMessage(page: Page, id: string): Promise<void> {
  if (await page.getByTestId("inbox-collapsed").isVisible().catch(() => false)) await page.getByTestId("inbox-back").click();
  await expect(page.getByTestId(`inbox-msg-${id}`)).toHaveAttribute("aria-current", "true");
}


/**
 * Walks the guided Demo, the late-payment loop of docs/DEMO_FLOW.md in six scenes and eleven steps, and asserts the numbers the server formats.
 * The same spec runs in both Playwright projects: `desktop` (mock data, recorded from the API) and `live` (the real FastAPI service). Only the
 * identifiers the server generates differ (approval ids, commitment ids), so those are matched by pattern or read from the session.
 */

const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const STORY_KEY = "tl-demo-v3";

/** The Demo's session as the browser keeps it: the story's offer, the cure it queued and the pointer. */
async function session(page: Page): Promise<{ step: number; storyOfferId: string | null; cure: { approvalId: string; decisionId: string | null; amount: string; landsDay: number | null } | null }> {
  return page.evaluate((key) => JSON.parse(sessionStorage.getItem(key) ?? "{}"), STORY_KEY);
}

/** The ledger's entry count on the ledger page (0 when the books hold no operation). */
async function ledgerEntries(page: Page): Promise<number> {
  await page.goto("/ledger");
  const status = page.getByTestId("chain-status");
  const empty = page.getByText("No operations yet");
  await expect(status.or(empty)).toBeVisible();
  if (await empty.isVisible()) return 0;
  return Number(/(\d+) entries/.exec((await status.textContent()) ?? "")?.[1]);
}

/** How many times the ledger holds an operation of this kind (the Activity page lists one row per entry). */
async function activityRows(page: Page, kind: string): Promise<number> {
  await page.goto("/activity");
  await expect(page.getByTestId("activity-list")).toBeVisible();
  return page.getByTestId(`activity-${kind}`).count();
}

test("the six scenes run with Next: the buyer asks, FLOW decides, the agreement acts, reality diverges, the owner stays in control, the proof", async ({ page }) => {
  test.setTimeout(150_000);
  await page.goto("/demo");
  const narration = page.getByTestId("demo-step-narration");
  await expect(stripOf(page)).toContainText("Walk the story");
  await expect(page.getByTestId("demo-next")).toHaveText(/Start demo/);

  // Scene 1, the buyer asks: the books are reset and the message is read; Deals shows the original request beside the interpreted terms.
  await page.getByTestId("demo-next").click();
  await expect(page).toHaveURL(/\/deals/);
  await expect(stripOf(page)).toContainText(`step 1 of ${STORY_STEPS}`);
  await expect(narration).toContainText("Offer from Foshan Home Retail Co.");
  await expectSelectedMessage(page, "EX01");
  await expect(page.getByTestId("deal-ask-IMMEDIATE_DISCOUNT")).toContainText("1.20% discount for paying the ¥420,000.00 invoice early");
  await expect(page.getByTestId("deal-ask-TERMS_EXTENSION")).toContainText("60");

  // Scene 2, the decision: the forward cost, the cash impact, the recommended counter and its scope.
  await walkStory(page, 1, 1);
  await expect(page.getByTestId("deal-recommendation")).toContainText("Don't accept as asked");
  await expect(page.getByTestId("deal-impact-forward").getByTestId("deal-impact-total")).toHaveText("¥28,326.92");
  await expect(page.getByTestId("path-tile-0")).toContainText("¥209,960.00");
  await expect(narration).toContainText("Sends Option A to the buyer (the reply is simulated)");
  await expect(page.getByTestId("path-col-cost-1")).toHaveText("¥3,027.77");

  // Scene 3, the agreement and its action: the recommended counter is sent bound to what was shown; the live agreement, then cash now.
  await walkStory(page, 1, 2);
  await expect(page).toHaveURL(/\/deals#commitments/);
  await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "AGREED");
  await expect(page.getByTestId("commitments-live")).toBeVisible();
  await expect(narration).toContainText("Agreed.");
  await walkStory(page, 1, 3);
  await expect(page).toHaveURL(/\/cash/);
  await expect(narration).toContainText("Funding of ¥149,986.20 was requested and has landed.");
  await expect(narration).toContainText("Cash in hand is ¥550k.");
  await expect(page.getByTestId("cash-headline")).toBeVisible();

  // Scene 4, reality diverges: the one synthetic bank event, labelled as such, then time passes with nothing received.
  await walkStory(page, 1, 4);
  await expect(page).toHaveURL(/\/receivables/);
  await expect(page.getByTestId("demo-step-title")).toContainText("(synthetic)");
  await expect(narration).toContainText("Synthetic bank event DEMO-RCPT-1: the agreed early payment arrived.");
  await expect(narration).toContainText("The deal now reads: Fulfilled.");
  await expect(page.getByTestId("promised-RCV-A")).toHaveAttribute("data-status", "RECEIVED");
  await walkStory(page, 1, 5);
  await expect(page).toHaveURL(/\/$/);
  await expect(narration).toContainText("32 days passed and the clock recorded no receipt.");
  // Home detects the missed later receipt: the reserve breach and the cure priced above the autonomous ceiling, queued with the owner's click.
  const risk = page.getByTestId("home-next-action");
  await expect(risk).toContainText("¥1,782.19");
  await expect(risk.getByTestId("next-action-needs-owner")).toContainText("15.00%");
  await expect(risk.getByTestId("fix-open-ALERT-RESERVE-42")).toHaveText("Queue it for my approval");

  // Scene 5, the owner stays in control: the cure is queued, not run.
  await walkStory(page, 1, 6);
  await expect(page).toHaveURL(/\/approvals#approval-APR-/);
  await expect(narration).toContainText("Queued, not run: Approve ¥200,000.00 of invoice financing?");
  await expect(page.getByText("1 pending")).toBeVisible();
  // The owner approves ON THE CARD (its one filled Approve); the strip's button only opens the approval, and then moves the story on.
  const card = page.locator('[id^="approval-APR-"]').first();
  await expect(page.getByTestId("demo-next")).toHaveText("Open the approval");
  await expect(page.getByRole("button", { name: /^Approve/ })).toHaveCount(1);
  await card.getByRole("button", { name: /^Approve/ }).click();
  await expect(card.locator('[data-testid^="approval-result-"]')).toContainText("the cash lands in 3 days");
  await expect(page.getByText("0 pending")).toBeVisible();
  await expect(page.getByTestId("demo-next")).toHaveText("Next");
  await page.getByTestId("demo-next").click();
  await expect(stripOf(page)).toContainText(`step 8 of ${STORY_STEPS}`);
  await expect(narration).toContainText("Approved by the owner.");
  // Then the funding settles: landed, not in transit.
  await walkStory(page, 1, 8);
  await expect(page).toHaveURL(/\/cash/);
  await expect(narration).toContainText("the funding has landed");
  await expect(page.getByTestId("home-in-transit")).toHaveCount(0);

  // Scene 6, outcome and proof: Home, then Activity with the evidence export beside it.
  await walkStory(page, 1, 9);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("home-status")).toHaveAttribute("data-status", "WATCH");
  await expect(narration).toContainText("The deal: Fulfilled.");
  await expect(narration).toContainText("The funding: ");
  await walkStory(page, 1, 10);
  await expect(page).toHaveURL(/\/activity/);
  await expect(page.getByTestId("chain-status")).toContainText("Record chain checks passed");
  await expect(narration).toContainText("The record check says: Record chain checks passed.");
  await expect(page.getByTestId("demo-step-link")).toHaveAttribute("href", "/evidence");
  await expect(page.getByTestId("demo-next")).toBeDisabled();

  // The receipt is labelled synthetic where the owner reads the books, and it is the only receipt.
  const receipt = page.getByTestId("activity-RECEIVE_PAYMENT");
  await expect(receipt).toHaveCount(1);
  await expect(receipt).toContainText("Synthetic bank event, reference DEMO-RCPT-1");
  await expect(page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").first()).toBeVisible();

  // Both records end where the story says: the deal fulfilled by the receipt, the cure settled by its landing.
  const s = await session(page);
  expect(s.storyOfferId).toBeTruthy();
  await page.goto(`/decisions/${encodeURIComponent(`deal:${s.storyOfferId}`)}`);
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "FULFILLED");
  await page.goto(`/decisions/${encodeURIComponent(s.cure?.decisionId ?? "")}`);
  await expect(page.getByTestId("record-state")).toHaveAttribute("data-state", "SETTLED");

  // The engine pages keep the story's books: the ledger holds the receipt and the executed advance.
  await page.goto("/ledger");
  await expect(page.getByTestId("chain-status")).toContainText("Chain valid");
  await expect(page.getByText("Get cash early on an invoice").first()).toBeVisible();
  await page.goto("/evidence");
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-evidence").click()]);
  expect(download.suggestedFilename()).toBe("termsledger-evidence.jsonl");
});

test("the approve step needs the owner's click: nothing approves while the story waits, the strip only opens the card, and a second Run is a Show", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/demo");
  await walkStory(page, 7);
  await expect(page).toHaveURL(/\/approvals#approval-APR-/);
  const waiting = page.getByText("1 pending");
  await expect(waiting).toBeVisible();
  // Time passes in the browser and the cure is still waiting: neither the stepper nor the page decides for the owner.
  await page.waitForTimeout(1500);
  await page.goto("/approvals");
  await expect(page.getByText("1 pending")).toBeVisible();
  // One decision, one filled Approve: the card's. The strip says where it is ("Scene 5 of 6, step 7 of 11") and only opens the approval.
  await expect(page.getByTestId("demo-next")).toHaveText("Open the approval");
  await expect(page.getByRole("button", { name: /^Approve/ })).toHaveCount(1);
  await expect(page.getByTestId("demo-step-title")).toContainText("Scene 5 of 6, step 7 of 11");
  await expect(stripOf(page)).toContainText(`step 7 of ${STORY_STEPS}`);
  // The story page shows the step's state, not a second button for the same decision.
  await page.goto("/demo");
  await expect(page.getByTestId("story-waiting-8")).toContainText("Waiting for your approval");
  await expect(page.getByTestId("story-run-8")).toHaveCount(0);
  await expect(page.getByTestId("story-next")).toHaveText("Open the approval");
  await expect(page.getByTestId("story-run-9")).toBeDisabled();
  // The owner's click is the card's.
  await page.goto("/approvals");
  await page.locator('[id^="approval-APR-"]').first().getByRole("button", { name: /^Approve/ }).click();
  await expect(page.getByText("0 pending")).toBeVisible();
  await expect(page.getByTestId("demo-next")).toHaveText("Next");
  await page.getByTestId("demo-next").click();
  await expect(stripOf(page)).toContainText(`step 8 of ${STORY_STEPS}`);
  const entries = await ledgerEntries(page);
  expect(entries).toBeGreaterThan(0);
  const advances = await activityRows(page, "SUBMIT_INVOICE_FOR_FINANCING");
  // A second Run of the finished step approves nothing again (and Replay of it is the same Run): the books are as they were.
  await page.goto("/demo");
  await page.getByTestId("story-replay-8").click();
  await expect(stripOf(page)).toContainText(`step 8 of ${STORY_STEPS}`);
  expect(await ledgerEntries(page)).toBe(entries);
  expect(await activityRows(page, "SUBMIT_INVOICE_FOR_FINANCING")).toBe(advances);
});

test("Back then Next only shows the steps already finished: the ledger, the clock and the receipt do not move", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/demo");
  await walkStory(page, 5); // the buyer asks, FLOW decides, the agreement acts, cash, the synthetic bank event
  const entries = await ledgerEntries(page);
  expect(entries).toBeGreaterThan(0);
  expect(await activityRows(page, "RECEIVE_PAYMENT")).toBe(1);
  await page.goto("/demo");
  await expect(page.getByTestId("home-day")).toHaveText(/^Day \d+$/);
  const day = await page.getByTestId("home-day").textContent();

  const back = page.getByRole("button", { name: "Back" });
  await back.click();
  await expect(stripOf(page)).toContainText(`step 4 of ${STORY_STEPS}`);
  await back.click();
  await expect(stripOf(page)).toContainText(`step 3 of ${STORY_STEPS}`);
  // Next is a Show up to the highest finished step: the pointer moves, the screen opens, nothing runs.
  await page.getByTestId("demo-next").click();
  await expect(stripOf(page)).toContainText(`step 4 of ${STORY_STEPS}`);
  await expect(page).toHaveURL(/\/cash/);
  await page.getByTestId("demo-next").click();
  await expect(stripOf(page)).toContainText(`step 5 of ${STORY_STEPS}`);
  await expect(page).toHaveURL(/\/receivables/);
  expect(await ledgerEntries(page)).toBe(entries);
  expect(await activityRows(page, "RECEIVE_PAYMENT")).toBe(1);
  await page.goto("/demo");
  await expect(page.getByTestId("home-day")).toHaveText(day ?? "");
  // The story page agrees: every step up to the fifth is still done, and the next one runs (Run) rather than shows.
  await expect(page.getByTestId("story-show-5")).toBeVisible();
  await expect(page.getByTestId("story-run-6")).toBeEnabled();
  // Beyond the highest finished step Next runs: the sixth step lets time pass.
  await page.getByTestId("demo-next").click();
  await expect(stripOf(page)).toContainText(`step 6 of ${STORY_STEPS}`);
  await expect(page.getByTestId("demo-step-narration")).toContainText("days passed");
});

test("a step waits for the one before it: scenes and Run buttons ahead are disabled, the next one is not", async ({ page }) => {
  await page.goto("/demo");
  const jumps = page.getByRole("list", { name: "Demo scenes" }).getByRole("button");
  expect(await jumps.count()).toBe(6);
  await expect(jumps.nth(0)).toBeEnabled(); // the first scene starts the story, like Start demo
  for (let i = 1; i < 6; i++) await expect(jumps.nth(i)).toBeDisabled();
  await expect(page.getByTestId("story-run-1")).toBeEnabled();
  await expect(page.getByTestId("story-run-2")).toBeDisabled();
  await walkStory(page, 2);
  await expect(jumps.nth(0)).toBeEnabled();
  await expect(jumps.nth(1)).toBeEnabled();
  await expect(jumps.nth(2)).toBeEnabled(); // the next scene starts with Next
  await expect(jumps.nth(3)).toBeDisabled();
  await page.goto("/demo");
  await expect(page.getByTestId("story-run-3")).toBeEnabled();
  await expect(page.getByTestId("story-run-4")).toBeDisabled();
});

test("the optional scenes run from More to show and never move the story's pointer", async ({ page }) => {
  test.setTimeout(150_000);
  await page.goto("/demo");
  await walkStory(page, STORY_STEPS);
  await page.goto("/demo");
  await expect(page.getByTestId("more-reworded")).toContainText("Open \"The buyer walks away\" first.");
  await expect(page.getByTestId("more-run-reworded")).toBeDisabled();

  // The capex question: evaluated on the books the story left, applying stays the owner's click on the Capex page.
  await page.getByTestId("more-run-capex").click();
  await expect(page).toHaveURL(/\/capex/);
  await expect(page.getByTestId("capex-as-of")).toContainText("Computed today");
  await expect(stripOf(page)).toContainText(`step ${STORY_STEPS} of ${STORY_STEPS}`);
  await expect(page.getByTestId("capex-apply")).toBeEnabled();

  // The attack message is read on its own offer; the story's message is the current one again when the story is shown.
  await page.goto("/demo");
  await page.getByTestId("more-run-security").click();
  await expect(page).toHaveURL(/\/security/);
  await expect(page.locator('[data-testid^="event-"]').first()).toBeVisible();
  await expect(page.locator('[data-testid^="event-"]').filter({ hasText: "UNKNOWN_COUNTERPARTY" }).first()).toBeVisible();
  await expect(stripOf(page)).toContainText(`step ${STORY_STEPS} of ${STORY_STEPS}`);
  await page.goto("/demo");
  await page.getByTestId("story-show-2").click();
  await expect(page).toHaveURL(/\/deals/);
  await expectSelectedMessage(page, "EX01");
  await expect(stripOf(page)).toContainText(`step ${STORY_STEPS} of ${STORY_STEPS}`);

  // The engine's own pages open as they are.
  await page.goto("/demo");
  await page.getByRole("link", { name: "Debt Desk" }).click();
  await expect(page).toHaveURL(/\/funding/);

  // The buyer who walks away replaces the books, so it is the one scene after which the story starts over, and it says so beforehand.
  await page.goto("/demo");
  await expect(page.getByTestId("more-walk")).toContainText("Replaces the books: the story starts over afterwards.");
  await page.getByTestId("more-run-walk").click();
  await expect(page).toHaveURL(/\/verdict/);
  await expect(page.getByTestId("negotiation-result")).toContainText("NO DEAL");
  await expect(stripOf(page)).toContainText("Walk the story");
  await page.goto("/demo");
  await page.getByTestId("more-run-reworded").click();
  await expect(page).toHaveURL(/\/verdict/);
  await expect(page.getByTestId("outcome-badge")).toContainText("REJECT");
  await expect(page.getByTestId("violation-AGG_CONCESSION_EXCEEDED")).toContainText("¥28,326.92");
});

test("the capex application stays the owner's click and its approval is logged", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("more-run-capex").click();
  await expect(page).toHaveURL(/\/capex/);
  await expect(page.getByText("¥380,885.77").first()).toBeVisible();
  await page.goto("/approvals");
  await expect(page.getByText("0 pending")).toBeVisible();
  await page.goto("/capex");
  await page.getByTestId("capex-apply").click();
  await expect(page.getByTestId("capex-applied")).toBeVisible();
  await page.goto("/approvals");
  await page.getByRole("button", { name: /^Approve/ }).first().click();
  await expect(page.getByText("Approved").first()).toBeVisible();
  await page.goto("/ledger");
  await expect(page.getByTestId("chain-status")).toContainText("Chain valid");
});

test("the label toggle switches the UI to Chinese and back", async ({ page }) => {
  await page.goto("/mandate");
  await page.getByLabel("中文").check();
  await expect(page.getByRole("heading", { name: "授权书", level: 1 })).toBeVisible();
  await page.getByLabel("English").check();
  await expect(page.getByRole("heading", { name: "Mandate", level: 1 })).toBeVisible();
});

test("reset clears the session back to the demo's starting point", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("demo-next").click();
  await expect(page).toHaveURL(/\/deals/);
  await page.getByTestId("demo-next").click();
  await expect(stripOf(page)).toContainText(`step 2 of ${STORY_STEPS}`);
  await page.getByTestId("demo-reset").click();
  await expect(page).toHaveURL(/\/demo/);
  await expect(stripOf(page)).toContainText("Walk the story");
  await page.goto("/ledger");
  // The demo opens on the three demo documents read by the agent and confirmed by the owner; nothing else is logged.
  const ops = page.locator("#operations tbody tr");
  await expect(ops).toHaveCount(3);
  await expect(ops.filter({ hasText: "Confirm document" })).toHaveCount(3);
  await expect(page.getByTestId("chain-status")).toContainText("3 entries");
});

// ---------------------------------------------------------------- Show, Replay, Reset and the in-flight lock (Wave 6, ticket #75)

const strip = stripOf;

/** The strip's "step n of 11" as a number, or null while it shows the idle text. */
async function progressOf(page: Page): Promise<number | null> {
  const m = new RegExp(`step (\\d+) of ${STORY_STEPS}`).exec((await strip(page).textContent()) ?? "");
  return m ? Number(m[1]) : null;
}

test("rapid clicks on Start and Next end at the last step, in order, with the books of one walk", async ({ page }, testInfo) => {
  test.setTimeout(240_000);
  await page.goto("/demo");
  const next = page.getByTestId("demo-next");
  await expect(next).toHaveText(/Start demo/);

  // Raw clicks every 50 ms with no waiting: a disabled button swallows a click as it does for a hand. The eighth step is the owner's approval:
  // the strip's button only opens the card, so the story waits at step 7 until the owner presses the card's Approve, and then the clicks go on.
  const seen: (number | null)[] = [];
  const started = Date.now();
  let clicks = 0;
  while (Date.now() - started < 150_000) {
    await next.evaluate((el) => (el as HTMLButtonElement).click());
    clicks++;
    await page.waitForTimeout(50);
    const n = await progressOf(page);
    seen.push(n);
    if (n === 7 && (await next.textContent())?.includes("Open the approval") && page.url().includes("/approvals")) {
      await page.getByRole("button", { name: /^Approve/ }).click();
      await expect(page.getByText("0 pending")).toBeVisible();
    }
    if (n === STORY_STEPS && clicks >= 30) break; // at least thirty presses, the last ones past the end of the story
  }
  const rapidMs = Date.now() - started;

  // Never the idle text once started, never a step back, and the last step is reached.
  const firstStep = seen.findIndex((n) => n !== null);
  expect(firstStep).toBeGreaterThanOrEqual(0);
  const afterStart = seen.slice(firstStep);
  expect(afterStart.every((n) => n !== null)).toBe(true);
  for (let i = 1; i < afterStart.length; i++) expect(afterStart[i]!, `progress went back at sample ${i}: ${afterStart.join(",")}`).toBeGreaterThanOrEqual(afterStart[i - 1]!);
  expect(afterStart.at(-1)).toBe(STORY_STEPS);
  await expect(next).toBeDisabled();

  // The books of one walk: the same ledger as a guarded walk (no scene ran twice, no second negotiation, one receipt).
  const rapidEntries = await ledgerEntries(page);
  await page.goto("/demo");
  await page.getByTestId("story-reset").click();
  await expect(strip(page)).toContainText("Walk the story");
  const guardedStarted = Date.now();
  await walkStory(page, STORY_STEPS);
  const guardedMs = Date.now() - guardedStarted;
  const guardedEntries = await ledgerEntries(page);
  expect(rapidEntries).toBeGreaterThan(0);
  expect(rapidEntries).toBe(guardedEntries);
  expect(await activityRows(page, "RECEIVE_PAYMENT")).toBe(1);

  const timing = { project: testInfo.project.name, steps: STORY_STEPS, rapid: { clicks, ms: rapidMs, ledgerEntries: rapidEntries, progress: afterStart.filter((n, i) => i === 0 || n !== afterStart[i - 1]) }, guarded: { ms: guardedMs, ledgerEntries: guardedEntries } };
  console.log(`DEMO_TIMING ${JSON.stringify(timing)}`);
  await testInfo.attach("demo-timing", { body: JSON.stringify(timing, null, 1), contentType: "application/json" });
});

test("Show opens a finished step and changes nothing; Replay runs it again and is safe on a story that moves time; Reset resets", async ({ page }) => {
  test.setTimeout(150_000);
  await page.goto("/demo");
  await walkStory(page, 3); // the buyer asks, FLOW decides, the agreement acts

  // Move the clock to day 7 from the story page.
  await page.goto("/demo");
  await page.getByTestId("home-plus-7").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 7");
  const entries = await ledgerEntries(page);
  expect(entries).toBeGreaterThan(0);

  // Finished steps offer Show and Replay; the next one offers Run, and the ones after it wait.
  await page.goto("/demo");
  await expect(page.getByTestId("story-show-1")).toBeVisible();
  await expect(page.getByTestId("story-replay-1")).toHaveAttribute("aria-label", /erases the books/);
  await expect(page.getByTestId("story-replay-3")).toHaveAttribute("aria-label", /runs this step again and changes the books/);
  await expect(page.getByTestId("story-show-4")).toHaveCount(0);
  await expect(page.getByTestId("story-run-4")).toBeEnabled();

  // Show on the first step and on a later one: the screen opens, the day and the ledger stay.
  await page.getByTestId("story-show-1").click();
  await expect(page).toHaveURL(/\/deals/);
  await page.goto("/demo");
  await page.getByTestId("story-show-3").click();
  await expect(page).toHaveURL(/\/deals#commitments/);
  await page.goto("/demo");
  await expect(page.getByTestId("home-day")).toHaveText("Day 7");
  await expect(strip(page)).toContainText(`step 3 of ${STORY_STEPS}`);
  expect(await ledgerEntries(page)).toBe(entries);

  // Replay of the agreement runs it again: the deal was agreed once and is not agreed twice.
  await page.goto("/demo");
  await page.getByTestId("story-replay-3").click();
  await expect(strip(page)).toContainText(`step 3 of ${STORY_STEPS}`);
  expect(await ledgerEntries(page)).toBe(entries);

  // Replay of the first step is the deliberate reset: day 0, the story at step 1, and nothing logged but the owner's confirmation of
  // the three demo documents the demo opens on (brief 03).
  await page.goto("/demo");
  await page.getByTestId("story-replay-1").click();
  await expect(page).toHaveURL(/\/deals/);
  await expect(strip(page)).toContainText(`step 1 of ${STORY_STEPS}`);
  await page.goto("/demo");
  await expect(page.getByTestId("home-day")).toHaveText("Day 0");
  expect(await ledgerEntries(page)).toBe(3);

  // Reset starts the story over.
  await page.goto("/demo");
  await page.getByTestId("story-next").click();
  await expect(strip(page)).toContainText(`step 2 of ${STORY_STEPS}`);
  await page.goto("/demo");
  await page.getByTestId("story-reset").click();
  await expect(strip(page)).toContainText("Walk the story");
  await expect(page.getByTestId("story-show-1")).toHaveCount(0);
  await expect(page.getByTestId("story-run-1")).toBeVisible();
});

test("while a step runs every control that conflicts with it is disabled", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "live", "The mock answers in milliseconds; the live API is held back to make the window long enough to see.");
  await page.route(`${API}/demo/reset`, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    await route.continue();
  });
  await page.goto("/demo");
  await page.getByTestId("story-next").click();
  // The first step is running: nothing else can start.
  for (const id of ["demo-next", "story-next", "demo-reset", "story-reset", "story-run-2", "home-advance", "home-plus-1", "more-run-capex", "more-run-walk"]) await expect(page.getByTestId(id), id).toBeDisabled();
  const jumps = page.getByRole("list", { name: "Demo scenes" }).getByRole("button");
  expect(await jumps.count()).toBe(6);
  for (let i = 0; i < 6; i++) await expect(jumps.nth(i)).toBeDisabled();
  await expect(page.getByRole("button", { name: "Back" })).toBeDisabled();
  await expect(strip(page)).toContainText(`step 1 of ${STORY_STEPS}`);
  await expect(page.getByTestId("demo-next")).toBeEnabled();
});

test("a reload in the middle of a step is said, not silently unlocked", async ({ page }) => {
  await page.goto("/demo");
  await walkStory(page, 2);
  // What the browser holds when the tab is closed while step 3 runs: running is saved, busy never is.
  await page.evaluate((key) => {
    const s = JSON.parse(sessionStorage.getItem(key) ?? "{}");
    sessionStorage.setItem(key, JSON.stringify({ ...s, busy: false, running: 2 }));
  }, STORY_KEY);
  await page.reload();
  await expect(page.getByTestId("demo-interrupted")).toContainText("Step 3 was interrupted by a reload");
  await expect(page.getByTestId("demo-next")).toBeEnabled();
  await expect(strip(page)).toContainText(`step 2 of ${STORY_STEPS}`);
  // Running the next step clears the notice.
  await page.getByTestId("demo-next").click();
  await expect(strip(page)).toContainText(`step 3 of ${STORY_STEPS}`);
  await expect(page.getByTestId("demo-interrupted")).toHaveCount(0);
});

test("the narration is the server's: a step that was told nothing shows its plain sentence, and a language change drops the old sentences", async ({ page }) => {
  await page.goto("/demo");
  await walkStory(page, 2);
  const narration = page.getByTestId("demo-step-narration");
  await expect(narration).toContainText("¥28,326.92");
  // The plain sentences carry no figure: the dictionary never holds one.
  await page.getByLabel("中文").check();
  await expect(narration).not.toContainText("¥28,326.92");
  await expect(narration).toHaveText(/FLOW|检查|报价/);
  // The sentences were written in English: in English they are told again, nothing was lost.
  await page.getByLabel("English").check();
  await expect(narration).toContainText("¥28,326.92");
});

test("an engine view with Business stored shows the Demo shell and the Demo radio, with a way back", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.goto("/demo");
  await expect(page.getByTestId("demo-strip")).toBeVisible();
  await expect(page.getByLabel("Demo", { exact: true })).toBeChecked();
  await expect(page.getByTestId("tab-bar")).toHaveCount(0);

  await page.getByTestId("back-to-business").click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("tab-bar")).toHaveCount(1);
  await expect(page.getByTestId("demo-strip")).toHaveCount(0);
  await expect(page.getByLabel("Business", { exact: true })).toBeChecked();

  // Choosing Business on an engine view goes Home.
  await page.goto("/mandate");
  await expect(page.getByLabel("Demo", { exact: true })).toBeChecked();
  await page.getByLabel("Business", { exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("tab-bar")).toHaveCount(1);
});

test("what-if and equipment open from Cash inside the Business shell, with a way back to Cash", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "business" })));
  await page.goto("/cash");
  await page.getByRole("link", { name: "Try different terms" }).click();
  await expect(page).toHaveURL(/\/whatif/);
  await expect(page.getByTestId("tab-bar")).toHaveCount(1);
  await expect(page.getByTestId("demo-strip")).toHaveCount(0);
  await expect(page.getByTestId("back-to-business")).toHaveCount(0);
  await page.getByTestId("back-to-cash").click();
  await expect(page).toHaveURL(/\/cash/);

  await page.goto("/capex");
  await expect(page.getByTestId("tab-bar")).toHaveCount(1);
  await expect(page.getByTestId("demo-strip")).toHaveCount(0);
  await expect(page.getByTestId("back-to-cash")).toBeVisible();
});

test("the Demo sidebar's footer is on screen at 768 px of height", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "phone", "the sidebar is the desktop's");
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/demo");
  const footer = page.locator("aside").getByText("Synthetic fixture data. No real funds move.");
  await expect(footer).toBeVisible();
  // The column scrolls when its links need more than the window: the footer can be brought into view, and it ends inside the window.
  await footer.scrollIntoViewIfNeeded();
  const box = (await footer.boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(768);
});
