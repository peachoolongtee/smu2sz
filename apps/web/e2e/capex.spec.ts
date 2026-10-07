import { expect, test } from "./fixtures";

/**
 * The borrower file on the Business Capex page (mock mode): its contents read like the downloaded file, with the tables
 * as tables under the server's column names, hashes shortened on screen, and the owner's estimates marked.
 */
test("the borrower file's contents show its tables with their columns, not joined strings", async ({ page }) => {
  await page.goto("/capex");
  await page.getByRole("button", { name: "Evaluate the ¥600k machine" }).click();
  await expect(page.getByTestId("capex-recommendation")).toBeVisible();
  await page.getByTestId("capex-file").click();
  const card = page.getByTestId("capex-borrower-file");
  await expect(card).toBeVisible();
  await card.getByText("What is in the file").click();

  const forecast = card.getByTestId("file-section-forecast_13w");
  await expect(forecast.getByRole("columnheader", { name: "Closing cash", exact: true })).toBeVisible();
  await expect(forecast.getByRole("row", { name: /Week 1 \(days 1–7\)/ }).getByRole("cell")).toHaveCount(5);
  await expect(forecast).not.toContainText(" · ");
  await expect(card.getByTestId("file-section-trajectory_12m").getByRole("columnheader", { name: "Leverage" })).toBeVisible();

  // A 64-character hash never shows whole on the page; the owner's own figures are marked.
  await expect(card).not.toContainText(/[0-9a-f]{64}/);
  await expect(card.getByText("Your estimate").first()).toBeVisible();
  // Mock mode has no file to download and says where it can be downloaded.
  await expect(card.getByTestId("borrower-file-downloads")).toContainText("live mode");
});
