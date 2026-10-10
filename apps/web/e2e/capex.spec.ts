import { expect, test } from "./fixtures";

/**
 * The borrower file on the capex page (mock mode): its contents read like the downloaded file, with the tables as tables
 * under the server's column names, hashes shortened on screen, and the owner's estimates marked (feat/upgrading).
 */
test("the borrower file's contents show its tables with their columns, not joined strings", async ({ page }) => {
  await page.goto("/capex");
  await page.getByRole("button", { name: "Evaluate the ¥600k machine" }).click();
  await expect(page.getByTestId("capex-recommendation")).toBeVisible();
  await page.getByTestId("capex-file").click();
  const card = page.locator("#file");
  await expect(card.getByTestId("file-sections")).toBeVisible();

  const forecast = card.getByTestId("file-section-forecast_13w");
  await expect(forecast.getByRole("columnheader", { name: "Closing cash", exact: true })).toBeVisible();
  await expect(forecast.getByRole("row", { name: /Week 1 \(days 1–7\)/ }).getByRole("cell")).toHaveCount(5);
  await expect(forecast).not.toContainText(" · ");
  await expect(card.getByTestId("file-section-trajectory_12m").getByRole("columnheader", { name: "Leverage" })).toBeVisible();

  // A 64-character hash never shows whole on the page; the owner's own figures are marked.
  await expect(card.getByTestId("file-sections")).not.toContainText(/[0-9a-f]{64}/);
  await expect(card.getByText("Your estimate").first()).toBeVisible();
});

test("how this was worked out reads as short headings, with the server's full assumptions one tap away", async ({ page }) => {
  await page.goto("/capex");
  await page.getByRole("button", { name: "Evaluate the ¥600k machine" }).click();
  await page.getByText("How this was worked out").click();
  const basis = page.getByTestId("capex-basis");
  await expect(basis.locator("li")).toHaveCount(7);
  await expect(basis).toContainText("Lowest financing charges");
  await expect(basis).toContainText("¥22,000.00 a month from month 4 to month 60");
  await expect(basis).toContainText("more than 10.00% a year");
  await expect(page.getByTestId("capex-assumptions")).toBeHidden();
  await page.getByText("Full assumptions").click();
  await expect(page.getByTestId("capex-assumptions")).toContainText("ranked on lowest total financing charges");
});
