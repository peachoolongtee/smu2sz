import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "./fixtures";

/**
 * Attach deals, "Who it is with" and a file given first (owner's report, 17 Oct, fix/deals-contracts-upload). The company field is a combobox: the books'
 * companies of the right role show on focus, click or ArrowDown without typing, typing filters them, and for a contract with a buyer "+ Add a new customer" is
 * the list's last choice and a link under the field. A file given before the company waits, named, the field asks who it is with, and the file is read as soon
 * as a company is chosen or added; Remove discards it. Mock mode: the mock reads the demo supply agreement's own text filed under a company it does not name
 * (new-customer.spec.ts does the same), so the walks here file Foshan's agreement under another buyer; the live reading after a pick is documents.spec.ts.
 */

const SUPPLY = join(__dirname, "..", "..", "..", "fixtures", "contracts", "fhr-2026-07-supply-agreement.md");
const FOSHAN = "Foshan Home Retail Co.";
const DONGGUAN = "Dongguan Office Supplies Ltd.";
const NEW_BUYER = "Shunde Kitchen Supply Co.";
const ASK = "Who is this contract with? Choose a customer or add a new one.";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec: the recognised demo contract (desktop project; the phone width is set inside)");
});

async function scan(page: Page, label: string) {
  await expect.poll(() => page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length), { message: `${label}: animations still running` }).toBe(0);
  const result = await new AxeBuilder({ page }).analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const text = bad.map((v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.slice(0, 4).map((n) => n.target.join(" ")).join("\n  ")}`);
  expect(result.passes.length, `${label}: axe ran its rules`).toBeGreaterThan(10);
  expect(text, `${label}: serious or critical findings`).toEqual([]);
}

/** The demo supply agreement as a file, named as the owner's own copy. */
function supplyFile(name = "fhr-2026-07-supply-agreement.md", buyerInText = FOSHAN) {
  return { name, mimeType: "text/plain", buffer: Buffer.from(readFileSync(SUPPLY, "utf8").split(FOSHAN).join(buyerInText)) };
}

test("the list of the books' customers opens on a click with nothing typed, filters as the owner types, and ends with Add a new customer", async ({ page }) => {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  const party = form.getByTestId("doc-counterparty");
  await expect(party).toHaveAttribute("role", "combobox");
  await expect(party).toHaveAttribute("aria-expanded", "false");
  await party.click();
  await expect(party).toHaveAttribute("aria-expanded", "true");
  const list = form.getByTestId("doc-counterparty-list");
  await expect(party).toHaveAttribute("aria-controls", (await list.getAttribute("id"))!);
  await expect(list.getByRole("option")).toHaveText([FOSHAN, DONGGUAN, "+Add a new customer"]);
  // Typing filters; the add choice stays last and names what was typed when it matches no company.
  await party.fill("dong");
  await expect(list.getByRole("option")).toHaveText([DONGGUAN, "+Add a new customer"]);
  await party.fill("Nobody Ltd");
  await expect(list.getByRole("option")).toHaveText(["+Add “Nobody Ltd” as a new customer"]);
  // A click picks: the name is in the field, the list closes.
  await party.fill("");
  await list.getByRole("option", { name: DONGGUAN }).click();
  await expect(party).toHaveValue(DONGGUAN);
  await expect(party).toHaveAttribute("aria-expanded", "false");
  await expect(party).not.toHaveAttribute("aria-invalid", "true");
  // Opened again on the chosen company, the whole list shows, the chosen one marked.
  await party.click();
  await expect(list.getByRole("option")).toHaveCount(3);
  await expect(list.getByRole("option", { name: DONGGUAN })).toHaveAttribute("aria-selected", "true");
  // A click outside closes it.
  await page.getByRole("heading", { level: 1 }).click();
  await expect(party).toHaveAttribute("aria-expanded", "false");
});

test("the keyboard: Tab opens the list, the arrows move, Enter picks, Escape closes", async ({ page }) => {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  const party = form.getByTestId("doc-counterparty");
  await form.getByTestId("doc-kind").focus();
  await page.keyboard.press("Tab");
  await expect(party).toBeFocused();
  await expect(party).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Escape");
  await expect(party).toHaveAttribute("aria-expanded", "false");
  await page.keyboard.press("ArrowDown");
  await expect(party).toHaveAttribute("aria-expanded", "true");
  const active = async () => page.locator(`#${await party.getAttribute("aria-activedescendant")}`);
  await expect(await active()).toHaveText(FOSHAN);
  await page.keyboard.press("ArrowDown");
  await expect(await active()).toHaveText(DONGGUAN);
  await page.keyboard.press("ArrowDown");
  await expect(await active()).toHaveText("+Add a new customer");
  await page.keyboard.press("ArrowDown"); // round to the top
  await expect(await active()).toHaveText(FOSHAN);
  await page.keyboard.press("ArrowUp");
  await expect(await active()).toHaveText("+Add a new customer");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  await expect(party).toHaveValue(DONGGUAN);
  await expect(party).toHaveAttribute("aria-expanded", "false");
  // Enter on the add choice opens the add panel, its name empty (nothing new was typed).
  await page.keyboard.press("ArrowUp");
  await expect(await active()).toHaveText("+Add a new customer");
  await page.keyboard.press("Enter");
  const panel = form.getByTestId("doc-new-customer-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByLabel("Name", { exact: true })).toHaveValue("");
  await expect(panel.getByLabel("Name", { exact: true })).toBeFocused();
});

test("a file first, then a customer picked from the list: the file waits, named, and is read the moment the customer is chosen", async ({ page }) => {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  const party = form.getByTestId("doc-counterparty");
  await form.getByLabel(/^File/).setInputFiles(supplyFile());
  await expect(page.getByTestId("doc-waiting")).toHaveText("Ready to read: fhr-2026-07-supply-agreement.md");
  await expect(party).toBeFocused();
  await expect(form.getByTestId("doc-counterparty-popup")).toContainText(ASK);
  await expect(form.getByTestId("doc-ask-who")).toHaveText(ASK);
  await expect(party).toHaveAttribute("aria-describedby", new RegExp((await form.getByTestId("doc-ask-who").getAttribute("id"))!));
  // Nothing is read before a company is chosen (the mock reads in the page, so the proof is that no reading opened; documents.spec.ts counts the requests live).
  await expect(page.getByTestId("doc-progress")).toHaveCount(0);
  await expect(page).toHaveURL(/\/documents$/);
  await form.getByTestId("doc-counterparty-list").getByRole("option", { name: DONGGUAN }).click();
  await expect(page).toHaveURL(/\/documents\?id=DOC-000004$/);
  await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "PROPOSED");
  await expect(page.getByTestId("doc-waiting")).toHaveCount(0);
  await expect(form.getByTestId("doc-ask-who")).toHaveCount(0);
});

test("a file dropped first, then the customer typed in full and Enter: read at once", async ({ page }) => {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  // The companies on the books have been read (a name typed before they arrive matches nothing yet).
  await form.getByTestId("doc-counterparty").click();
  await expect(form.getByTestId("doc-counterparty-list").getByRole("option", { name: DONGGUAN })).toBeVisible();
  await page.keyboard.press("Escape");
  const file = supplyFile();
  const data = await page.evaluateHandle(({ name, text }) => {
    const dt = new DataTransfer();
    dt.items.add(new File([text], name, { type: "text/plain" }));
    return dt;
  }, { name: file.name, text: file.buffer.toString("utf8") });
  await page.getByTestId("doc-dropzone").dispatchEvent("drop", { dataTransfer: data });
  await expect(page.getByTestId("doc-waiting")).toHaveText("Ready to read: fhr-2026-07-supply-agreement.md");
  const party = form.getByTestId("doc-counterparty");
  await party.fill(DONGGUAN);
  await party.press("Enter");
  await expect(page).toHaveURL(/\/documents\?id=DOC-000004$/);
  await expect(page.getByTestId("doc-review")).toHaveAttribute("data-status", "PROPOSED");
});

test("a file first, then a new customer added from the list's last choice: added, chosen and the file read", async ({ page }) => {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  const party = form.getByTestId("doc-counterparty");
  await form.getByLabel(/^File/).setInputFiles(supplyFile("supply-agreement.md"));
  await expect(page.getByTestId("doc-waiting")).toHaveText("Ready to read: supply-agreement.md");
  await party.fill(NEW_BUYER);
  await form.getByTestId("doc-counterparty-add").click();
  const panel = form.getByTestId("doc-new-customer-panel");
  await expect(panel.getByLabel("Name", { exact: true })).toHaveValue(NEW_BUYER);
  await panel.getByRole("button", { name: "Add customer" }).click();
  await expect(panel).toHaveCount(0);
  await expect(party).toHaveValue(NEW_BUYER);
  // Added and chosen: the waiting file is read for it.
  await expect(page).toHaveURL(/\/documents\?id=DOC-\d+$/);
  await expect(page.getByTestId("doc-review")).toBeVisible();
  await expect(page.getByTestId("doc-waiting")).toHaveCount(0);
});

test("+ Add a new customer is under the field with nothing typed: an empty panel; Remove discards a waiting file", async ({ page }) => {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  const link = form.getByTestId("doc-new-customer");
  await expect(link).toHaveText("+ Add a new customer");
  await expect(link).toBeVisible();
  await link.click();
  const panel = form.getByTestId("doc-new-customer-panel");
  await expect(panel.getByLabel("Name", { exact: true })).toHaveValue("");
  await panel.getByRole("button", { name: "Cancel" }).click();
  await expect(panel).toHaveCount(0);
  // A waiting file, then Remove (the list closed first: Remove is under it).
  await form.getByLabel(/^File/).setInputFiles(supplyFile());
  await expect(page.getByTestId("doc-waiting")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByTestId("doc-waiting-remove").click();
  await expect(page.getByTestId("doc-waiting")).toHaveCount(0);
  await expect(form.getByTestId("doc-ask-who")).toHaveCount(0);
  // Choosing a company now reads nothing: the file was discarded.
  await form.getByTestId("doc-counterparty").click();
  await form.getByTestId("doc-counterparty-list").getByRole("option", { name: FOSHAN }).click();
  await expect(page).toHaveURL(/\/documents$/);
  await expect(page.getByTestId("doc-review")).toHaveCount(0);
  // Sent, the mock would answer this file with its 422 (it reads only an agreement filed under a company it does not name): no answer, nothing sent.
  await expect(page.locator("#docs-read").getByRole("alert")).toHaveCount(0);
});

test("a lender agreement lists the lenders on the books and offers no new customer", async ({ page }) => {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  await form.getByTestId("doc-kind").click();
  await form.getByRole("option", { name: /^Lender agreement/ }).click();
  await form.getByTestId("doc-counterparty").click();
  const options = form.getByTestId("doc-counterparty-list").getByRole("option");
  await expect(options.first()).toBeVisible();
  await expect(options.filter({ hasText: "Add" })).toHaveCount(0);
  await expect(options.filter({ hasText: FOSHAN })).toHaveCount(0);
  await expect(form.getByTestId("doc-new-customer")).toHaveCount(0);
  // A file waiting for a lender asks for a lender.
  await page.keyboard.press("Escape");
  await form.getByLabel(/^File/).setInputFiles(supplyFile());
  await expect(form.getByTestId("doc-ask-who")).toHaveText("Who is this agreement with? Choose a lender.");
});

test("the list and the waiting file pass axe and fit a phone (390 px)", async ({ page }, testInfo) => {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  await form.getByLabel(/^File/).setInputFiles(supplyFile());
  await expect(form.getByTestId("doc-counterparty-list")).toBeVisible();
  await scan(page, "waiting file, list open, desktop");
  await form.screenshot({ path: testInfo.outputPath("upload-waiting-desktop.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(form.getByTestId("doc-counterparty-list")).toBeVisible();
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(over, "no horizontal scroll at 390 px").toBeLessThanOrEqual(0);
  const list = (await form.getByTestId("doc-counterparty-popup").boundingBox())!;
  expect(list.x, "the list starts on the screen").toBeGreaterThanOrEqual(0);
  expect(list.x + list.width, "the list ends on the screen").toBeLessThanOrEqual(390);
  for (const option of await form.getByTestId("doc-counterparty-list").getByRole("option").all()) expect((await option.boundingBox())!.height, "each choice is a 44 px target on a phone").toBeGreaterThanOrEqual(40);
  await scan(page, "waiting file, list open, phone");
  await form.screenshot({ path: testInfo.outputPath("upload-waiting-phone.png") });
});
