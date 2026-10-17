import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "./fixtures";

/**
 * Attach deals with a customer who is not on the books yet (feat/new-customer-base). The upload form offers to add the
 * buyer typed, right under "Who it is with", and chooses it once added. A contract filed under a company it does not name
 * (the party check's blocking PARTY_NOT_NAMED flag) offers, under that flag, to file it under a party it does name, adding a
 * buyer not on the books as a new customer, or to discard the reading. Mock mode: the mock adds the customer for the session
 * and recognises the demo supply agreement's own text (or that text naming another buyer) filed under another company. The
 * live specs follow with the API.
 */

const SUPPLY = join(__dirname, "..", "..", "..", "fixtures", "contracts", "fhr-2026-07-supply-agreement.md");
const FOSHAN = "Foshan Home Retail Co.";
const DONGGUAN = "Dongguan Office Supplies Ltd.";
const NEW_BUYER = "Shunde Kitchen Supply Co.";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec: the session's customers and the recognised demo contract (desktop project; the phone width is set inside)");
});

async function scan(page: Page, label: string) {
  await expect.poll(() => page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length), { message: `${label}: animations still running` }).toBe(0);
  const result = await new AxeBuilder({ page }).analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const text = bad.map((v) => `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.slice(0, 4).map((n) => n.target.join(" ")).join("\n  ")}`);
  expect(result.passes.length, `${label}: axe ran its rules`).toBeGreaterThan(10);
  expect(text, `${label}: serious or critical findings`).toEqual([]);
}

async function noSideScroll(page: Page, label: string) {
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(over, `${label}: no horizontal scroll`).toBeLessThanOrEqual(0);
}

/** Opens the add panel for the name typed into "Who it is with". */
async function openPanel(page: Page, typed: string) {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  await form.getByLabel("Who it is with").fill(typed);
  await form.getByTestId("doc-new-customer").click();
  const panel = form.getByTestId("doc-new-customer-panel");
  await expect(panel).toBeVisible();
  return { form, panel, party: form.getByLabel("Who it is with") };
}

/** Uploads the demo supply agreement (optionally naming another buyer) as a contract with the company typed. */
async function uploadContract(page: Page, filedUnder: string, buyerInText = FOSHAN) {
  await page.goto("/documents");
  const form = page.locator("#docs-read");
  await expect(form.getByLabel("What it is")).toHaveText("Contract with a buyer");
  await form.getByLabel("Who it is with").fill(filedUnder);
  // Chosen once the companies on the books have been read.
  await expect(form.getByLabel("Who it is with")).not.toHaveAttribute("aria-invalid", "true");
  const text = readFileSync(SUPPLY, "utf8").split(FOSHAN).join(buyerInText);
  await form.getByLabel(/^File/).setInputFiles({ name: "supply-agreement.md", mimeType: "text/plain", buffer: Buffer.from(text) });
  await expect(page).toHaveURL(/\/documents\?id=DOC-000004$/);
  const review = page.getByTestId("doc-review");
  await expect(review).toHaveAttribute("data-status", "PROPOSED");
  return review;
}

test.describe("adding a customer on Attach deals", () => {
  test("a name not on the books offers to add it; once added, the field has it chosen", async ({ page }) => {
    await page.goto("/documents");
    const form = page.locator("#docs-read");
    const party = form.getByLabel("Who it is with");
    await party.fill(NEW_BUYER);
    // In the place of the old hint, a small text button.
    const offer = form.getByTestId("doc-new-customer");
    await expect(offer).toHaveText(`Add “${NEW_BUYER}” as a new customer`);
    await expect(party).toHaveAttribute("aria-invalid", "true");
    await offer.click();
    const panel = form.getByTestId("doc-new-customer-panel");
    const name = panel.getByLabel("Name", { exact: true });
    await expect(name).toHaveValue(NEW_BUYER);
    await expect(name).toBeFocused();
    await panel.getByLabel("Short name (optional)").fill("Shunde");
    await panel.getByRole("button", { name: "Add customer" }).click();
    await expect(panel).toHaveCount(0);
    await expect(party).toHaveValue(NEW_BUYER);
    await expect(party).not.toHaveAttribute("aria-invalid", "true");
    await expect(form.getByTestId("doc-new-customer")).toHaveCount(0);
    // The server's sentence, quietly.
    await expect(form.getByTestId("doc-new-customer-done")).toHaveText(`You added ${NEW_BUYER} as a customer.`);
    // It is one of the companies on the books now: offered in the list and chosen when typed again.
    await expect(form.locator(`datalist option[value="${NEW_BUYER}"]`)).toHaveCount(1);
    await party.fill("");
    await party.fill(NEW_BUYER);
    await expect(form.getByTestId("doc-new-customer")).toHaveCount(0);
    // Chosen: Upload and read opens the file picker instead of asking for the company.
    const chooser = page.waitForEvent("filechooser");
    await page.getByTestId("doc-upload").click();
    await chooser;
    await expect(form.getByText("Type the name of the company this document is with first.")).toHaveCount(0);
  });

  test("a customer already on the books under that name is chosen, and the owner is told so", async ({ page }) => {
    const { form, panel, party } = await openPanel(page, "Nobody Ltd");
    await panel.getByLabel("Name", { exact: true }).fill(DONGGUAN);
    await panel.getByRole("button", { name: "Add customer" }).click();
    await expect(panel).toHaveCount(0);
    await expect(party).toHaveValue(DONGGUAN);
    await expect(form.getByTestId("doc-new-customer-done")).toHaveText(`${DONGGUAN} is already on your books, so it is chosen.`);
  });

  test("Cancel and Escape close the panel and add nothing; an empty name is said beside the button", async ({ page }) => {
    const { form, panel, party } = await openPanel(page, NEW_BUYER);
    await panel.getByLabel("Name", { exact: true }).fill("  ");
    await panel.getByRole("button", { name: "Add customer" }).click();
    const problem = panel.getByTestId("doc-new-customer-error");
    await expect(problem).toHaveText("Type the customer's name.");
    // Beside its button, on the same line on a desktop.
    const button = (await panel.getByRole("button", { name: "Add customer" }).boundingBox())!;
    const said = (await problem.boundingBox())!;
    expect(Math.abs(said.y + said.height / 2 - (button.y + button.height / 2)), "the error is beside the button").toBeLessThanOrEqual(12);
    await panel.getByRole("button", { name: "Cancel" }).click();
    await expect(panel).toHaveCount(0);
    await expect(party).toBeFocused();
    await expect(party).toHaveValue(NEW_BUYER);
    await expect(form.getByTestId("doc-new-customer")).toBeVisible();
    // Escape closes it too.
    await form.getByTestId("doc-new-customer").click();
    await expect(panel).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
    // Nothing was added: the name is still not on the books.
    await expect(form.locator(`datalist option[value="${NEW_BUYER}"]`)).toHaveCount(0);
  });

  test("a lender agreement keeps the plain hint: only a buyer is added here", async ({ page }) => {
    await page.goto("/documents");
    const form = page.locator("#docs-read");
    await form.getByTestId("doc-kind").click();
    await form.getByRole("option", { name: /^Lender agreement/ }).click();
    await form.getByLabel("Who it is with").fill("Nobody Bank");
    await expect(form.getByText("No company with that name is on your books.")).toBeVisible();
    await expect(form.getByTestId("doc-new-customer")).toHaveCount(0);
  });

  test("the panel passes axe and fits a phone", async ({ page }, testInfo) => {
    const { panel } = await openPanel(page, NEW_BUYER);
    await panel.getByLabel("Name", { exact: true }).fill("");
    await panel.getByRole("button", { name: "Add customer" }).click();
    await expect(panel.getByTestId("doc-new-customer-error")).toBeVisible();
    await scan(page, "add panel, desktop");
    await panel.getByLabel("Name", { exact: true }).fill(NEW_BUYER);
    await page.locator("#docs-read").screenshot({ path: testInfo.outputPath("add-panel-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(panel).toBeVisible();
    await noSideScroll(page, "add panel, phone");
    await scan(page, "add panel, phone");
    await page.locator("#docs-read").screenshot({ path: testInfo.outputPath("add-panel-phone.png") });
  });
});

test.describe("a contract filed under a company it does not name", () => {
  test("the blocking flag offers to file it under the buyer it names, or to discard it", async ({ page }) => {
    const review = await uploadContract(page, DONGGUAN);
    const flags = page.getByTestId("doc-flags");
    await expect(flags).toContainText(`not ${DONGGUAN} Check who it is with before confirming.`);
    await expect(flags).toContainText("This document does not name the company you chose, so it cannot be confirmed under it.");
    await expect(page.getByTestId("doc-confirm")).toBeDisabled();
    const actions = flags.getByTestId("doc-party-actions");
    // The buyer it names, on the books; the supplier (the owner's own company, not a customer) is not offered; then discard.
    await expect(actions.getByRole("button")).toHaveText([`File it under ${FOSHAN}`, "Discard this reading"]);
    await actions.getByRole("button", { name: `File it under ${FOSHAN}` }).click();
    await expect(page).toHaveURL(/\/documents\?id=DOC-000005$/);
    await expect(review).toHaveAttribute("data-id", "DOC-000005");
    await expect(review).toHaveAttribute("data-status", "PROPOSED");
    await expect(page.getByTestId("doc-party-actions")).toHaveCount(0);
    await expect(page.getByTestId("doc-flags")).toHaveCount(0);
    await expect(page.getByTestId("doc-confirm")).toBeEnabled();
    await expect(page.getByTestId("doc-replaces")).toContainText(`it was filed under ${DONGGUAN} before`);
    await expect(page.getByTestId("doc-row-DOC-000005")).toContainText(FOSHAN);
  });

  test("a buyer not on the books is added as a new customer and the contract filed under it", async ({ page }) => {
    await uploadContract(page, FOSHAN, NEW_BUYER);
    const actions = page.getByTestId("doc-party-actions");
    await expect(actions.getByRole("button")).toHaveText([`File it under ${NEW_BUYER} (add as a new customer)`, "Discard this reading"]);
    await actions.getByRole("button", { name: /add as a new customer/ }).click();
    await expect(page).toHaveURL(/\/documents\?id=DOC-000005$/);
    const review = page.getByTestId("doc-review");
    await expect(review).toHaveAttribute("data-id", "DOC-000005");
    await expect(page.locator("#doc-review")).toContainText(NEW_BUYER);
    await expect(page.getByTestId("doc-flags")).toHaveCount(0);
    // The reading is the text as filed: it names the new customer.
    await expect(page.getByTestId("doc-terms")).toContainText(NEW_BUYER);
    await page.getByTestId("doc-confirm").click();
    await expect(review).toHaveAttribute("data-status", "CONFIRMED");
    // The customer is on the books now: the upload form chooses it by name.
    const form = page.locator("#docs-read");
    await form.getByLabel("Who it is with").fill(NEW_BUYER);
    await expect(form.getByTestId("doc-new-customer")).toHaveCount(0);
  });

  test("discard rejects the reading", async ({ page }) => {
    const review = await uploadContract(page, DONGGUAN);
    await page.getByTestId("doc-party-actions").getByRole("button", { name: "Discard this reading" }).click();
    await expect(review).toHaveAttribute("data-status", "REJECTED");
    await expect(page.getByTestId("doc-result")).toHaveAttribute("data-status", "EXECUTED");
    await expect(page.getByTestId("doc-party-actions")).toHaveCount(0);
  });

  test("the actions pass axe and fit a phone", async ({ page }, testInfo) => {
    await uploadContract(page, FOSHAN, NEW_BUYER);
    const flags = page.getByTestId("doc-flags");
    await expect(flags.getByTestId("doc-party-actions")).toBeVisible();
    await scan(page, "mismatch actions, desktop");
    await flags.screenshot({ path: testInfo.outputPath("mismatch-actions-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(flags.getByTestId("doc-party-actions")).toBeVisible();
    await noSideScroll(page, "mismatch actions, phone");
    await scan(page, "mismatch actions, phone");
    // Brought to the top of the screen, the actions sit clear of the decision bar at the foot of a phone.
    const actions = flags.getByTestId("doc-party-actions");
    await flags.evaluate((el) => window.scrollBy(0, el.getBoundingClientRect().top - 72));
    await expect(actions.getByRole("button").last()).toBeInViewport({ ratio: 1 });
    const bar = (await page.locator("#doc-decide").boundingBox())!;
    const last = (await actions.getByRole("button").last().boundingBox())!;
    expect(last.y + last.height, "the actions are above the decision bar").toBeLessThanOrEqual(bar.y);
    await page.screenshot({ path: testInfo.outputPath("mismatch-actions-phone.png") });
  });
});
