import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import rec from "../mocks/buyer_inputs.json";
import off from "../mocks/buyer_inputs_off.json";
import { expect, test } from "./fixtures";

/**
 * The owner's Inputs sheet, /customers/{id}/inputs (map #88 Phase 2, ticket #97), in mock mode on the recorded API answers
 * (scripts/record-mocks.mjs --inputs, and --inputs --economics-off): the rows and their provenance words, the overview's "Edit these facts"
 * link landing here with its context and the back link returning, saving a margin turning the overview's "assumed for the Demo" into
 * "you entered" (read again), the server's 422 sentence, the economics fields off, Chinese, a phone, the keyboard and axe. Every string
 * asserted is read from the recording; the mock serves only the two saves it was recorded with (a margin of 25%, a margin of 150%).
 */

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded sheet");
});

const SHEET = "/customers/BUYER-1/inputs";
const row = (view: { fields: { key: string }[] }, key: string) => view.fields.find((f) => f.key === key) as Record<string, string | null>;

/** The overview as the server answers with the customer economics on (its "Edit these facts" link set). */
async function economicsOn(page: Page) {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-economics", "1"));
}

async function scan(page: Page, label: string) {
  const result = await new AxeBuilder({ page }).analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(result.passes.length, `${label}: axe ran its rules`).toBeGreaterThan(10);
  expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`), `${label}: serious or critical findings`).toEqual([]);
}

test("the sheet: three facts and the delay, each with where it came from, the check against the books and the firm's rows", async ({ page }) => {
  await page.goto(SHEET);
  const en = rec.opening.en;
  await expect(page.locator("h1")).toHaveText("Three facts FLOW cannot read from your books");
  await expect(page.getByText(en.eyebrow_text as string)).toBeVisible();
  const sales = row(en, "annual_sales");
  await expect(page.getByText(sales.label as string, { exact: true })).toBeVisible();
  await expect(page.getByTestId("inputs-input-annual_sales")).toHaveValue(sales.input_text as string);
  await expect(page.getByTestId("inputs-source-annual_sales")).toContainText(sales.note as string);
  await expect(page.getByTestId("inputs-provenance-annual_sales")).toContainText("projected from your books");
  const margin = row(en, "gross_margin");
  await expect(page.getByTestId("inputs-input-gross_margin")).toHaveValue("20%");
  await expect(page.getByTestId("inputs-provenance-gross_margin")).toContainText("assumed for the Demo");
  await expect(page.getByTestId("inputs-source-gross_margin")).toContainText(margin.note as string);
  await expect(page.getByTestId("inputs-check-ebitda_floor")).toHaveText(`${en.consistency[0].lead} ${en.consistency[0].text}`);
  // classification: context only, said by the server; choosing one shows that choice's own note
  await expect(page.getByTestId("inputs-class-note")).toHaveText(row(en, "classification").note as string);
  await page.getByTestId("inputs-class-STRATEGIC").click();
  await expect(page.getByTestId("inputs-class-STRATEGIC")).toHaveAttribute("aria-selected", "true");
  const strategic = en.fields.find((f) => f.key === "classification")!.options.find((o) => o.value === "STRATEGIC")!;
  await expect(page.getByTestId("inputs-class-note")).toHaveText(strategic.note);
  await expect(page.getByTestId("inputs-vat-note")).toHaveText(en.vat_note as string);
  await expect(page.getByText(en.footer_text as string)).toBeVisible();
  await expect(page.getByTestId("inputs-back")).toHaveText(en.context.back!.label);
});

test("Edit these facts lands here with the overview's context, and the back link returns to the overview", async ({ page }) => {
  await economicsOn(page);
  await page.goto("/customers/BUYER-1?invoice=RCV-A");
  await page.getByTestId("customer-edit").click();
  await expect(page).toHaveURL(/\/customers\/BUYER-1\/inputs\?invoice=RCV-A$/);
  await expect(page.getByTestId("inputs-sheet")).toBeVisible();
  await page.getByTestId("inputs-back").click();
  await expect(page).toHaveURL(new RegExp(`${rec.opening.en.context.back!.href}$`));
  await expect(page.getByTestId("customer-overview")).toBeVisible();
});

test("saving a margin: the server's words come back, and the overview's qualifier turns from assumed to what you entered", async ({ page }) => {
  await economicsOn(page);
  await page.goto("/customers/BUYER-1");
  const before = rec.overview_before.en.economics!.find((r) => r.key === "gross_margin")!;
  await expect(page.getByTestId("customer-economics-rows-gross_margin")).toContainText(before.note as string);
  await page.getByTestId("customer-edit").click();
  await page.getByTestId("inputs-input-gross_margin").fill("25%");
  await page.getByTestId("inputs-save").click();
  await expect(page.getByTestId("inputs-status")).toHaveText("Saved. The facts below are what FLOW now holds.");
  const after = row(rec.after_margin.en, "gross_margin");
  await expect(page.getByTestId("inputs-input-gross_margin")).toHaveValue(after.input_text as string);
  await expect(page.getByTestId("inputs-provenance-gross_margin")).toHaveText(`${after.provenance_text} · ${after.entered_day_text}`);
  await page.getByTestId("inputs-back").click();
  const now = rec.overview_after.en.economics!.find((r) => r.key === "gross_margin")!;
  await expect(page.getByTestId("customer-economics-rows-gross_margin")).toContainText(now.note as string);
  await expect(page.getByTestId("customer-economics-rows-gross_margin")).toContainText(now.value_display);
});

test("a value the field does not take: the server's sentence, under the field, and nothing saved", async ({ page }) => {
  await page.goto(SHEET);
  await page.getByTestId("inputs-input-gross_margin").fill("150%");
  await page.getByTestId("inputs-save").click();
  await expect(page.getByTestId("inputs-error")).toHaveText(rec.rejected.en.detail.message);
  await expect(page.getByTestId("inputs-status")).toHaveText("");
  await expect(page.getByTestId("inputs-input-gross_margin")).toHaveAttribute("aria-invalid", "true");
});

test("a Save that partly fails: what saved reads as the server holds it and is not sent again, what failed keeps the owner's value and why", async ({ page }) => {
  await page.goto(SHEET);
  await page.getByTestId("inputs-input-gross_margin").fill("25%");  // recorded: saved
  await page.getByTestId("inputs-input-typical_delay").fill("10");  // not recorded: the mock refuses it
  await page.getByTestId("inputs-save").click();
  await expect(page.getByTestId("inputs-status")).toHaveText("Saved. The facts below are what FLOW now holds.");
  const after = row(rec.after_margin.en, "gross_margin");
  await expect(page.getByTestId("inputs-provenance-gross_margin")).toHaveText(`${after.provenance_text} · ${after.entered_day_text}`);
  await expect(page.getByTestId("inputs-input-typical_delay")).toHaveValue("10");
  await expect(page.getByTestId("inputs-error")).toHaveCount(1);
  await expect(page.getByTestId("inputs-input-typical_delay")).toHaveAttribute("aria-invalid", "true");
});

test("with the customer economics off: the server's sentence as a quiet notice and no form", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-economics-off", "1"));
  await page.goto(SHEET);
  await expect(page.getByTestId("inputs-off")).toHaveText(off.en.economics_off_text as string);
  await expect(page.getByTestId("inputs-save")).toHaveCount(0);
  await expect(page.locator("form")).toHaveCount(0);
});

test("in Chinese the sheet reads in Chinese with the same figures", async ({ page }) => {
  await page.goto(SHEET);
  await page.evaluate(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.goto(SHEET);
  const zh = rec.opening.zh;
  await expect(page.locator("h1")).toHaveText("FLOW 无法从您的账目中读出的三项信息");
  await expect(page.getByTestId("inputs-input-annual_sales")).toHaveValue(row(zh, "annual_sales").input_text as string);
  await expect(page.getByTestId("inputs-provenance-gross_margin")).toContainText(row(zh, "gross_margin").provenance_text as string);
  await expect(page.getByTestId("inputs-check-ebitda_floor")).toContainText(zh.consistency[0].text);
  await expect(page.getByTestId("inputs-save")).toHaveText("保存这些信息");
  await page.getByTestId("inputs-input-gross_margin").fill("150%");
  await page.getByTestId("inputs-save").click();
  await expect(page.getByTestId("inputs-error")).toHaveText(rec.rejected.zh.detail.message);
  await scan(page, `${SHEET} zh`);
});

test("on a phone the title and the first fact are in the first screen, Save is reachable, nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(SHEET);
  await expect(page.locator("h1")).toBeInViewport();
  await expect(page.getByTestId("inputs-input-annual_sales")).toBeInViewport();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.getByTestId("inputs-save").scrollIntoViewIfNeeded();
  await expect(page.getByTestId("inputs-save")).toBeInViewport();
});

test("by keyboard alone: type a margin, reach Save and save", async ({ page }) => {
  await page.goto(SHEET);
  await page.getByTestId("inputs-input-gross_margin").focus();
  await page.keyboard.press("ControlOrMeta+a");
  await page.keyboard.type("25%");
  await page.keyboard.press("Enter");  // the form submits from its field
  await expect(page.getByTestId("inputs-status")).toHaveText("Saved. The facts below are what FLOW now holds.");
  const save = page.getByTestId("inputs-save");
  await save.focus();
  await expect(save).toBeFocused();
});

test("axe finds nothing serious on the sheet", async ({ page }) => {
  await page.goto(SHEET);
  await expect(page.getByTestId("inputs-sheet")).toBeVisible();
  await scan(page, SHEET);
});
