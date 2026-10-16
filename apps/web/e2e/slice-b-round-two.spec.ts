import { DEMO_TOKEN, expect, test } from "./fixtures";
import picture from "../mocks/offer_picture_ex01.json";
import { checkedDeal, openOperatorTools, resetBooks } from "./helpers";

/** The recommended reply's words as the server wrote them (the mandate's words, round four). */
const optionA = picture.en.paths.find((p) => p.kind === "reply" && p.recommended)!;

/**
 * Slice B round two (docs/design/flow-mockup-2026-10-13/04_slice_b_round_two.md): the Deals queue's controls, the workspace's timing diagram and its two switchable cards, the Customer page's flow,
 * its links and the share bar, and Approvals' lifecycle. The mock project runs on the API's recordings; the live project on a real API and the busy books. Every string is the server's, read from the page.
 */

const live = (info: { project: { name: string } }) => info.project.name === "live";

test.describe("mock", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(live(testInfo), "mock-mode: the recorded reads");
  });

  test("the choices table's Terms row says each choice's terms by scope in the server's words; the payment-period bars, the timing diagram and the separate terms table are gone from the Overview", async ({ page }) => {
    await checkedDeal(page);
    const terms = page.getByTestId("deal-choice-row-terms");
    await expect(terms).toBeVisible();
    await expect(terms.getByTestId("deal-choice-cell-terms-asked")).toContainText("Future invoices");
    await expect(terms.getByTestId("deal-choice-cell-terms-asked")).toContainText("60 days");
    await expect(terms.getByTestId("deal-choice-cell-terms-reply").first()).toContainText("45 days");
    await expect(terms.getByTestId("deal-choice-cell-terms-reply").nth(1)).toContainText("55 days");
    await expect(page.getByTestId("deal-choices-table").locator("thead th").filter({ hasText: /\S/ }).nth(1)).toContainText("Option A");
    for (const gone of ["deal-timing", "deal-scope-terms", "deal-scope-terms-bar-current"]) await expect(page.getByTestId(gone)).toHaveCount(0);
  });

  test("the choices table's cost and lowest-cash cells say each choice's figures in the server's words, and Escape clears the selection (there is no rail to bring back)", async ({ page }) => {
    await checkedDeal(page);
    await expect(page.getByTestId("deal-choice-cell-cost-asked")).toContainText("¥28,326.92");
    await expect(page.getByTestId("deal-choice-cell-cost-reply").first()).toContainText("¥3,035.99");
    await expect(page.getByTestId("deal-choice-cell-lowest-reply").first()).toContainText("¥300k");
    await expect(page.getByTestId("deal-choice-cell-lowest-asked")).toContainText("¥165k");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("deal-pane")).toHaveCount(0);
    await expect(page.getByTestId("deals-queue")).toBeVisible();
  });

  test("a deep link keeps the section: Cash impact opens on Cash impact with its two charts, and an address that still names Compare responses lands on the Overview", async ({ page }) => {
    await checkedDeal(page);
    const here = `${new URL(page.url()).pathname}${new URL(page.url()).search}`;
    await page.goto(`${here}&view=cash`);
    await expect(page.getByTestId("deal-tab-cash")).toHaveAttribute("aria-current", "page");
    await expect(page.getByTestId("deal-chart")).toBeVisible();
    await expect(page.getByTestId("deal-why-lines")).toContainText("Why the lines differ");
    await page.goto(`${here}&view=compare`);
    await expect(page.getByTestId("deal-choices")).toBeVisible();
    await expect(page).not.toHaveURL(/view=compare/);
  });

  test("the queue's controls: sort and grouping are offered only as the queue grows (four and six negotiations; the busy books in the live describe below pin them), and one row shows none", async ({ page }) => {
    await checkedDeal(page);
    await expect(page.getByTestId("queue-sort-urgency")).toHaveCount(0);
    await expect(page.getByTestId("queue-group")).toHaveCount(0);
    await expect(page.getByTestId("queue-row").first()).toHaveAttribute("data-selected", "true");
  });

  test("Customer: the share figure has its bar, the flow's steps and chips lead to the invoice and the money, and the exposure is a table", async ({ page }) => {
    await checkedDeal(page);
    await page.goto("/customers/BUYER-1");
    await expect(page.getByTestId("customer-figure-share-bar")).toBeVisible();
    const flow = page.getByTestId("customer-flow");
    expect(await flow.getByTestId("customer-flow-steps").locator("li").count()).toBeGreaterThanOrEqual(2);
    await expect(flow.getByTestId("customer-flow-step-owed")).toContainText("Foshan owes you");
    await expect(flow.getByTestId("customer-flow-step-link-owed")).toHaveAttribute("href", /\/receivables\?/);
    const chips = flow.getByTestId("customer-flow-links").getByRole("link");
    expect(await chips.count()).toBeGreaterThanOrEqual(2);
    await expect(page.getByTestId("customer-exposure-table")).toBeVisible();
  });

  test("a picked reply is reviewed from its own column, and \"FLOW recommends\" stays with the recommended reply only", async ({ page }) => {
    await checkedDeal(page);
    await page.goto(`${new URL(page.url()).pathname}${new URL(page.url()).search}&path=CTR-6b07cbf70441`);
    const heads = page.locator('[data-testid="deal-choice-head-reply"]:visible');
    await expect(heads.first()).toHaveAttribute("data-recommended", "true");
    await expect(heads.nth(1)).not.toHaveAttribute("data-recommended", "true");
    // The Overview still says the recommended reply's authority in the short word, Option A's column alone.
    await expect(page.getByTestId("deal-choice-cell-decides-reply").first()).toContainText(optionA.authority_short_text!);
    await expect(page.getByTestId("deal-recommends-title")).toHaveText("FLOW recommends");
    await expect(page.getByTestId("deal-rec-label")).toHaveText("Option A");
    await expect(page.getByTestId("deal-rec-reason")).toHaveText(optionA.recommended_reason_text!);
  });

  test("Approvals: the lifecycle shows three stages, the first current while the owner has not authorized, and the button names the act", async ({ page }) => {
    await page.goto("/demo");
    await openOperatorTools(page); // the optional scenes sit in the Demo's operator tools fold
    await page.getByTestId("more-run-capex").click();
    await page.getByTestId("capex-apply").click();
    await expect(page.getByTestId("capex-applied")).toBeVisible();
    await page.goto("/approvals");
    const stages = page.getByTestId("approval-stage");
    await expect(stages).toHaveCount(3);
    await expect(stages.nth(0)).toHaveAttribute("data-state", "current");
    await expect(stages.nth(1)).toHaveAttribute("data-state", "next");
    await expect(stages.nth(2)).toHaveAttribute("data-state", "next");
    await expect(page.getByTestId("approval-approve-APR-000001")).toHaveText("Authorize the application");
    // Once authorized the decided row keeps the stages: You authorize is done, the lender's is next to happen.
    await page.getByTestId("approval-approve-APR-000001").click();
    const decided = page.getByTestId("approvals-decided").getByTestId("approval-stage");
    await expect(decided).toHaveCount(3);
    await expect(decided.nth(0)).toHaveAttribute("data-state", "done");
    await expect(decided.nth(1)).toHaveAttribute("data-state", "current");
    await expect(decided.nth(2)).toHaveAttribute("data-state", "next");
  });
});

test.describe("live", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(!live(testInfo), "live-mode: a real API and the busy books");
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

  test("the busy queue: distinct subjects, lifecycle words, sort by latest activity and grouping by customer", async ({ page, request }) => {
    await busy(request);
    await page.goto("/deals");
    await expect(page.getByTestId("queue-row")).toHaveCount(6);
    const subjects = await page.getByTestId("queue-subject").allTextContents();
    expect(new Set(subjects).size, "every negotiation has its own subject").toBe(subjects.length);
    for (const word of ["Owner review needed", "Counter ready", "More information needed"]) await expect(page.getByTestId("queue-status").filter({ hasText: word }).first()).toBeVisible();
    await expect(page.locator("main")).not.toContainText(/OFF-|RCV-|\bDay \d/);
    await expect(page.getByTestId("queue-sort-latest")).toBeEnabled();
    await page.getByTestId("queue-sort-latest").click();
    await expect(page.getByTestId("queue-activity").first()).toBeVisible();
    await page.getByTestId("queue-group").click();
    const headings = (await page.getByTestId("queue-group-heading").allTextContents()).map((h) => h.replace(/\s*\(\d+\)$/, ""));
    expect(headings.length, "three customers").toBe(3);
    expect(headings.some((h) => h.startsWith("Foshan"))).toBe(true);
    // Demo mode may show the offer's id; Business never does.
    await page.evaluate(() => localStorage.setItem("tl-mode", JSON.stringify({ mode: "demo" })));
    await page.reload();
    await expect(page.getByTestId("queue-subject").first()).toContainText(/OFF-/);
  });

  test("Foshan's EX01 on the busy books: the comparison says the request breaches the reserve, the terms say the difference of the period, and the customer page leads with the selected negotiation", async ({ page, request }) => {
    await busy(request);
    await page.goto("/deals");
    await page.getByTestId("queue-row").filter({ hasText: "60-day terms" }).getByTestId("queue-select").click();
    // The request breaches the reserve: its cash outcome says so in the comparison; the terms say the difference of the period.
    await expect(page.getByTestId("deal-choice-cell-terms-asked")).toContainText("days", { timeout: 45_000 });
    await expect(page.getByTestId("deal-choice-cell-lowest-asked")).toContainText(/Breached by/);
    // The choices table is the Overview (the redesign): the Overview link shows only from another section.
    if (await page.getByTestId("deal-tab-overview").count()) await page.getByTestId("deal-tab-overview").click();
    await page.getByTestId("deal-selected-customer").click();
    await expect(page.getByTestId("customer-relationship")).toContainText("Foshan contributes an estimated");
    await expect(page.getByTestId("customer-decision-heading")).toContainText("60-day terms");
    await expect(page.getByTestId("customer-others")).toContainText("Other open negotiations (3)");
    await expect(page.getByTestId("customer-flow-links").getByRole("link").first()).toBeVisible();
  });

  test("authorizing on the busy books leaves the three stages on the decided row, the first done", async ({ page, request }) => {
    await busy(request);
    await page.goto("/approvals");
    await page.locator('[data-testid^="approval-approve-"]').first().click();
    const decided = page.getByTestId("approvals-decided").getByTestId("approval-stage");
    await expect(decided).toHaveCount(3);
    await expect(decided.nth(0)).toHaveAttribute("data-state", "done");
    await expect(decided.nth(1)).toHaveAttribute("data-state", "current");
    await expect(decided.nth(2)).toHaveAttribute("data-state", "next");
  });

  test("the flow's financing link lands on the facility it names on Cash: the element has the id, opens and takes focus", async ({ page, request }) => {
    await busy(request);
    await page.goto("/customers/BUYER-1");
    const link = page.locator('[data-testid^="customer-flow-step-link-"]').filter({ hasText: /financing/i }).first();
    const href = await link.getAttribute("href");
    expect(href).toMatch(/^\/cash#facility-/);
    await link.click();
    await expect(page).toHaveURL(/\/cash#facility-/);
    const id = new URL(page.url()).hash.slice(1);
    const fold = page.locator(`#${id}`);
    await expect(fold).toBeVisible();
    await expect(fold).toHaveAttribute("open", "");
    await expect(fold.locator("summary")).toBeFocused();
  });
});
