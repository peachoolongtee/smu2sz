import { expect, proseOf, test } from "./fixtures";
import { runPlan } from "./helpers";

/**
 * The Business Activity page in mock mode: every row leads with a business sentence (what happened, in the owner's words:
 * names, not ids, and distances from today), with the plain operation name as a muted label; the executor's own sentence, the
 * operation id, the codes and the hashes are audit details, closed.
 * The recorded demo path: day 34, the owner queues the fix for approval, then approves it.
 */

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path");
});

const RAW = '[data-testid="activity-raw"]';

test("each row leads with the business sentence, the operation name is a muted label, and the executor's sentence is an audit detail", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toBeVisible();

  await page.goto("/activity");
  const rows = page.getByTestId("activity-list").locator("li");
  await expect(rows.first()).toBeVisible();
  const row = page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").first();
  // The sentence is the row's heading line; the operation's plain name sits beside the day as a label.
  const sentence = row.getByTestId("activity-event");
  await expect(sentence).toHaveText("Waiting for your approval: ¥200,000.00 of invoice financing at 32.5% a year, above the 15.00% limit you signed for funding without your approval.");
  await expect(sentence).not.toContainText("Queued for owner approval");
  await expect(sentence).not.toContainText("what the agent may borrow alone");
  await expect(sentence).not.toContainText("RI:");
  await expect(row.getByTestId("activity-op")).toHaveText("Get cash early on an invoice");
  await expect(row).toContainText("today");
  // The raw executor sentence, the operation id, the tier and the hashes stay under Audit details, closed until opened.
  const audit = row.locator("details");
  await expect(audit).not.toHaveAttribute("open", "");
  await audit.locator("summary").click();
  await expect(audit.getByTestId("activity-raw")).toContainText("Queued for owner approval (APR-000001)");
  await expect(audit).toContainText("Tier 2");
  await expect(page.locator("body")).not.toContainText(/\bDay \d/);
  // The executor's own sentence is the audit level and keeps the engine's day numbers; the rest of the page does not.
  expect(await proseOf(page, [RAW])).not.toMatch(/\bday \d/i);
});

test("approving the fix reads \"You approved ...\" on Activity, never the executor's advance sentence", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await page.locator("#approval-APR-000001").getByRole("button", { name: "Approve" }).click();
  await expect(page.locator("#approval-APR-000001")).toContainText("Approved");

  await page.goto("/activity");
  const approved = page.getByTestId("activity-event").filter({ hasText: "You approved" });
  await expect(approved).toHaveText("You approved ¥200,000.00 of invoice financing. Funds arrive in 3 days.");
  // One operation, one story (the API words the entry that waited in the past, "Approval requested", once it is decided): the entry that waited reads in the past beside the decision, never "Waiting" beside "You approved".
  const events = await page.getByTestId("activity-event").allTextContents();
  expect(events.filter((x) => x.includes("¥200,000.00 of invoice financing")).map((x) => x.split(":")[0].split(".")[0])).toEqual(["You approved ¥200,000", "Approval requested"]);
  expect(events.some((x) => x.startsWith("Waiting for your approval"))).toBe(false);
  // No row leads with the executor's sentence.
  for (const text of await page.getByTestId("activity-event").allTextContents()) {
    expect(text).not.toMatch(/^Advance ¥/);
    expect(text).not.toMatch(/^Queued for owner approval/);
    expect(text).not.toContain("RI:");
  }
  expect(await proseOf(page, [RAW])).not.toMatch(/\bday \d/i);
});

test("day 34: Activity lists the agreement Receivables lists, not 'No commitments yet'", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/receivables");
  await expect(page.getByTestId("promised-RCV-A")).toBeVisible();
  await page.goto("/activity");
  const agreements = page.locator("#activity-commitments");
  await expect(agreements).toContainText("Foshan Home Retail Co.");
  await expect(agreements).not.toContainText("No commitments yet");
  await expect(page.getByTestId("activity-ACCEPT_OFFER")).toBeVisible();
  // The badge says what the check does (the log's own hash chain) and nothing wider; the scope sits in its tooltip and in a fold.
  const chain = page.getByTestId("chain-status");
  await expect(chain).toContainText("Record chain checks passed");
  await expect(chain).not.toContainText("Records verified");
  await expect(chain.locator("[title]")).toHaveAttribute("title", /does not confirm bank facts or buyer promises/);
  const scope = page.getByTestId("activity-chain-scope");
  await expect(scope).not.toHaveAttribute("open", "");
  await scope.locator("> summary").click();
  await expect(scope).toContainText("This checks the log's own integrity; it does not confirm bank facts or buyer promises.");
});

test("an empty log has no chain badge", async ({ page }) => {
  await page.goto("/activity");
  await expect(page.getByTestId("activity-empty")).toBeVisible();
  await expect(page.getByTestId("chain-status")).toHaveCount(0);
  await expect(page.getByTestId("activity-chain-scope")).toHaveCount(0);
});

test("each event says what changed, why it matters (labelled Now when it is today's forecast) and what remains; the request reads as history with the decision's state and a link", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/");
  await runPlan(page, "ALERT-RESERVE-42");
  await expect(page.getByTestId("alert-waiting-ALERT-RESERVE-42")).toBeVisible();

  // While it waits: the request carries its label, the quote as the reason (not "Now": it is the entry's own quote) and what is still open.
  await page.goto("/activity");
  const waiting = page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").first();
  await expect(waiting.getByTestId("activity-event")).toContainText("Waiting for your approval");
  await expect(waiting.getByTestId("activity-why")).toContainText("Why it matters");
  await expect(waiting.getByTestId("activity-why")).toContainText("Quoted cost ¥1,782.19");
  await expect(waiting.getByTestId("activity-why")).not.toContainText("Now");
  await expect(waiting.getByTestId("activity-remains")).toContainText("What is left");
  await expect(waiting.getByTestId("activity-approval")).toContainText("Approval requested");

  // Approved: the history keeps "Approval requested" but says where the decision stands today and links to it; the decision row reads in the present.
  await page.goto("/");
  await page.getByTestId("alert-approval-link-ALERT-RESERVE-42").click();
  await page.locator("#approval-APR-000001").getByRole("button", { name: "Approve" }).click();
  await expect(page.locator("#approval-APR-000001")).toContainText("Approved");
  await page.goto("/activity");
  const requested = page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").filter({ hasText: "Approval requested:" });
  await expect(requested.getByTestId("activity-approval")).toContainText("Approval requested");
  await expect(requested.getByTestId("activity-approval-state")).toHaveText("Now: Requested; the cash is on its way");
  await expect(requested.getByTestId("activity-record")).toHaveAttribute("href", /^\/decisions\/alert:ALERT-RESERVE-42/);
  const approved = page.getByTestId("activity-SUBMIT_INVOICE_FOR_FINANCING").filter({ hasText: "You approved" });
  // Today's forecast is one sentence, labelled Now, said once above the timeline; the row does not repeat it.
  await expect(page.getByTestId("activity-now")).toContainText("Now");
  await expect(page.getByTestId("activity-now")).toHaveCount(1);
  await expect(approved.getByTestId("activity-why")).toHaveCount(0);
  await expect(approved.getByTestId("activity-remains")).toContainText("Waiting for Invoice financing");
  // What changed, then what is left.
  const order = await approved.evaluate((el) => ["activity-event", "activity-remains"].map((id) => el.querySelector(`[data-testid="${id}"]`)?.getBoundingClientRect().top ?? -1));
  expect(order[0]).toBeLessThan(order[1]);
  // The request is history once the owner has decided: it wears where the decision stands now, never "Waiting for your approval", and the decision is "You".
  await expect(requested.getByTestId("activity-request-state")).toContainText("Requested; the cash is on its way");
  await expect(requested.getByText("Waiting for your approval")).toHaveCount(0);
  await expect(approved.getByTestId("activity-actor")).toHaveText("You");
  // The decision row never reads "Waiting" beside its own approval.
  await expect(page.getByTestId("activity-approval-state")).not.toContainText("Waiting for your approval");
});

test("the set-aside line on Deals lands on the real refused section of Activity", async ({ page }) => {
  await page.goto("/deals");
  const line = page.getByTestId("inbox-blocked");
  await expect(line).toBeVisible();
  const link = line.getByRole("link", { name: "See what was refused" });
  await expect(link).toHaveAttribute("href", "/activity#activity-refused");
  await link.click();
  await expect(page).toHaveURL(/\/activity#activity-refused$/);
  await expect(page.locator("#activity-refused")).toBeInViewport();
});

test("day 34, Business: the clock move reads in owner words and no row shows an engine term or a record id", async ({ page }) => {
  await page.goto("/demo");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
  await page.goto("/activity");
  const clock = page.getByTestId("activity-ADVANCE_CLOCK").first();
  await expect(clock).toBeVisible();
  await expect(clock.getByTestId("activity-event")).toContainText(/\d+ days? passed/);
  await expect(clock.getByTestId("activity-op")).toHaveText("Time passed");
  const prose = await proseOf(page, [RAW, "summary", "[data-testid=activity-commitment-id]"]);
  expect(prose).not.toMatch(/\bday \d/i);
  expect(prose).not.toContain("ADVANCE_CLOCK");
  expect(prose).not.toMatch(/flow\(s\)|commitment\(s\)|give-aways|Clock moved/);
  // The agreement says what it booked in the budget's words, and its ids sit under Audit details, closed.
  const agreements = page.locator("#activity-commitments");
  await expect(agreements).toContainText("Concessions booked against your budget");
  await expect(agreements.locator("details").first()).not.toHaveAttribute("open", "");
  await expect(page.getByTestId("activity-ACCEPT_OFFER").getByTestId("activity-event")).toContainText("concessions booked against your budget");
  expect(await page.locator("body").innerText()).not.toContain("CMT-");
});
