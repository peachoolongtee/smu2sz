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
  await expect(page.getByTestId("whatif-codes")).toContainText("Gives buyers more than your limit allows");
  await expect(page.getByTestId("whatif-forward-total")).toHaveText("¥28,326.92");
  // Days are distances from today in Business mode; the verdict is in words, the figures are the server's.
  await expect(page.getByTestId("whatif-outcome")).toHaveText("Breaks your limits");
  await expect(page.getByTestId("whatif-cash-fig")).toHaveText("Below it in 47 days");

  // 60 -> 45 days with the arrow keys (5-day steps): no extension, so no concession breach.
  const terms = page.getByRole("slider", { name: "Payment terms" });
  await terms.focus();
  await terms.press("ArrowLeft");
  await terms.press("ArrowLeft");
  await terms.press("ArrowLeft");
  await expect(page.getByTestId("whatif-terms-readout")).toHaveText("45 days");
  // No terms extension any more, so no concession breach; but 1.2% early settlement is above the 0.88%
  // break-even, so the verifier counters at 0.85% rather than accepting.
  await expect(outcome).toHaveAttribute("data-outcome", "COUNTER");
  await expect(page.getByTestId("whatif-codes")).not.toContainText("AGG_CONCESSION_EXCEEDED");

  // Option A preset: 45 days, 0.85% on ¥257,200 of the invoice.
  await page.getByTestId("whatif-preset-option_a").click();
  await expect(page.getByTestId("whatif-discount-readout")).toHaveText("0.85%");
  await expect(page.getByTestId("whatif-face-readout")).toHaveText("¥257,200.00");
  await expect(outcome).toHaveAttribute("data-outcome", "ACCEPT");

  // Back to the buyer's actual offer.
  await page.getByTestId("whatif-preset-actual").click();
  await expect(outcome).toHaveAttribute("data-outcome", "REJECT");
});
