import { expect, test } from "./fixtures";
import { resetBooks } from "./helpers";

/**
 * What-if sandbox in mock mode: the page opens on the buyer's actual offer (REJECT), moving the terms
 * slider back to 45 days changes the hypothetical verdict, and the presets jump to the counters.
 * Every figure is a server-formatted string from mocks/whatif_presets.json.
 */
test("what-if: moving the terms slider changes the hypothetical verdict", async ({ page, request }) => {
  await resetBooks(request);
  await page.goto("/whatif");
  await expect(page.getByRole("heading", { name: "What-if sandbox", level: 1 })).toBeVisible();

  const outcome = page.getByTestId("whatif-outcome");
  await expect(outcome).toHaveAttribute("data-outcome", "REJECT");
  await expect(page.getByTestId("whatif-codes")).toContainText("AGG_CONCESSION_EXCEEDED");
  await expect(page.getByTestId("whatif-forward-total")).toHaveText("¥26,455.62");
  await expect(page.getByText("Breach day 47").first()).toBeVisible();

  // 60 -> 45 days with the arrow keys (5-day steps): no extension, so no concession breach.
  const terms = page.getByRole("slider", { name: "Payment terms" });
  await terms.focus();
  await terms.press("ArrowLeft");
  await terms.press("ArrowLeft");
  await terms.press("ArrowLeft");
  await expect(page.getByTestId("whatif-terms-readout")).toHaveText("45 days");
  // The 1% rebate is still in the package: within the cap, but only an early-pay discount on a named
  // invoice is accepted autonomously, so the owner must approve it.
  await expect(outcome).toHaveAttribute("data-outcome", "NEEDS_OWNER_APPROVAL");
  await expect(page.getByTestId("whatif-codes")).not.toContainText("AGG_CONCESSION_EXCEEDED");

  // Option A preset: 45 days, 0.85% on ¥211,800 of the invoice.
  await page.getByTestId("whatif-preset-option_a").click();
  await expect(page.getByTestId("whatif-discount-readout")).toHaveText("0.85%");
  await expect(page.getByTestId("whatif-face-readout")).toHaveText("¥211,800.00");
  await expect(outcome).toHaveAttribute("data-outcome", "ACCEPT");

  // Back to the buyer's actual offer.
  await page.getByTestId("whatif-preset-actual").click();
  await expect(outcome).toHaveAttribute("data-outcome", "REJECT");
});
