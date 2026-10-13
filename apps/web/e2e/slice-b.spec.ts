import type { Page } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { checkedDeal, openInbox, openReview, resetBooks } from "./helpers";

/**
 * Slice B of the overhaul map #121 (tickets #126 to #132, #134, #143), the contract end to end: a row's link and the origin, a deep link that hydrates a fresh session,
 * a selection that names nothing asks, the receipt before the commit at a phone's width, Ask FLOW's scope chip, What-if asking which negotiation, and, on the live
 * project, the busy company's queue with one row per negotiation and the request Ask FLOW sends. The mock project runs on the API's recordings; the live project on a
 * real API (E2E_TARGET=live) and a reset of its books.
 */

const OFFER = "OFF-f806f79b6c21";
const DECISION = `deal:${OFFER}`;
const live = (info: { project: { name: string } }) => info.project.name === "live";

async function scope(page: Page) {
  return page.getByTestId("chat-scope");
}

test.describe("mock", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("a row's link is its own customer, decision and invoice plus the origin; the selected row's context is never copied onto it", async ({ page }) => {
    await checkedDeal(page);
    const decision = encodeURIComponent(DECISION);
    await expect(page.getByTestId("queue-customer").first()).toHaveAttribute("href", `/customers/BUYER-1?decision=${decision}&from=deal`);
    await page.goto("/receivables?invoice=RCV-A&decision=" + decision);
    await expect(page.getByTestId("recv-RCV-A").getByRole("link", { name: "Foshan Home Retail Co." })).toHaveAttribute("href", "/customers/BUYER-1?invoice=RCV-A&from=invoice");
    // Activity holds no selection: its customer names carry the origin and nothing else.
    await page.goto("/activity?invoice=RCV-A&decision=" + decision);
    const names = page.locator("main a[href^='/customers/']");
    if (await names.count()) for (const href of await names.evaluateAll((els) => els.map((el) => el.getAttribute("href")!))) expect(href).toMatch(/^\/customers\/[^?]+\?from=activity$/);
  });

  test("a deep link in a fresh session hydrates the negotiation, its reply and its open investigation from the server", async ({ page }) => {
    await checkedDeal(page);
    await page.evaluate(() => sessionStorage.removeItem("tl-demo-v3")); // the tab's own session cache is gone: only the server is read
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}&path=CTR-6b07cbf70441&compare=1`);
    await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
    await expect(page.getByTestId("deal-recommends-title")).toHaveText("The response you picked · Option B");
    await expect(page.getByTestId("deal-compare-table")).toBeVisible();
    await expect(page.getByTestId("queue-check-button")).toHaveCount(0); // an evaluated deal is read, not checked again
  });

  test("a selection that names nothing asks which negotiation, on Deals and on What-if, and never shows a sample", async ({ page }) => {
    await page.goto("/deals?decision=deal%3AOFF-nope");
    await expect(page.getByTestId("deal-ask-which")).toContainText("Which negotiation?");
    await page.goto("/whatif?decision=deal%3AOFF-nope&customer=BUYER-1");
    await expect(page.getByTestId("whatif-ask")).toContainText("Which negotiation?");
    await expect(page.getByTestId("whatif-outcome")).toHaveCount(0);
    await page.goto("/whatif");
    await expect(page.getByTestId("whatif-ask")).toBeVisible();
    await expect(page.getByTestId("whatif-none")).toBeVisible(); // nothing is open on the opening books: the page says so and leads to Deals
    await expect(page.getByTestId("whatif-outcome")).toHaveCount(0);
  });

  test("What-if opens on the named negotiation's own terms and says which negotiation it is for", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-whatif").click();
    await expect(page).toHaveURL(/\/whatif\?customer=BUYER-1&decision=/);
    await expect(page.getByTestId("whatif-scope")).toContainText("Testing terms for");
    await expect(page.getByTestId("whatif-terms-readout")).toHaveText("60 days"); // the buyer's offer: 60 days, 1.20%, 1.00%
    await expect(page.getByTestId("whatif-discount-readout")).toHaveText("1.20%");
    await expect(page.getByTestId("whatif-outcome")).toHaveAttribute("data-outcome", "REJECT");
    await page.getByTestId("whatif-scope-back").click();
    await expect(page).toHaveURL(/\/deals\?decision=/);
    // Listing the open negotiations is the page's own choice when none is named.
    await page.goto("/whatif");
    await expect(page.getByTestId("whatif-choice")).toHaveCount(1);
    await page.getByTestId("whatif-choice").click();
    await expect(page.getByTestId("whatif-scope")).toBeVisible();
  });

  test("at 390 px the receipt's terms come before the one commit button, in the DOM and on screen", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await checkedDeal(page);
    await openReview(page);
    const lines = page.locator('[data-testid^="receipt-line-"]');
    expect(await lines.count()).toBeGreaterThanOrEqual(4);
    const order = await lines.evaluateAll((els) => els.map((el) => Number(el.getAttribute("data-line"))));
    expect(order).toEqual([...order].sort((a, b) => a - b));
    const lastLine = (await lines.last().boundingBox())!;
    const send = (await page.getByTestId("deal-send").boundingBox())!;
    expect(lastLine.y + lastLine.height, "the last line ends before the button begins").toBeLessThanOrEqual(send.y);
    expect(await page.evaluate(() => {
      const last = Array.from(document.querySelectorAll('[data-testid^="receipt-line-"]')).pop()!;
      const button = document.querySelector('[data-testid="deal-send"]')!;
      return Boolean(last.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING);
    })).toBe(true);
    // The figures and the basis words under them are 13 px or larger: no financial qualifier is 12 px.
    const small = await page.evaluate(() => Array.from(document.querySelectorAll('[data-testid="queue-review"] *')).filter((el) => el.children.length === 0 && (el.textContent ?? "").trim() && parseFloat(getComputedStyle(el).fontSize) < 13).length);
    expect(small).toBe(0);
  });

  test("the scope chip names what the question is about before it is asked, widens for this route only, and clears when the route changes", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("chat-open").click();
    const chip = await scope(page);
    await expect(chip).toHaveAttribute("data-kind", "decision");
    await expect(chip.getByRole("tab")).toHaveText(["Decision", "Customer", "Company"]);
    await expect(page.getByTestId("chat-scope-name")).toContainText("Foshan Home Retail Co.");
    await chip.getByRole("tab", { name: "Company" }).click();
    await expect(chip).toHaveAttribute("data-kind", "company");
    await page.keyboard.press("Escape");
    // Another route: the choice is void, and the chip follows the address (Customer has its own questions).
    await page.goto("/customers/BUYER-1");
    await page.getByTestId("chat-open").click();
    await expect(await scope(page)).toHaveAttribute("data-kind", "customer");
    await expect(page.getByRole("dialog", { name: "Ask FLOW" }).locator('[data-testid^="prompt-"]')).toHaveText(["Who owes us money?", "What is overdue?", "What happens if this payment is late?", "What are we waiting for?"]);
    await page.keyboard.press("Escape");
    await page.goto("/activity");
    await page.getByTestId("chat-open").click();
    await expect(await scope(page)).toHaveAttribute("data-kind", "company");
    await expect(page.getByRole("dialog", { name: "Ask FLOW" }).locator('[data-testid^="prompt-"]')).toHaveText(["What changed today?", "What are we waiting for?", "Which payments are late?"]);
  });

  test("Receivables registers the invoice it shows as the scope, even when it is the default row", async ({ page }) => {
    await page.goto("/receivables");
    await expect(page.getByTestId("recv-RCV-A")).toBeVisible();
    await page.getByTestId("chat-open").click();
    const chip = await scope(page);
    await expect(chip).toHaveAttribute("data-kind", "invoice");
    await expect(chip.getByRole("tab")).toHaveText(["Invoice", "Customer", "Company"]);
  });

  test("Ask FLOW is a quiet outline pill, never a filled button", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/deals");
    const pill = page.getByTestId("chat-open");
    await expect(pill).toBeVisible();
    const fill = await pill.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(fill).not.toBe("rgb(3, 104, 233)");
    expect(fill).not.toBe("rgb(23, 29, 30)");
    expect(await pill.evaluate((el) => parseFloat(getComputedStyle(el).borderTopWidth))).toBeGreaterThan(0);
  });
});

test.describe("live", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(!live(testInfo), "live-only: the busy company on a real API");
  });

  async function busy(request: import("@playwright/test").APIRequestContext) {
    const port = process.env.E2E_API_PORT ?? 8000;
    const res = await request.post(`http://localhost:${port}/demo/reset?scenario=busy`, { headers: { "X-Owner-Token": DEMO_TOKEN } });
    expect(res.ok()).toBeTruthy();
  }

  test("the busy company's queue has one row per task: two Foshan negotiations are two rows, an approval, a collection and the agreement's promise each their own", async ({ page, request }) => {
    await busy(request);
    await page.goto("/deals");
    await expect(page.getByTestId("queue-count-needs_you")).toHaveText("6");
    await expect(page.getByTestId("queue-count-waiting")).toHaveText("1");
    await expect(page.getByTestId("queue-count-agreements")).toHaveText("2");
    await expect(page.getByTestId("queue-count-customers")).toHaveText("3");
    await expect(page.getByTestId("queue-count-all")).toHaveText("9");
    const rows = page.locator('[data-testid="queue-row"]');
    await expect(rows).toHaveCount(9);
    const foshan = page.locator('[data-testid="queue-row"][data-tier="needs_you"][data-kind="DECISION"]').filter({ hasText: "Foshan" });
    await expect(foshan).toHaveCount(2);
    const hrefs = await foshan.getByTestId("queue-customer").evaluateAll((els) => els.map((el) => el.getAttribute("href")!));
    expect(new Set(hrefs).size, "each row's customer link carries its own decision").toBe(2);
    for (const href of hrefs) expect(href).toMatch(/^\/customers\/BUYER-1\?decision=deal%3AOFF-.*&from=deal$/);
    await expect(page.locator('[data-testid="queue-row"][data-kind="APPROVAL"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="queue-row"][data-kind="COLLECTION"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="queue-row"][data-kind="PROMISE"]')).toHaveCount(1);
    // No id and no day number in the prose.
    await expect(page.locator("main")).not.toContainText(/OFF-|BUYER-\d|RCV-|\bDay \d/);
    // Selecting one of the two Foshan rows opens that negotiation and no other.
    await foshan.nth(1).getByTestId("queue-select").click();
    await expect(page).toHaveURL(/decision=deal%3AOFF-/);
    const chosen = new URL(page.url()).searchParams.get("decision");
    await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-decision", chosen!);
  });

  test("Ask FLOW sends the scope the chip showed and nothing stale, and says what the server used", async ({ page, request }) => {
    await resetBooks(request);
    await page.goto("/deals");
    await openInbox(page);
    await page.getByTestId("inbox-msg-EX01").click();
    await page.getByTestId("queue-check-button").click();
    await page.getByTestId("queue-recommends").waitFor();
    const bodies: Record<string, unknown>[] = [];
    page.on("request", (r) => {
      if (r.method() === "POST" && /\/nl(\?|$)/.test(r.url())) bodies.push(r.postDataJSON() as Record<string, unknown>);
    });
    await page.getByTestId("chat-open").click();
    const panel = page.getByRole("dialog", { name: "Ask FLOW" });
    await panel.getByTestId("prompt-page-counter").click();
    await expect(panel.getByTestId("chat-turn").last()).toBeVisible();
    expect(bodies.length).toBe(1);
    const sent = bodies[0] as { scope?: { customer?: string; decision?: string }; context?: Record<string, unknown> };
    expect(sent.scope?.decision).toMatch(/^deal:OFF-/);
    expect(sent.scope?.customer).toBe("BUYER-1");
    expect(sent.context && "offer_id" in sent.context, "no prior-offer context").toBe(false);
    await expect(panel.getByTestId("chat-discussing")).toContainText("Answered about:");
    await expect(panel.getByTestId("chat-discussing")).toHaveAttribute("data-mismatch", "false");
    // Widened to the company, the next question carries no deal and no customer.
    await panel.getByTestId("chat-scope").getByRole("tab", { name: "Company" }).click();
    await panel.getByTestId("prompt-page-waiting").click();
    await expect.poll(() => bodies.length).toBe(2);
    expect((bodies[1] as { scope?: unknown }).scope).toBeUndefined();
  });
});
