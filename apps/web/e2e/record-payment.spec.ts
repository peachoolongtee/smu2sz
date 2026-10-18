import type { APIRequestContext, Page } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { resetBooks, runPlan } from "./helpers";
import { en, zh } from "../lib/dictionary";
import receipts from "../mocks/receipts.json";

/**
 * "Record a payment" on the Receivables page (feature inventory gap 1) and the setup wizard's words about what can change after setup (gap 2).
 *
 * Mock mode: every sentence asserted is the recorded answer of the real route (mocks/receipts.json, `record-mocks.mjs --receipts`) or the
 * dictionary's label, never typed here. Live mode: the same flow against the API, where the words are whatever the server writes; the spec
 * checks their meaning (the residual left open, the lender repaid first) and that the books moved.
 */

type Answer = (typeof receipts.day0.answers)[number];
const answer = (point: "day0" | "settled", variant: string): Answer => receipts[point].answers.find((a) => a.variant === variant)! as Answer;
const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
const isLive = () => test.info().project.name === "live";

async function openInvoice(page: Page, id: string) {
  await page.goto(`/receivables?customer=BUYER-1&invoice=${encodeURIComponent(id)}`);
  await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", id);
}

async function openForm(page: Page) {
  await page.getByTestId("recv3-pay-open").click();
  await expect(page.getByTestId("recv3-pay-form")).toBeVisible();
}

async function api(request: APIRequestContext, method: "GET" | "POST", path: string, body?: unknown) {
  const res = method === "GET"
    ? await request.get(`${API}${path}`, { headers: { "X-Owner-Token": DEMO_TOKEN } })
    : await request.post(`${API}${path}`, { headers: { "X-Owner-Token": DEMO_TOKEN }, data: body ?? {} });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

test.describe("record a payment", () => {
  test.beforeEach(async ({ request }) => {
    await resetBooks(request);
  });

  test("the whole amount: the invoice is paid, the server says so and the reconciliation reads it", async ({ page }) => {
    await openInvoice(page, "RCV-A");
    await openForm(page);
    await expect(page.getByTestId("recv3-pay-form")).toContainText(en["recv3.pay.date"]);
    await expect(page.getByTestId("recv3-pay-full")).toBeChecked();
    await page.getByTestId("recv3-pay-ref").fill("BANK-STMT-1");
    await page.getByTestId("recv3-pay-submit").click();
    const result = page.getByTestId("recv3-pay-result");
    await expect(result).toHaveAttribute("data-status", "EXECUTED");
    await expect(page.getByTestId("recv3-pay-form")).toHaveCount(0);
    if (isLive()) {
      await expect(page.getByTestId("recv3-pay-headline")).toContainText("Recorded: ¥420,000.00 received from Foshan Home Retail Co.");
      await expect(result).toContainText("is paid in full.");
    } else {
      const words = answer("day0", "full").answer.en.receipt!;
      await expect(page.getByTestId("recv3-pay-headline")).toHaveText(words.headline_text!);
      await expect(page.getByTestId("recv3-pay-line")).toHaveText(words.lines);
      await expect(page.getByTestId("recv3-pay-recon")).toHaveText(`${en["recv3.pay.recon"]} ${words.reconciliation_text}`);
    }
    // The books were read again: the paid invoice is no longer waiting to be collected.
    await expect(page.getByTestId("recv3-detail")).toHaveCount(0);
    await page.getByTestId("recv3-pay-dismiss").click();
    await expect(result).toHaveCount(0);
  });

  test("part of it: the rest stays open on the invoice", async ({ page }) => {
    await openInvoice(page, "RCV-A");
    await openForm(page);
    await page.getByTestId("recv3-pay-part").check();
    await expect(page.getByTestId("recv3-pay-amount")).toBeFocused();
    // A typed amount that is not one is the dictionary's sentence beside the button; nothing is sent.
    await page.getByTestId("recv3-pay-amount").fill("a lot");
    await page.getByTestId("recv3-pay-submit").click();
    await expect(page.getByTestId("recv3-pay-error")).toHaveText(en["recv3.pay.amount.invalid"]);
    await page.getByTestId("recv3-pay-amount").fill("100,000");
    await page.getByTestId("recv3-pay-submit").click();
    await expect(page.getByTestId("recv3-pay-result")).toHaveAttribute("data-status", "EXECUTED");
    if (isLive()) {
      await expect(page.getByTestId("recv3-pay-line").first()).toHaveText("¥320,000.00 is still open on the ¥420,000.00 invoice to Foshan Home Retail Co., due in 32 days.");
      await expect(page.getByTestId("recv3-pay-recon")).toContainText("Partial payment");
    } else {
      const words = answer("day0", "partial").answer.en.receipt!;
      await expect(page.getByTestId("recv3-pay-line")).toHaveText(words.lines);
      await expect(page.getByTestId("recv3-pay-recon")).toContainText(words.reconciliation_text!);
    }
    // The invoice is read again with what is still owed on it.
    await expect(page.getByTestId("recv3-detail")).toHaveAttribute("data-receivable", "RCV-A");
    await expect(page.getByTestId("recv3-bd-invoice")).toHaveText(isLive() ? "¥320,000.00" : answer("day0", "partial").after!.en.rows[0].outstanding_display);
  });

  test("more than is open: refused beside the button, nothing recorded", async ({ page }) => {
    await openInvoice(page, "RCV-A");
    await openForm(page);
    await page.getByTestId("recv3-pay-part").check();
    await page.getByTestId("recv3-pay-amount").fill("500000");
    await page.getByTestId("recv3-pay-submit").click();
    const error = page.getByTestId("recv3-pay-error");
    const words = answer("day0", "too_much").answer.en.receipt!;
    await expect(error).toContainText(words.headline_text!);
    await expect(error).toContainText(words.lines[0]);
    await expect(page.getByTestId("recv3-pay-result")).toHaveCount(0);
    await expect(page.getByTestId("recv3-pay-form")).toBeVisible();
    await expect(page.getByTestId("recv3-bd-invoice")).toHaveText("¥420,000.00");
  });

  test("a financed invoice: the receipt repays the lender first", async ({ page, request }) => {
    if (isLive()) {
      // The day-0 plan finances the invoice; its advance lands on day 3 and is settled once that day has closed. The owner's receipt then repays the lender first.
      await page.goto("/cash");
      const alerts = await api(request, "GET", "/alerts");
      await runPlan(page, alerts.alerts.find((a: { id: string; actionable: boolean }) => a.id.startsWith("ALERT-RESERVE") && a.actionable).id);
      await expect.poll(async () => ((await api(request, "GET", "/state")).state.lots ?? []).length).toBeGreaterThan(0);
      await api(request, "POST", "/clock/advance", { to_day: 5 });
      await openInvoice(page, "RCV-A");
    } else {
      await page.addInitScript(() => sessionStorage.setItem("tl-mock-home-v4", JSON.stringify({ day: 38, stage: "approved", funded: false, receipted: true, moved: 0 })));
      await openInvoice(page, receipts.settled.receivable_id);
    }
    await openForm(page);
    await page.getByTestId("recv3-pay-submit").click();
    await expect(page.getByTestId("recv3-pay-result")).toHaveAttribute("data-status", "EXECUTED");
    if (isLive()) {
      await expect(page.getByTestId("recv3-pay-line").first()).toContainText("went to Invoice financing (onboarded platform) first, to repay the advance on this invoice");
      const state = (await api(request, "GET", "/state")).state;
      expect(state.receivables.find((r: { id: string }) => r.id === "RCV-A").status).toBe("SETTLED");
    } else {
      await expect(page.getByTestId("recv3-pay-line")).toHaveText(answer("settled", "full").answer.en.receipt!.lines);
    }
  });

  test("in Chinese: the labels are the dictionary's and the answer is the server's Chinese", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
    await openInvoice(page, "RCV-A");
    await expect(page.getByTestId("recv3-pay-open")).toHaveText(zh["recv3.pay.button"]);
    await openForm(page);
    await page.getByTestId("recv3-pay-submit").click();
    const words = answer("day0", "full").answer.zh.receipt!;
    await expect(page.getByTestId("recv3-pay-headline")).toHaveText(words.headline_text!);
    await expect(page.getByTestId("recv3-pay-recon")).toHaveText(`${zh["recv3.pay.recon"]} ${words.reconciliation_text}`);
  });

  test("on a phone the form fits the screen and its buttons are a finger wide", async ({ page }) => {
    test.skip(isLive(), "layout: the mock is enough");
    await page.setViewportSize({ width: 390, height: 844 });
    await openInvoice(page, "RCV-A");
    await openForm(page);
    await page.getByTestId("recv3-pay-part").check();
    const form = await page.getByTestId("recv3-pay-form").boundingBox();
    expect(form && form.x >= 0 && form.x + form.width <= 390).toBeTruthy();
    for (const id of ["recv3-pay-submit", "recv3-pay-cancel", "recv3-pay-open"]) {
      expect((await page.getByTestId(id).boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
});

test.describe("setup: no promise of a feature that does not exist", () => {
  test("bills and limits say how they change after setup, in English and Chinese", async ({ page }) => {
    await page.goto("/setup?step=4");
    await expect(page.getByTestId("setup-s4-foot")).toHaveText(en["setup.s4.foot"]);
    await expect(page.getByTestId("setup-s4-foot")).not.toContainText("any time after setup");
    await page.goto("/setup?step=5");
    await expect(page.getByTestId("setup-s5-foot")).toHaveText(en["setup.s5.foot"]);
    await expect(page.getByTestId("setup-s5-foot")).toContainText("FLOW never changes them");
    await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
    await page.reload();
    await expect(page.getByTestId("setup-s5-foot")).toHaveText(zh["setup.s5.foot"]);
    await page.goto("/setup?step=4");
    await expect(page.getByTestId("setup-s4-foot")).toHaveText(zh["setup.s4.foot"]);
  });
});
