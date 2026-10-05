import { expect, test } from "./fixtures";

/**
 * Your documents (mock mode): a buyer offer added by the owner is read and checked, with the agent's feedback in plain
 * words; another kind is filed and says the agent does not read it; a message read in the inbox shows up too.
 */

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the demo buyer message is the recorded fixture");
});

test("an added offer gets the agent's feedback; an invoice is filed, not read", async ({ page }) => {
  await page.goto("/documents");
  await expect(page.getByText("Nothing yet")).toBeVisible();

  await page.getByTestId("docs-demo").click();
  await page.getByTestId("docs-submit").click();
  const results = page.getByTestId("docs-results");
  await expect(results).toContainText("Foshan Home Retail offer.txt");
  await expect(results).toContainText("Checked");
  const feedback = results.getByTestId("docs-feedback");
  await expect(feedback).toContainText("Gives buyers more than your limit allows");
  await expect(feedback).toContainText("Option A");
  await expect(feedback).toContainText("¥28,326.92");

  await page.getByLabel("Invoice").check();
  await expect(page.getByTestId("docs-kind-note")).toContainText("does not read this kind of document yet");
  await page.getByTestId("docs-name").fill("INV-2031.txt");
  await page.getByTestId("docs-text").fill("Invoice INV-2031, ¥42,000, due in 45 days.");
  await page.getByTestId("docs-submit").click();
  await expect(results).toContainText("INV-2031.txt");
  await expect(results).toContainText("Filed, not read");

  // The full decision is one click away.
  await results.getByRole("button", { name: "Open the full decision" }).click();
  await expect(page).toHaveURL(/\/verdict/);
});

test("a message read in the inbox shows up with a way to check it", async ({ page }) => {
  await page.goto("/inbox");
  await page.getByTestId("inbox-msg-SEC").click();
  await expect(page.locator("#doc-SEC-msg")).toBeVisible();
  await page.goto("/documents");
  const results = page.getByTestId("docs-results");
  await expect(results).toContainText("FastCapital");
  await expect(results).toContainText("Read, not checked");
  await results.getByRole("button", { name: "Check against my limits" }).click();
  await expect(results).toContainText("Checked");
});
