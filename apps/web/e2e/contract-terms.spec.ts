import type { Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { resetBooks } from "./helpers";

/**
 * ADR-0014, "Set up these terms in your books": a confirmed customer contract can add that customer's repeating invoices to the books, as a
 * step of its own after confirming, with the forecast before and after and the owner's confirmation; and the set-up can be undone. The demo's
 * supply agreement is already in the books (mock and live). A new customer's contract, read from a file, is set up and undone against the
 * live API (the mock reads only the three demo documents), whose test server runs with FEATURE_CONTRACT_TERMS=1.
 */

const API_PORT = process.env.E2E_API_PORT ?? "8000";
const API = `http://localhost:${API_PORT}`;
const DGOS = readFileSync(join(__dirname, "..", "..", "..", "fixtures", "contract_terms", "dgos-2026-09-supply-agreement.md"));

test.beforeEach(async ({ request }) => {
  await resetBooks(request);
});

/** Presses the dialog's confirm once it takes a click (it waits a moment after opening, so a double click never lands on it). */
async function confirmDialog(page: Page, yes: string) {
  const dialog = page.getByTestId("terms-dialog");
  await expect(dialog).toBeVisible();
  const button = dialog.getByTestId("terms-dialog-yes");
  await expect(button).toHaveText(yes);
  await expect(button).not.toHaveAttribute("aria-disabled", "true");
  await button.click();
  await expect(dialog).toBeHidden();
}

test("the demo's supply agreement is already in the books: one quiet line, nothing to set up", async ({ page }) => {
  await page.goto("/documents?id=DOC-000001");
  const step = page.getByTestId("terms-step");
  await expect(step).toHaveAttribute("data-status", "ALREADY");
  await expect(step).toContainText("Set up these terms in your books");
  await expect(step).toContainText("Already in your books: they expect these invoices from Foshan Home Retail Co.");
  await expect(step.getByTestId("terms-set-up")).toHaveCount(0);
});

test("a lender agreement has no such step: a contract sets up only a customer's invoices", async ({ page }) => {
  await page.goto("/documents?id=DOC-000002");
  await expect(page.getByTestId("doc-review")).toHaveAttribute("data-kind", "LENDER_AGREEMENT");
  await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "CONFIRMED");
  await expect(page.getByTestId("terms-step")).toHaveCount(0);
});

test.describe("against the live API", () => {
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "live", "a new customer's contract is read by the live server; the mock reads only the demo documents");
  });

  /** The owner reads Dongguan's contract from a file and confirms the reading: the set-up step appears under the decision. */
  async function confirmDongguan(page: Page) {
    await page.goto("/documents");
    const form = page.locator("#docs-read");
    // The companies on the books load with the page: choose the file only once the name typed is one of them.
    await form.getByTestId("doc-counterparty").click();
    await expect(form.getByTestId("doc-counterparty-list").getByRole("option", { name: "Dongguan Office Supplies Ltd." })).toHaveCount(1);
    await form.getByTestId("doc-counterparty").fill("Dongguan Office Supplies Ltd.");
    await expect(form.getByTestId("doc-counterparty")).not.toHaveAttribute("aria-invalid", "true");
    await form.locator('input[type="file"]').setInputFiles({ name: "dgos-supply-agreement.md", mimeType: "text/plain", buffer: DGOS });
    const review = page.getByTestId("doc-review");
    await expect(review).toHaveAttribute("data-status", "PROPOSED");
    // Not before confirming: the set-up is a separate step on a confirmed contract, never part of the confirmation.
    await expect(page.getByTestId("terms-step")).toHaveCount(0);
    await page.getByTestId("doc-confirm").click();
    await expect(page.getByTestId("doc-result")).toHaveAttribute("data-status", "EXECUTED");
    await expect(page.getByTestId("doc-result")).toContainText("Your books and forecast are unchanged.");
    return page.getByTestId("terms-step");
  }

  test("a new customer's contract: the terms beside their clauses, the forecast before and after, set up on confirmation, then undone", async ({ page }) => {
    const step = await confirmDongguan(page);
    await expect(step).toHaveAttribute("data-status", "READY");
    await expect(step).toContainText("Your books do not expect these invoices from Dongguan Office Supplies Ltd. yet.");
    await expect(step.getByTestId("terms-row-PRICE")).toContainText("¥180,000.00");
    await expect(step.getByTestId("terms-row-PRICE")).toContainText("The Buyer shall pay the Supplier RMB 180,000");
    await expect(step.getByTestId("terms-row-INVOICING")).toContainText("30 days");
    await expect(step.getByTestId("terms-row-NEXT_INVOICE")).toContainText("15 Oct 2026");
    await expect(step.getByTestId("terms-row-PAYMENT_TERMS")).toContainText("45 days of the invoice date");
    const forecast = step.getByTestId("terms-forecast");
    await expect(forecast.locator('tr[data-key="customer"]')).toContainText("none");
    await expect(forecast.locator('tr[data-key="customer"]')).toContainText("¥540,000.00 from 3 invoices");
    await expect(forecast.locator('tr[data-key="end"]')).toContainText("¥1,340,000.00");
    await expect(forecast.locator('tr[data-key="end"]')).toContainText("¥1,880,000.00");
    // CT-2: the set-up's invoices count once the clock has issued the first one, and the step says so.
    await expect(forecast.locator("thead")).toContainText("Once the first invoice is issued");
    await expect(step.getByTestId("terms-forecast-text")).toContainText("once the first one is issued, on 15 Oct 2026");
    await expect(step.getByTestId("terms-not-set-up")).toContainText("Early payment");

    // The owner presses, reads the confirmation, and can still say no: nothing changes.
    await step.getByTestId("terms-set-up").click();
    await expect(page.getByTestId("terms-dialog")).toContainText("Your forecast will count on this money arriving on time.");
    await page.getByTestId("terms-dialog-no").click();
    await expect(page.getByTestId("terms-dialog")).toBeHidden();
    await expect(step).toHaveAttribute("data-status", "READY");

    await step.getByTestId("terms-set-up").click();
    await confirmDialog(page, "Yes, set them up");
    const result = step.getByTestId("terms-result");
    await expect(result).toHaveAttribute("data-status", "EXECUTED");
    await expect(result).toContainText("Set up: your books now expect Dongguan Office Supplies Ltd. to pay an invoice of ¥180,000.00 every 30 days");
    await expect(step).toHaveAttribute("data-status", "SET_UP");
    await expect(step.getByTestId("terms-set-up-text")).toContainText("¥180,000.00 every 30 days, paid in 45 days.");

    // Reloaded, the books say the same: the set-up is in force.
    await page.reload();
    await expect(page.getByTestId("terms-step")).toHaveAttribute("data-status", "SET_UP");

    // Activity logs it in the owner's words.
    await page.goto("/activity");
    await expect(page.getByTestId("activity-list")).toContainText("Contract terms set up");

    // Undo: the books no longer expect the invoices, and the step offers the set-up again.
    await page.goBack();
    const again = page.getByTestId("terms-step");
    await again.getByTestId("terms-undo").click();
    await confirmDialog(page, "Yes, undo it");
    await expect(again.getByTestId("terms-result")).toContainText("Undone: your books no longer expect Dongguan Office Supplies Ltd.'s repeating invoices");
    await expect(again).toHaveAttribute("data-status", "READY");
  });

  test("Chinese: the step is in the owner's language", async ({ page }) => {
    await confirmDongguan(page);
    await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
    await page.reload();
    const step = page.getByTestId("terms-step");
    await expect(step).toContainText("将这些条款记入账簿");
    await expect(step.getByTestId("terms-set-up")).toHaveText("记入我的账簿");
  });

  test("the agent key and a buyer's key reach none of it", async ({ page, request }) => {
    await confirmDongguan(page);
    const id = new URL(page.url()).searchParams.get("id");
    const owner = await request.get(`${API}/documents/${id}/terms`, { headers: { "X-Owner-Token": DEMO_TOKEN } });
    const view = (await owner.json()).terms;
    const others: Record<string, string>[] = [{ "X-Agent-Key": "demo-agent-key" }, { "X-Counterparty-Key": "demo-buyer-2-key" }];
    for (const headers of others) {
      expect((await request.get(`${API}/documents/${id}/terms`, { headers })).status()).toBe(401);
      const post = await request.post(`${API}/documents/${id}/terms`, { headers, data: { doc_hash: view.doc_hash, terms_hash: view.terms_hash } });
      expect(post.status()).toBe(401);
    }
    // Built by hand and sent through the agent's operations channel, the operation is refused before it is queued.
    const op = {
      kind: "SET_UP_CONTRACT_TERMS", op_id: "e2e-agent", idempotency_key: "e2e-agent", mandate_version: 1, requested_by: "AGENT", day: 0,
      document_id: id, doc_hash: view.doc_hash, terms_hash: view.terms_hash, counterparty_id: "BUYER-2", face_fen: 18000000, every_days: 30,
      next_issue_day: 14, terms_days: 45,
    };
    const refused = (await (await request.post(`${API}/operations`, { headers: { "X-Agent-Key": "demo-agent-key" }, data: op })).json()).result;
    expect(refused.status).toBe("REFUSED");
    expect(refused.approval_id).toBeNull();
    await page.reload();
    await expect(page.getByTestId("terms-step")).toHaveAttribute("data-status", "READY");
  });
});
