import type { Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "./fixtures";
import { resetBooks } from "./helpers";

/**
 * Contract ingestion (brief 03): the home cards and the confirm flow. The demo opens on the three demo documents read by the
 * agent and confirmed by the owner (the first three ledger entries), so the home page shows the deal at once, as in the
 * prototype. Reading a demo document again is a new reading the owner reviews beside the text and confirms or rejects. The
 * same walk runs in mock mode (answers recorded from the live API) and in the live project (a fresh in-memory API). The
 * day-34 deal and the Chinese screens are mock-only (the live equivalent needs the whole demo path first).
 */

const SUPPLY = "FHR_SUPPLY_AGREEMENT";
const LINE = "MB_CREDIT_LINE_AGREEMENT";
const INVOICE_FINANCING = "GBR_INVOICE_FINANCING_AGREEMENT";

test.beforeEach(async ({ request }) => {
  await resetBooks(request);
});

/** Reads a demo document again: a new reading (DOC-000004 on fresh demo books), waiting for the owner. */
async function readAgain(page: Page, fixtureId: string, format?: "md" | "docx" | "pdf") {
  await page.goto("/documents");
  const row = page.getByTestId(`fixture-${fixtureId}`);
  if (format) await row.getByLabel("Format").selectOption(format);
  await row.getByTestId(`fixture-read-${fixtureId}`).click();
  await expect(page).toHaveURL(/\/documents\?id=DOC-000004$/);
  const review = page.getByTestId("doc-review");
  await expect(review).toHaveAttribute("data-status", "PROPOSED");
  return review;
}

test("home: the demo opens on the deal card and the three documents the agent read and the owner confirmed", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your deals", level: 2 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Documents the agent has read", level: 2 })).toBeVisible();
  // The cards come after Position, as the prototype places them.
  const order = await page.locator("main h2").allTextContents();
  expect(order.indexOf("Your deals")).toBe(order.indexOf("Position") + 1);
  expect(order.indexOf("Documents the agent has read")).toBe(order.indexOf("Position") + 2);

  const deal = page.getByTestId("home-deal-BUYER-1");
  await expect(deal).toHaveAttribute("data-has-contract", "true");
  await expect(deal).toContainText("Supply agreement FHR-2026-07 · signed 1 Sep 2026 · 12 months · an invoice every 30 days");
  await expect(deal.getByTestId("deal-pills")).toHaveText("On track");
  await expect(deal.getByTestId("deal-stages").locator("li")).toHaveCount(5);
  const contract = deal.getByTestId("deal-contract");
  await expect(contract).toContainText("Read by the agent, confirmed by you");
  await expect(contract).toContainText("¥420,000.00 per delivery batch");
  await expect(contract).toContainText("45 days from the invoice date");
  await expect(contract).toContainText("§4.2");
  await expect(deal.getByTestId("deal-blanks")).toContainText("Late-payment interest");
  await expect(deal.getByTestId("deal-invoice-RCV-A")).toContainText("¥420,000.00");
  await expect(deal.getByTestId("deal-owed")).toContainText("a quality inspection certificate for the Batch");
  await expect(deal.getByTestId("deal-checks").locator("li")).toHaveCount(5);
  await expect(deal.getByTestId("deal-next")).toContainText("Nothing needs you on this deal today.");
  await expect(page.getByTestId("home-deal-BUYER-2")).toContainText("No contract confirmed yet.");

  const docs = page.getByTestId("home-docs-list").locator("li");
  await expect(docs).toHaveCount(3);
  for (const title of ["Supply agreement FHR-2026-07", "Credit line agreement MB-CL-2026-031", "Invoice financing agreement GBR-IF-2026-118"]) {
    await expect(docs.filter({ hasText: title })).toContainText("Confirmed day 0");
  }
});

test("the review screen: the confirmed supply agreement, every term beside the clause it came from", async ({ page }) => {
  await page.goto("/documents");
  await page.getByTestId(`fixture-open-${SUPPLY}`).click();
  await expect(page).toHaveURL(/\/documents\?id=DOC-000001$/);
  const review = page.getByTestId("doc-review");
  await expect(review).toHaveAttribute("data-status", "CONFIRMED");
  await expect(review.getByTestId("doc-ai-label")).toHaveText("Read by the agent, confirmed by you");
  await expect(page.getByTestId("doc-decided")).toContainText("Decided on day 0 (ledger entry #1)");
  await expect(page.getByTestId("doc-confirm")).toHaveCount(0);
  // Every term the agent read, each with its exact words; the three it could not find are left blank, with why.
  const terms = page.getByTestId("doc-terms");
  await expect(terms.locator(":scope > li")).toHaveCount(18);
  const price = terms.locator("li", { hasText: "¥420,000.00 per delivery batch" });
  await expect(price).toContainText("§3.1");
  await expect(price).toContainText("RMB 420,000");
  await expect(terms).toContainText("Every 30 days, the first on 3 Oct 2026 (day 2)");
  await expect(page.getByTestId("doc-blanks")).toContainText("Retention");
  // Focusing a term highlights its clause in the document.
  const id = (await price.getAttribute("data-testid"))!.replace("doc-item-", "");
  await price.focus();
  const mark = page.getByRole("group", { name: "Document text with the clauses the agent read highlighted" }).locator(`mark[data-annotation~="${id}"]`).first();
  await expect(mark).toContainText("RMB 420,000");
  await expect(mark).toHaveClass(/ring-2/);
});

test("the confirm flow: a new reading is labelled AI-generated until the owner confirms it, and the ledger logs it", async ({ page }) => {
  const review = await readAgain(page, SUPPLY);
  await expect(review.getByTestId("doc-ai-label")).toHaveText("AI-generated, for reference");
  await expect(page.getByTestId("doc-terms").locator(":scope > li")).toHaveCount(18);
  await page.getByTestId("doc-confirm").click();
  const result = page.getByTestId("doc-result");
  await expect(result).toHaveAttribute("data-status", "EXECUTED");
  await expect(result).toContainText("Confirm document");
  await expect(result).toContainText("nothing in the books changed");
  await expect(review).toHaveAttribute("data-status", "CONFIRMED");
  await expect(review.getByTestId("doc-ai-label")).toHaveText("Read by the agent, confirmed by you");
  await expect(page.getByTestId("doc-decided")).toContainText("Decided on day 0 (ledger entry #4)");

  // Home: the deal follows the reading confirmed last; the documents card lists the new reading too.
  await page.getByRole("navigation").getByRole("link", { name: "Home", exact: true }).first().click();
  const deal = page.getByTestId("home-deal-BUYER-1");
  await expect(deal).toHaveAttribute("data-has-contract", "true");
  await expect(deal.getByTestId("deal-contract")).toContainText("45 days from the invoice date");
  const docs = page.getByTestId("home-docs-list").locator("li");
  await expect(docs).toHaveCount(4);
  await expect(page.getByTestId("home-doc-DOC-000004")).toHaveAttribute("data-status", "CONFIRMED");

  // The ledger holds the owner's four confirmations, on the hash chain with everything else.
  await page.goto("/ledger");
  await expect(page.locator("#operations tbody tr").filter({ hasText: "Confirm document" })).toHaveCount(4);
});

test("a lender agreement (the PDF copy) is compared with the facility on the books and linked when confirmed", async ({ page }) => {
  const review = await readAgain(page, INVOICE_FINANCING, "pdf");
  await expect(review).toHaveAttribute("data-kind", "LENDER_AGREEMENT");
  await expect(review.getByTestId("doc-ai-label")).toHaveText("AI-generated, for reference");
  await expect(page.getByTestId("doc-terms")).toContainText("Advance rate");
  const compare = page.getByTestId("doc-compare");
  await expect(compare).toContainText("This agreement against FAC-IF on your books");
  await expect(compare.locator("tbody tr")).toHaveCount(9);
  await expect(compare.locator('tbody tr[data-same="false"]')).toHaveCount(0);
  await expect(page.locator("#doc-facility")).toContainText("All-in rate 10.84%");
  await expect(page.getByTestId("doc-link")).toBeChecked();
  await expect(page.locator("#doc-decide")).toContainText("Link to FAC-IF on your books");
  await page.getByTestId("doc-confirm").click();
  await expect(page.getByTestId("doc-result")).toHaveAttribute("data-status", "EXECUTED");
  await expect(review).toHaveAttribute("data-status", "CONFIRMED");
});

test("reject: a new reading is set aside and logged; the agreement already confirmed stays", async ({ page }) => {
  const review = await readAgain(page, LINE);
  await expect(page.getByTestId("doc-compare")).toContainText("FAC-LINE");
  await page.getByTestId("doc-reject").click();
  const result = page.getByTestId("doc-result");
  await expect(result).toHaveAttribute("data-status", "EXECUTED");
  await expect(result).toContainText("Reject document");
  await expect(review).toHaveAttribute("data-status", "REJECTED");
  await expect(review.getByTestId("doc-status")).toContainText("Rejected day 0");
  await expect(page.getByTestId("doc-row-DOC-000002")).toHaveAttribute("data-status", "CONFIRMED");
  await expect(page.getByTestId("doc-row-DOC-000004")).toHaveAttribute("data-status", "REJECTED");
});

test("your own file: the upload form sends a Word, PDF or text file with what it is and who it is with", async ({ page }, testInfo) => {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  await form.getByLabel("What it is").selectOption("BUYER_CONTRACT");
  await expect(form.getByLabel("Who it is with")).toHaveValue("BUYER-1");
  const text = readFileSync(join(__dirname, "..", "..", "..", "fixtures", "contracts", "fhr-2026-07-supply-agreement.md"));
  await form.getByLabel(/^File/).setInputFiles({ name: "supply-agreement.md", mimeType: "text/plain", buffer: text });
  await page.getByTestId("doc-upload").click();
  if (testInfo.project.name === "live") {
    // The server reads the upload like any other document: the same text gives the same reading.
    const review = page.getByTestId("doc-review");
    await expect(review).toHaveAttribute("data-status", "PROPOSED");
    await expect(page.getByTestId("doc-terms").locator(":scope > li")).toHaveCount(18);
  } else {
    await expect(form.getByRole("alert")).toContainText("Mock mode reads only the three demo documents");
  }
});

test("day 34: the deal card tells the story and points at the approval", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path (deal, receipt on day 2, clock to day 34)");
  await page.goto("/");
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");

  const deal = page.getByTestId("home-deal-BUYER-1");
  await expect(deal.getByTestId("deal-pills")).toHaveText("Payment overdue");
  await expect(deal.getByTestId("deal-stages").locator('li[data-state="now"]')).toContainText("Collecting");
  const rcvA = deal.getByTestId("deal-invoice-RCV-A");
  await expect(rcvA).toHaveAttribute("data-status", "LATE");
  await expect(rcvA).toContainText("¥162,800.00");
  await expect(rcvA).toContainText("2 days late");
  await expect(deal.getByTestId("deal-changes")).toContainText("¥255,013.80 received on RCV-A");
  await expect(deal.getByTestId("deal-in-force").locator('[data-vs="DIFFERENT"]')).toContainText("0.85%");
  await expect(deal.getByTestId("deal-next")).toContainText("Chase the ¥162,800.00 on RCV-A (2 days late).");

  // The owner lets the agent fix the reserve alert: the cure waits for approval, and the deal card says so.
  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  await expect(deal.getByTestId("deal-pills")).toContainText("1 approval waiting");
  await expect(deal.getByTestId("deal-invoice-RI:BUYER-1:2")).toHaveAttribute("data-status", "ADVANCE_WAITING");
  await expect(deal.getByTestId("deal-next")).toContainText("Review APR-000001");
  await deal.getByRole("link", { name: "Review approval" }).click();
  await expect(page).toHaveURL(/\/approvals/);
});

test("Chinese: the cards and the review screen", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "live", "the strings are the same in both modes; checked once");
  await page.goto("/");
  await page.getByLabel("中文").check();
  await expect(page.getByRole("heading", { name: "您的交易", level: 2 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "代理读过的文件", level: 2 })).toBeVisible();
  await expect(page.getByTestId("home-deal-BUYER-1")).toContainText("合同约定");
  await expect(page.getByTestId("home-docs-list")).toContainText("第 0 天确认");
  await readAgain(page, SUPPLY);
  await expect(page.getByRole("heading", { name: "文件", level: 1 })).toBeVisible();
  await expect(page.getByTestId("doc-ai-label")).toHaveText("由 AI 生成，仅供参考");
  await expect(page.getByTestId("doc-terms")).toContainText("账期");
  await page.getByTestId("doc-confirm").click();
  await expect(page.getByTestId("doc-ai-label")).toHaveText("由代理读取，经您确认");
});
