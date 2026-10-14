import type { APIRequestContext, Page } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { checkedDeal, resetBooks } from "./helpers";

/**
 * Accept as asked (map #121): a negotiation whose buyer request needs the owner's review and has no counter (the busy books' Zhuhai 75-day terms and Dongguan rebate,
 * `lifecycle: owner_review`) can be reviewed, accepted as asked or declined from the Deals pane. The review is the server's `accept.receipt` as three statements, the terms and
 * the cost of the ask, then ONE filled button (`accept.commit_label`) with a quiet decline beside it. Every word asserted is read from the page or the API.
 *
 * Live project: the busy company on a real API (POST /demo/reset?scenario=busy); the mock holds no request that may be accepted as asked (its one open offer, EX01, has counters), so the
 * mock project runs only the golden EX01 check: its asked path is over the mandate, the server says so and nothing is offered.
 */

const live = (info: { project: { name: string } }) => info.project.name === "live";
const API = () => `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const headers = { "X-Owner-Token": DEMO_TOKEN };

async function busy(request: APIRequestContext) {
  const res = await request.post(`${API()}/demo/reset?scenario=busy`, { headers });
  expect(res.ok()).toBeTruthy();
}

/** The queue's row for a customer's request that needs the owner's review, selected. */
async function selectRequest(page: Page, customer: string) {
  await page.goto("/deals?tab=needs_you");
  await page.locator('[data-testid="queue-row"][data-lifecycle="owner_review"]').filter({ hasText: customer }).getByTestId("queue-select").click();
  await expect(page.getByTestId("deal-pane")).toBeVisible();
}

/** The receipt's statements come before the commit control in the reading order. */
async function receiptBeforeButton(page: Page) {
  const before = await page.evaluate(() => {
    const receipt = document.querySelector('[data-testid="accept-review"] [data-testid="commitment-receipt"]');
    const go = document.querySelector('[data-testid="accept-go"]');
    return Boolean(receipt && go && receipt.compareDocumentPosition(go) & Node.DOCUMENT_POSITION_FOLLOWING);
  });
  expect(before, "the receipt precedes the commit button in the DOM").toBe(true);
  const [r, b] = await Promise.all([page.getByTestId("accept-review").getByTestId("commitment-receipt").boundingBox(), page.getByTestId("accept-go").boundingBox()]);
  expect(r!.y, "and on screen").toBeLessThan(b!.y);
}

test.describe("mock", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("the golden EX01 asked path is over the mandate: the comparison says it is outside the mandate, the server's reason is said once in full, and no accept button is offered", async ({ page }) => {
    await checkedDeal(page);
    await page.getByTestId("deal-tab-compare").click();
    await expect(page.getByTestId("deal-compare-head-asked").getByTestId("deal-compare-badge")).toHaveText("Outside mandate");
    await expect(page.getByTestId("deal-why-authority")).toContainText("As they asked.");
    await expect(page.getByTestId("deal-why-authority")).toContainText(/mandate/i);
    await expect(page.getByTestId("deal-review-request")).toHaveCount(0);
    await expect(page.getByTestId("accept-go")).toHaveCount(0);
    await expect(page.getByTestId("accept-review-open")).toHaveCount(0);
    // The one filled button is still the send's, and its review has no fourth statement: "What it does to your cash" belongs to accepting as asked, and only when the server writes it.
    await expect(page.getByTestId("queue-review-open")).toBeVisible();
    await page.getByTestId("queue-review-open").click();
    await expect(page.getByTestId("send-statements")).toBeVisible();
    await expect(page.getByTestId("receipt-line-cash")).toHaveCount(0);
  });
});

test.describe("live", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(!live(testInfo), "live-only: the busy company on a real API");
  });

  test("the golden books' EX01 asked path is over the mandate: the server's reason is said and no accept button is offered", async ({ page, request }) => {
    await resetBooks(request);
    await checkedDeal(page);
    await expect(page.getByTestId("accept-reason-asked")).toContainText(/mandate/i);
    await expect(page.getByTestId("accept-go")).toHaveCount(0);
    await expect(page.getByTestId("accept-review-open")).toHaveCount(0);
  });

  test("Zhuhai: Review the request opens the receipt before the one filled button; accepting agrees it, the record reads Agreed, the queue drops it and Activity says so", async ({ page, request }) => {
    await busy(request);
    await selectRequest(page, "Zhuhai");
    const none = page.getByTestId("deal-no-reply");
    await expect(none).toBeVisible();
    await expect(page.getByTestId("accept-review")).toHaveCount(0);
    // One outline button leads; nothing is filled until the review is open.
    const open = page.getByTestId("accept-review-open");
    await expect(open).toHaveText("Review the request");
    await open.click();
    const review = page.getByTestId("accept-review");
    await expect(review).toBeVisible();
    const statements = review.getByTestId("send-statements");
    // Three statements, then a fourth when accepting moves the cash against the reserve (the server's `cash_text`; Zhuhai's does).
    await expect(statements.locator("dt")).toHaveText(["What you are authorizing", "What happens immediately", "What does not happen yet", "What it does to your cash"]);
    await expect(review.getByTestId("receipt-line-cash")).not.toBeEmpty();
    await expect(review.getByTestId("accept-terms-table")).toContainText("75 days");
    await expect(review.getByTestId("accept-cost-table")).toContainText("over 12 months");
    await receiptBeforeButton(page);
    // The one filled button names the act; the decline is quiet beside it.
    const go = page.getByTestId("accept-go");
    await expect(go).toBeEnabled();
    await expect(go).toHaveText("Accept as asked");
    await expect(page.getByTestId("accept-decline")).toHaveText("Decline the request");
    expect(await go.evaluate((el) => getComputedStyle(el).backgroundColor), "the one filled button is the ink primary").toBe("rgb(23, 29, 30)");
    expect(await page.getByTestId("accept-decline").evaluate((el) => getComputedStyle(el).backgroundColor), "the decline is quiet").toBe("rgba(0, 0, 0, 0)");
    await go.click();
    // The server's own account of what ran, then the record: Agreed, with the agreement's receipt.
    await expect(page.getByTestId("deal-accepted-ran")).not.toBeEmpty();
    await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-state", "AGREED");
    await page.getByTestId("deal-tab-terms").click();
    await expect(page.getByTestId("deal-record")).toBeVisible();
    await expect(page.getByTestId("deal-state-chip")).toContainText("Agreed");
    await expect(page.getByTestId("accept-go")).toHaveCount(0);
    // The queue no longer asks for it.
    await page.goto("/deals?tab=needs_you");
    await expect(page.locator('[data-testid="queue-row"]').filter({ hasText: "Zhuhai" })).toHaveCount(0);
    // And the record of what happened is on Activity.
    await page.goto("/activity");
    await expect(page.getByRole("main")).toContainText(/Zhuhai/);
    await expect(page.getByRole("main")).toContainText("You accepted Zhuhai's request as asked.");
  });

  test("an agreed Zhuhai is in force and does not expire: no 'expire' word, no empty or trailing '·', no None or null, on the Deals pane, the Agreements tab, the Deals agreements section and the decision record", async ({ page, request }) => {
    await busy(request);
    const offer = await offerOfRow(request, "Zhuhai");
    const decision = `deal:${offer}`;
    // Accept through the API with what a review would send (the verdict the owner is shown and its books version).
    const evaluated = await request.post(`${API()}/offers/${offer}/evaluate`, { headers, data: {} });
    expect(evaluated.ok()).toBeTruthy();
    const verdict = (await evaluated.json()) as { id: string; state_version: number };
    const accepted = await request.post(`${API()}/offers/${offer}/accept`, { headers, data: { verdict_id: verdict.id, state_version: verdict.state_version } });
    expect(accepted.ok(), await accepted.text()).toBeTruthy();
    const record = (await (await request.get(`${API()}/decisions/${encodeURIComponent(decision)}?lang=en`, { headers })).json()) as { agreement: { expires_day: number | null; expires_when: string | null } };
    expect(record.agreement.expires_when, "the server says an agreement in force has no expiry").toBeNull();
    const clean = async (locator: ReturnType<Page["locator"]>, what: string) => {
      const text = ((await locator.textContent()) ?? "").replace(/\s+/g, " ");
      expect(text, `${what}: no expire word`).not.toMatch(/expire/i);
      expect(text, `${what}: no None or null`).not.toMatch(/\b(None|null|undefined)\b/);
      expect(text, `${what}: no empty or trailing separator`).not.toMatch(/(^|\s)·(\s|$)\s*$|·\s*·|^\s*·/);
    };
    // The Deals pane: the record's agreement line and the agreement receipt.
    await page.goto(`/deals?decision=${encodeURIComponent(decision)}`);
    await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-state", "AGREED");
    await page.getByTestId("deal-tab-terms").click();
    await clean(page.getByTestId("deal-agreement"), "the agreement line");
    await expect(page.getByTestId("deal-agreement")).toHaveText(/\S/);
    await expect(page.getByTestId("deal-agreement-receipt")).toContainText("In force.");
    await clean(page.getByTestId("deal-record"), "the record block");
    // The Agreements tab's row for it, and the section under the panes.
    await page.goto("/deals?tab=agreements");
    await expect(page.getByTestId("queue-list")).toBeVisible();
    await clean(page.getByTestId("deals-queue"), "the Agreements tab");
    await clean(page.getByTestId("deals-agreements"), "the agreements section");
    // The decision record page.
    await page.goto(`/decisions/${encodeURIComponent(decision)}`);
    await expect(page.getByTestId("record-agreement")).toBeVisible();
    await clean(page.getByRole("main"), "the decision record page");
  });

  test("Dongguan: declining asks once in one line, closes the request and leaves the queue; the pane shows Declined with the record", async ({ page, request }) => {
    await busy(request);
    await selectRequest(page, "Dongguan");
    await page.getByTestId("accept-review-open").click();
    await expect(page.getByTestId("accept-review")).toBeVisible();
    await expect(page.getByTestId("accept-decline-confirm")).toHaveCount(0);
    await page.getByTestId("accept-decline").click();
    const confirm = page.getByTestId("accept-decline-confirm");
    await expect(confirm).toContainText("Nothing moves; the request closes.");
    await expect(page.getByTestId("accept-decline-go")).toBeFocused();
    // Escape takes the question back and leaves the review as it was.
    await page.keyboard.press("Escape");
    await expect(confirm).toHaveCount(0);
    await expect(page.getByTestId("deal-pane")).toBeVisible();
    await page.getByTestId("accept-decline").click();
    await page.getByTestId("accept-decline-go").click();
    await expect(page.getByTestId("deal-pane")).toHaveAttribute("data-state", "DECLINED");
    await expect(page.getByTestId("deal-state-chip")).toContainText(/declined/i);
    await expect(page.getByTestId("deal-record")).toBeVisible();
    await expect(page.getByTestId("accept-go")).toHaveCount(0);
    await page.goto("/deals?tab=needs_you");
    await expect(page.locator('[data-testid="queue-row"]').filter({ hasText: "Dongguan" }).filter({ hasText: /rebate/ })).toHaveCount(0);
  });

  for (const width of [1440, 390] as const) {
    test(`at ${width} the receipt precedes the commit button, and ?review=1 opens the review on arrival`, async ({ page, request }) => {
      await busy(request);
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      await page.goto("/deals?tab=needs_you");
      const row = page.locator('[data-testid="queue-row"][data-lifecycle="owner_review"]').filter({ hasText: "Zhuhai" });
      await expect(row).toBeVisible();
      await page.goto(`/deals?decision=${encodeURIComponent("deal:" + (await offerOfRow(request, "Zhuhai")))}&review=1`);
      await expect(page.getByTestId("accept-review")).toBeVisible();
      await expect(page.getByTestId("accept-go")).toBeEnabled();
      await receiptBeforeButton(page);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    });
  }

  test("Home's selected deal card and the Customer page lead to the Deals pane with the review open on arrival, and the queue row says the server's own consequence", async ({ page, request }) => {
    await busy(request);
    const offer = await offerOfRow(request, "Zhuhai");
    const decision = `deal:${offer}`;
    // The queue row's consequence is the server's sentence for it, word for word.
    const deals = await request.get(`${API()}/deals?lang=en`, { headers });
    const served = ((await deals.json()) as { queue: { needs_you: { decision_id?: string | null; consequence_text: string }[] } }).queue.needs_you.find((r) => r.decision_id === decision)!.consequence_text;
    await page.goto("/deals?tab=needs_you");
    await expect(page.locator('[data-testid="queue-row"]').filter({ hasText: "Zhuhai" }).getByTestId("queue-consequence")).toContainText(served);
    // Customer page: the primary decision block's one button.
    await page.goto(`/customers/BUYER-3?decision=${encodeURIComponent(decision)}`);
    const primary = page.getByTestId("customer-decision-primary");
    await expect(primary).toHaveText("Review the request");
    await expect(primary).toHaveAttribute("href", /review=1/);
    await primary.click();
    await expect(page.getByTestId("accept-review")).toBeVisible();
    await expect(page.getByTestId("accept-go")).toBeEnabled();
    // Home: the selected deal card's primary.
    await page.goto(`/?customer=BUYER-3&decision=${encodeURIComponent(decision)}`);
    const card = page.getByTestId("deal-primary");
    await expect(card).toHaveText("Review the request");
    await expect(card).toHaveAttribute("href", /review=1/);
    await card.click();
    await expect(page.getByTestId("accept-review")).toBeVisible();
  });

  test("a refusal (the books moved) is said in the server's own words in place, with no spinner, and nothing was accepted", async ({ page, request }) => {
    await busy(request);
    await selectRequest(page, "Zhuhai");
    await page.getByTestId("accept-review-open").click();
    await expect(page.getByTestId("accept-go")).toBeEnabled();
    // The books move under the open review (a day passes), so what the owner was shown is stale.
    const moved = await request.post(`${API()}/clock/advance`, { headers, data: { days: 1 } });
    expect(moved.ok()).toBeTruthy();
    await page.getByTestId("accept-go").click();
    const refused = page.getByTestId("accept-refused");
    await expect(refused).toBeVisible();
    expect(((await refused.textContent()) ?? "").trim().length).toBeGreaterThan(10);
    await expect(refused).toHaveAttribute("data-code", /COUNTER_CHANGED|OFFER_LAPSED|OVER_MANDATE/);
    await expect(page.getByTestId("accept-go").locator(".spinner")).toHaveCount(0);
    await expect(page.getByTestId("deal-accepted")).toHaveCount(0);
  });
});

/** The offer id of a customer's request needing review, from the deals read (a deep link needs it). */
async function offerOfRow(request: APIRequestContext, customer: string): Promise<string> {
  const res = await request.get(`${API()}/deals?lang=en`, { headers });
  expect(res.ok()).toBeTruthy();
  const body = (await res.json()) as { queue: { needs_you: { decision_id?: string | null; subject_text: string; lifecycle?: string | null }[] } };
  const row = body.queue.needs_you.find((r) => r.lifecycle === "owner_review" && r.subject_text.includes(customer));
  expect(row?.decision_id, `${customer}'s request in the queue`).toBeTruthy();
  return row!.decision_id!.replace(/^deal:/, "");
}
