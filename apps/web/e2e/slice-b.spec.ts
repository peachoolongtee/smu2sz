import type { Page } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { checkedDeal, expandRow, openCompare, openInbox, openOperatorTools, openReview, resetBooks } from "./helpers";

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

  test("a deep link in a fresh session hydrates the negotiation, its reply and its open comparison from the server", async ({ page }) => {
    await checkedDeal(page);
    await page.evaluate(() => sessionStorage.removeItem("tl-demo-v3")); // the tab's own session cache is gone: only the server is read
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(DECISION)}&path=CTR-6b07cbf70441&view=compare`);
    await expect(page.getByTestId("deal-state-chip")).toHaveAttribute("data-state", "RESPONSE_READY");
    await expect(page.locator('[data-testid="deal-compare-table"]:visible')).toBeVisible();
    await expect(page.locator('[data-testid="deal-use-CTR-6b07cbf70441"]:visible')).toHaveText("Option B is selected");
    await page.getByTestId("deal-tab-overview").click();
    await expect(page.getByTestId("deal-recommends-title")).toHaveText("The response you picked · Option B");
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

  test("a decision in the address that is not a deal (a funding request) asks which negotiation at once and never waits", async ({ page }) => {
    await page.goto("/deals?decision=approval%3AAPR-000001");
    await expect(page.getByTestId("deal-ask-which")).toContainText("Which negotiation?");
    await expect(page.getByTestId("deal-ask-which")).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText("Working it out…")).toHaveCount(0);
    await expect(page.getByTestId("deal-pane")).toHaveCount(0);
    await page.getByTestId("deal-which-close").click();
    await expect(page).toHaveURL(/\/deals$/);
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
    // The three statements (authorizing, immediately, not yet) come before the button; the rest of the receipt is the fold after it.
    const lines = page.locator('[data-testid="send-statements"] [data-testid^="receipt-line-"]');
    expect(await lines.count()).toBeGreaterThanOrEqual(3);
    const order = await lines.evaluateAll((els) => els.map((el) => Number(el.getAttribute("data-line"))));
    expect(order).toEqual([...order].sort((a, b) => a - b));
    const lastLine = (await lines.last().boundingBox())!;
    const send = (await page.getByTestId("deal-send").boundingBox())!;
    expect(lastLine.y + lastLine.height, "the last line ends before the button begins").toBeLessThanOrEqual(send.y);
    expect(await page.evaluate(() => {
      const last = Array.from(document.querySelectorAll('[data-testid="send-statements"] [data-testid^="receipt-line-"]')).pop()!;
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
    await expect(page.getByRole("dialog", { name: "Ask FLOW" }).locator('[data-testid^="prompt-"]')).toHaveText(["What changed today?", "What are we waiting for?", "Which payments are late?", "Who owes us money?"]);
  });

  test("the queue's card holds its row at 1440, 820 and 390, in English and in Chinese; with one negotiation it offers no tabs (the four tabs on one line are pinned on the busy books in slice-b-round-three.spec.ts)", async ({ page }) => {
    for (const lang of ["en", "zh"] as const) {
      await page.addInitScript((l) => localStorage.setItem("tl-lang", JSON.stringify({ lang: l })), lang);
      for (const width of [1440, 820, 390]) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/deals");
        const card = page.getByTestId("deals-queue");
        await expect(card).toBeVisible();
        const box = (await card.boundingBox())!;
        await expect(page.getByTestId("queue-tabs"), `${lang} ${width}: one row, no tabs`).toHaveCount(0);
        await expect(page.getByTestId("queue-empty").or(page.getByTestId("queue-total")).first()).toBeVisible();
        expect(box.x + box.width, `${lang} ${width}: the card is inside the page`).toBeLessThanOrEqual(width + 1);
      }
    }
  });

  test("the scope chip's widened choice does not come back: Deals, widen to Company, Customer, Back, and the chip is the decision again", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("chat-open").click();
    await page.getByTestId("chat-scope").getByRole("tab", { name: "Company" }).click();
    await expect(await scope(page)).toHaveAttribute("data-kind", "company");
    await page.keyboard.press("Escape");
    // A client-side navigation (the customer's name is a link), then the browser's Back: the same address, a new visit.
    await page.getByTestId("deal-selected-customer").click();
    await expect(page).toHaveURL(/\/customers\/BUYER-1/);
    await page.goBack();
    await expect(page.getByTestId("deal-pane")).toBeVisible();
    await page.getByTestId("chat-open").click();
    await expect(await scope(page)).toHaveAttribute("data-kind", "decision");
    // A choice made on this visit still holds while the owner stays on it.
    await page.getByTestId("chat-scope").getByRole("tab", { name: "Customer" }).click();
    await page.keyboard.press("Escape");
    await page.getByTestId("chat-open").click();
    await expect(await scope(page)).toHaveAttribute("data-kind", "customer");
  });

  test("no financial qualifier is 12 px: What-if's limit, face and current terms, and the approval's Amount requested, Facility and What if you decline", async ({ page }) => {
    const small = (el: Element) => parseFloat(getComputedStyle(el).fontSize) < 13;
    await checkedDeal(page);
    await page.getByTestId("deal-whatif").click();
    await expect(page.getByTestId("whatif-outcome")).toBeVisible();
    for (const text of [/^Now \d+ days/, /^Whole invoice/]) {
      const el = page.getByText(text).first();
      await expect(el).toBeVisible();
      expect(await el.evaluate(small), String(text)).toBe(false);
    }
    // Everything in the figures strip that qualifies a figure (the limit, the headroom) is 13 px too.
    const qualifiers = page.locator('[data-testid="whatif-outcome"] ~ * dd, main dd').filter({ hasText: /limit|headroom/i });
    for (const el of await qualifiers.all()) expect(await el.evaluate(small)).toBe(false);
    // The approval card.
    await page.goto("/demo");
    await openOperatorTools(page); // the optional scenes sit in the Demo's operator tools fold
    await page.getByTestId("more-run-capex").click();
    await expect(page).toHaveURL(/\/capex/);
    await page.goto("/approvals");
    await page.goto("/capex");
    await page.getByTestId("capex-apply").click();
    await expect(page.getByTestId("capex-applied")).toBeVisible();
    await page.goto("/approvals");
    const card = page.locator("#approval-APR-000001");
    // Round two: the summary's rows (Amount requested, Facility, What if you decline) are the card's own, 13 px at the least.
    for (const label of ["Amount requested", "Facility", "What if you decline"]) {
      const el = card.getByText(label, { exact: true }).first();
      await expect(el, label).toBeVisible();
      expect(await el.evaluate(small), label).toBe(false);
    }
  });

  test("a term or a figure the server has no word for is omitted, never the word None", async ({ page }) => {
    await checkedDeal(page);
    await expect(page.getByTestId("deal-pane").getByText("None", { exact: true })).toHaveCount(0);
    await openCompare(page);
    await expect(page.getByTestId("deal-panel-compare").getByText("None", { exact: true })).toHaveCount(0);
    await page.goto("/customers/BUYER-1");
    await expect(page.getByTestId("customer-figures")).toBeVisible();
    await expect(page.locator("main").getByText("None", { exact: true })).toHaveCount(0);
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
    // On a desktop the entry is the header's input (Home round three): a bordered field, never a filled button; its opener beside it is quiet too.
    const entry = page.getByTestId("ask-header");
    await expect(entry).toBeVisible();
    expect(await entry.evaluate((el) => parseFloat(getComputedStyle(el).borderTopWidth))).toBeGreaterThan(0);
    for (const el of [entry, page.getByTestId("chat-open")]) {
      const fill = await el.evaluate((e) => getComputedStyle(e).backgroundColor);
      expect(fill).not.toBe("rgb(3, 104, 233)");
      expect(fill).not.toBe("rgb(23, 29, 30)");
    }
  });
});

test.describe("live", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(!live(testInfo), "live-only: the busy company on a real API");
  });
  // The busy books are loaded by these specs: the golden books go back through the API when each one is done, so a later spec (the Demo story, which starts on the golden books) never finds them.
  test.afterEach(async ({ request }) => {
    await resetBooks(request);
  });

  async function busy(request: import("@playwright/test").APIRequestContext) {
    const port = process.env.E2E_API_PORT ?? 8000;
    const res = await request.post(`http://localhost:${port}/demo/reset?scenario=busy`, { headers: { "X-Owner-Token": DEMO_TOKEN } });
    expect(res.ok()).toBeTruthy();
  }

  test("the busy company's queue has one row per task: three Foshan negotiations are three rows, an approval and a collection each their own, and the tab counts are the Home's", async ({ page, request }) => {
    await busy(request);
    await page.goto("/deals");
    // Day 0 of the busy books: nothing is agreed yet (the agreements come from the owner's own sends), so the Agreements tab is empty.
    // Round two: Deals lists negotiations only (the server's `queue.deals` counts): the five decisions waiting on the owner and the buyer's reply; the loan approval and the overdue collection are Approvals' and Receivables' (Home keeps all eight).
    await expect(page.getByTestId("queue-count-needs_you")).toHaveText("5");
    await expect(page.getByTestId("queue-count-waiting")).toHaveText("1");
    await expect(page.getByTestId("queue-count-agreements")).toHaveText("0");
    await expect(page.getByTestId("queue-count-all")).toHaveText("6");
    const rows = page.locator('[data-testid="queue-row"]');
    await expect(rows).toHaveCount(6);
    const foshan = page.locator('[data-testid="queue-row"][data-tier="needs_you"][data-kind="DECISION"]').filter({ hasText: "Foshan" });
    await expect(foshan).toHaveCount(3);
    const hrefs = await foshan.getByTestId("queue-customer").evaluateAll((els) => els.map((el) => el.getAttribute("href")!));
    expect(new Set(hrefs).size, "each row's customer link carries its own decision").toBe(3);
    for (const href of hrefs) expect(href).toMatch(/^\/customers\/BUYER-1\?decision=deal%3AOFF-.*&from=deal$/);
    await expect(page.locator('[data-testid="queue-row"][data-kind="APPROVAL"]')).toHaveCount(0);
    await expect(page.locator('[data-testid="queue-row"][data-kind="COLLECTION"]')).toHaveCount(0);
    // No id and no day number in the prose.
    await expect(page.locator("main")).not.toContainText(/OFF-|BUYER-\d|RCV-|\bDay \d/);
    // Selecting one of the Foshan rows opens that negotiation and no other.
    await foshan.nth(1).getByTestId("queue-select").click();
    await expect(page).toHaveURL(/decision=deal%3AOFF-/);
    const chosen = new URL(page.url()).searchParams.get("decision");
    await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-decision", chosen!);
    // Home says the same numbers as Deals.
    await page.goto("/");
    await expect(page.getByTestId("home-tab-needs_you-badge")).toHaveText("7");
    await expect(page.getByTestId("home-tab-waiting-badge")).toHaveText("1");
  });

  test("the approval row is a link to the Approvals page with that approval in view, never a selection; a differentiator is quoted once, on Deals and on Home", async ({ page, request }) => {
    await busy(request);
    // The approval is Home's row (Deals lists negotiations only): a link to the Approvals page with that approval in view, never a selection.
    await page.goto("/");
    const approval = page.locator('[data-testid="home-worklist-row"][data-kind="APPROVAL"]');
    await expect(approval).toHaveCount(1);
    const href = await approval.getByTestId("hv2-row-link").getAttribute("href");
    expect(href).toMatch(/^\/approvals#approval-APR-\d+$/);
    await page.goto("/deals");
    await expect(page.locator('[data-testid="queue-row"][data-kind="APPROVAL"]')).toHaveCount(0);
    await page.goto("/");
    await approval.getByTestId("hv2-row-link").click();
    await expect(page).toHaveURL((url) => url.pathname + url.hash === href);
    await expect(page.locator(`#${href!.split("#")[1]}`)).toBeVisible();
    await expect(page.getByTestId("deal-ask-which")).toHaveCount(0);

    // A direct load of the funding request as a decision asks at once.
    await page.goto("/deals?decision=approval%3AAPR-000001");
    await expect(page.getByTestId("deal-ask-which")).toContainText("Which negotiation?");
    await expect(page.getByText("Working it out…")).toHaveCount(0);

    // Round two: the server writes the subject distinct, the differentiator in it already quoted (one quoted phrase, never doubled quote marks), on Deals and on Home.
    await page.goto("/deals");
    await expect(page.getByTestId("queue-row").first()).toBeVisible();
    const quoted = async (testId: string) => (await page.getByTestId(testId).allTextContents()).filter((t) => t.includes("“"));
    const deals = await quoted("queue-subject");
    expect(deals.length, "the busy books hold rows that need a differentiator").toBeGreaterThan(0);
    for (const text of deals) expect(text, "Deals queue").toMatch(/^[^“”]*“[^“”]+”[^“”]*$/);
    await page.goto("/");
    await expect(page.getByTestId("hv2-row-subject").first()).toBeVisible();
    const home = await quoted("hv2-row-subject");
    expect(home.length, "Home shows the same rows").toBeGreaterThan(0);
    for (const text of home) expect(text, "Home worklist").toMatch(/^[^“”]*“[^“”]+”[^“”]*$/);
  });

  test("the What-if list offers negotiations only, not the loan approval; an agreed negotiation shows its record and no evaluation prompt; an ask that needs approval and has no counter shows its cost and offers no button", async ({ page, request }) => {
    await busy(request);
    await page.goto("/deals");
    await expect(page.getByTestId("queue-row").first()).toBeVisible();
    // The sandbox offers every negotiation (one needing the owner, or one waiting on the buyer), never an approval, collection or promise.
    const decisions = await page.locator('[data-testid="queue-row"][data-kind="DECISION"]:not([data-tier="agreements"]), [data-testid="queue-row"][data-kind="BUYER_REPLY"]:not([data-tier="agreements"])').count();
    expect(await page.locator('[data-testid="queue-row"][data-kind="APPROVAL"]').count(), "the loan approval is not a negotiation: it is not in Deals' queue").toBe(0);
    await page.goto("/whatif");
    await expect(page.getByTestId("whatif-choice")).toHaveCount(decisions);
    await expect(page.getByTestId("whatif-choices")).not.toContainText(/loan|approval/i);

    // A negotiation the owner has agreed: send the counter on Foshan's "same arrangement as usual" request (a read that abstained), and the agreed pane shows the agreement record,
    // its receipt and terms, and no "can't safely evaluate" with Clarify above "Agreed".
    const AGREED = "deal:OFF-39cabafae4ee";
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(AGREED)}`);
    await expect(page.getByTestId("deal-pane")).toBeVisible();
    await page.getByTestId("queue-review-open").click();
    await page.getByTestId("deal-send").click();
    await expect(page.getByTestId("deal-sent")).toBeVisible();
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent(AGREED)}`);
    await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-state", "AGREED");
    await page.getByTestId("deal-tab-terms").click();
    await expect(page.getByTestId("deal-record")).toBeVisible();
    await expect(page.getByTestId("deal-agreement-receipt")).toBeVisible();
    await expect(page.getByTestId("deal-abstentions")).toHaveCount(0);
    await expect(page.getByTestId("deal-pane")).not.toContainText(/can't safely evaluate/i);
    await expect(page.getByRole("link", { name: "Clarify" })).toHaveCount(0);

    // The Zhuhai ask needs approval and FLOW has no counter: the ask's own cost and basis are shown, the authority is said, and there is no commit control.
    await page.goto("/deals?tab=needs_you");
    await page.locator('[data-testid="queue-row"][data-kind="DECISION"]').filter({ hasText: "Zhuhai" }).getByTestId("queue-select").click();
    const none = page.getByTestId("deal-no-reply");
    await expect(none).toBeVisible();
    // The ask's own cost and basis are in the comparison's economic row, behind its calculation.
    await openCompare(page);
    await expandRow(page, "economic");
    await expect(page.locator('[data-testid="deal-cost-table-total-asked"]:visible')).toContainText(/¥\d/);
    await expect(page.locator('[data-testid="deal-cost-table-total-asked"]:visible')).toContainText("over 12 months");
    await page.getByTestId("deal-back").click();
    await expect(none).toContainText("you approve it first");
    await expect(page.getByTestId("deal-send")).toHaveCount(0);
    await expect(page.getByTestId("deal-review")).toHaveCount(0);
    await expect(page.getByTestId("deal-pane")).not.toContainText(/\bNone\b/);
    await expect(page.getByTestId("deal-scope-terms-table")).not.toContainText(/\bNone\b/);
  });

  test("the send review of a picked reply reads that reply's own receipt, not the recommended one's, and Send names the picked reply", async ({ page, request }) => {
    await resetBooks(request);
    await checkedDeal(page); // the opening books' EX01: Option A (FLOW may send it) and Option B (needs the owner's approval), both sendable
    await page.getByTestId("queue-review-open").click();
    const receipt = page.getByTestId("queue-review").getByTestId("commitment-receipt");
    await expect(receipt).toBeVisible();
    const recommended = (await receipt.textContent())!;
    const recommendedLabel = (await page.getByTestId("deal-send").textContent())!;
    await page.getByTestId("queue-review-close").click();
    await openCompare(page);
    // The first reply that is not the recommended one.
    await page.locator('[data-testid^="deal-use-"]:visible').nth(1).click();
    await expect(page.locator('[data-testid^="deal-use-"]:visible').nth(1)).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("queue-review-open").click();
    const picked = page.getByTestId("queue-review");
    await expect(picked.getByTestId("commitment-receipt")).toBeVisible();
    expect((await picked.getByTestId("commitment-receipt").textContent())!, "the picked reply's own receipt, not Option A's").not.toBe(recommended);
    expect((await page.getByTestId("deal-send").textContent())!).not.toBe(recommendedLabel);
    await expect(page.getByTestId("deal-unpriced")).toHaveCount(0);
  });

  test("What-if runs on the addressed negotiation's own invoice, in the server's words, and says why when the buyer has none it can act on", async ({ page, request }) => {
    await busy(request);
    const run = (offer: string, customer: string) => `/whatif?customer=${customer}&decision=${encodeURIComponent(`deal:${offer}`)}&from=deal`;
    await page.goto(run("OFF-96e709c2b1d8", "BUYER-3"));
    await expect(page.getByTestId("whatif-invoice")).toContainText(/the ¥150,000\.00 invoice to Zhuhai .*, due in \d+ days/);
    await expect(page.getByTestId("whatif-terms-readout")).toBeVisible();
    await expect(page.getByTestId("whatif-scope")).not.toContainText(/RCV-|Settle only part of RCV/);
    await expect(page.getByText("Settle only part of this invoice")).toBeVisible();
    await expect(page.getByText(/Settle only part of RCV/)).toHaveCount(0);
    // The assumption the sandbox runs on and the negotiation's own figure stand under the subject, as the server sent them; the cash word is the server's, not derived from a breach day.
    await expect(page.getByTestId("whatif-scope-text")).toContainText(/^The sandbox applies the terms to every Zhuhai invoice for the next 12 months, not only the next one; the negotiation itself asks for one invoice\.$/);
    await expect(page.getByTestId("whatif-compare")).toContainText(/^The negotiation as asked: .*(within|over) your limit\.$/);
    await expect(page.getByTestId("whatif-cash-fig")).toHaveText(/^(Stays above it|Below it for \d+ days?)$/);
    // Another buyer, another invoice.
    await page.goto(run("OFF-4f6bf9834d4d", "BUYER-1"));
    await expect(page.getByTestId("whatif-invoice")).toContainText("the ¥420,000.00 invoice to Foshan");
    // A buyer with no recurring invoice to extend: the server's reason, no sliders, no verdict.
    await page.goto(run("OFF-ea1ac57ae2a0", "BUYER-2"));
    await expect(page.getByTestId("whatif-unscoped")).toContainText("no recurring invoice to extend");
    await expect(page.getByTestId("whatif-terms-readout")).toHaveCount(0);
    await expect(page.getByTestId("whatif-outcome")).toHaveCount(0);
  });

  test("a negotiation whose invoice was settled under another agreement is Lapsed: its word in the pane, no reply ready, no cost, and it is gone from the queue", async ({ page, request }) => {
    await busy(request);
    // Agreeing Foshan's early-payment counter settles the invoice the other two Foshan requests were about.
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent("deal:OFF-39cabafae4ee")}`);
    await page.getByTestId("queue-review-open").click();
    await page.getByTestId("deal-send").click();
    await expect(page.getByTestId("deal-sent")).toBeVisible();
    await page.goto(`/deals?customer=BUYER-1&decision=${encodeURIComponent("deal:OFF-f806f79b6c21")}`);
    const pane = page.getByTestId("deal-pane");
    await expect(pane).toHaveAttribute("data-state", "LAPSED");
    await expect(page.getByTestId("deal-state-chip")).toContainText("Lapsed");
    await expect(page.getByTestId("queue-recommends")).toHaveCount(0);
    await expect(page.getByTestId("queue-review-open")).toHaveCount(0);
    await expect(page.getByTestId("deal-send")).toHaveCount(0);
    await expect(page.getByTestId("deal-costs")).toHaveCount(0);
    await expect(page.getByTestId("deal-abstentions")).toHaveCount(0);
    // The lapsed pane says what the server says: nobody is waiting on it.
    await expect(page.getByTestId("deal-waiting")).toHaveText("Nothing to do: this offer lapsed.");
    // The queue lists no lapsed decision as a task.
    await expect(page.locator('[data-testid="queue-row"][data-tier="needs_you"][data-kind="DECISION"]').filter({ hasText: "Foshan" })).toHaveCount(0);
  });

  test("the approval says what approving does and, once approved, the server's own result words; the queue row says the same", async ({ page, request }) => {
    await busy(request);
    const port = process.env.E2E_API_PORT ?? 8000;
    const rows = async () => ((await (await request.get(`http://localhost:${port}/approvals/queue?lang=en`, { headers: { "X-Owner-Token": DEMO_TOKEN } })).json()) as { approvals: { id: string; result_state_text: string | null }[] }).approvals;
    await page.goto("/");
    const row = page.locator('[data-testid="home-worklist-row"][data-kind="APPROVAL"]');
    await expect(row).toContainText("Approving submits the application; nothing runs until the bank commits.");
    await page.goto("/approvals");
    const card = page.locator("#approval-APR-000001");
    // The button names the act (the server's `commit_label`), not the amount.
    await expect(card.getByTestId("approval-approve-APR-000001")).toHaveText("Authorize the application");
    await card.getByTestId("approval-approve-APR-000001").click();
    const served = (await rows()).find((r) => r.id === "APR-000001")!.result_state_text;
    expect(served, "the server names the result").toBeTruthy();
    await expect(card.getByTestId("approval-state-APR-000001")).toHaveText(served!);
    await expect(card).toContainText(/submitted/i);
    // (the lifecycle names its stage "done" for assistive tools; the outcome, the state word and the headline never say the bare word)
    await expect(card.getByTestId("approval-outcome-APR-000001")).not.toContainText(/\bdone\b/i);
    await expect(card.getByTestId("approval-state-APR-000001")).not.toContainText(/\bdone\b/i);
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
