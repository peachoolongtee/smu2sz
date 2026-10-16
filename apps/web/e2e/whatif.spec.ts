import { expect, test } from "./fixtures";
import { checkedDeal, resetBooks } from "./helpers";

/**
 * What-if sandbox in mock mode: the page opens on the buyer's actual offer (REJECT), moving the terms
 * slider back to 45 days changes the hypothetical verdict, and the presets jump to the counters.
 * Every figure is a server-formatted string from mocks/whatif_presets.json.
 */
test("what-if: moving the terms slider changes the hypothetical verdict", async ({ page, request }) => {
  await resetBooks(request);
  // The sandbox is run for a negotiation: it opens on that offer's own terms (never on a sample).
  await checkedDeal(page);
  await page.goto(page.url().replace("/deals", "/whatif"));
  await expect(page.getByRole("heading", { name: "What-if sandbox", level: 1 })).toBeVisible();

  const outcome = page.getByTestId("whatif-outcome");
  await expect(outcome).toHaveAttribute("data-outcome", "REJECT");
  await expect(page.getByTestId("whatif-codes")).toContainText("AGG_CONCESSION_EXCEEDED");
  await expect(page.getByTestId("whatif-codes")).toContainText("Gives buyers more than your limit allows");
  await expect(page.getByTestId("whatif-forward-total")).toHaveText("¥28,326.92");
  await expect(page.getByText("Reserve breach in 47 days").first()).toBeVisible();
  // Level 1 is the summary: the verdict in words and three figures; the engine's cards wait behind one disclosure.
  await expect(outcome).toHaveText("Breaks your limits");
  await expect(page.getByTestId("whatif-cash-fig")).toHaveText("Below it for 15 days"); // the server's cash word (reserve.cash_text), not the breach day's
  // The assumption sentence stands under the subject, as sent. The mock recording was made without an offer, so it has no negotiation clause and no compare_text; the live API adds both (e2e/slice-b.spec.ts).
  await expect(page.getByTestId("whatif-scope-text")).toContainText("The sandbox applies the terms to every Foshan invoice for the next 12 months, not only the next one");
  await expect(page.getByTestId("whatif-plan-cost")).toContainText("¥1,468.05");
  const details = page.getByTestId("whatif-details");
  await expect(details).not.toHaveAttribute("open", "");
  await expect(page.locator("#whatif-meter")).toBeHidden();
  await details.locator("> summary").click();
  await expect(page.locator("#whatif-meter")).toBeVisible();
  await expect(page.getByTestId("whatif-engine-outcome")).toHaveAttribute("data-outcome", "REJECT");
  await details.locator("> summary").click();

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

  // Option A preset: 45 days, 0.85% on ¥260,000 of the invoice.
  await page.getByTestId("whatif-preset-option_a").click();
  await expect(page.getByTestId("whatif-discount-readout")).toHaveText("0.85%");
  await expect(page.getByTestId("whatif-face-readout")).toHaveText("¥260,000.00");
  await expect(outcome).toHaveAttribute("data-outcome", "ACCEPT");
  await expect(page.getByTestId("whatif-cash-fig")).toHaveText("Below it for 12 days");

  // Back to the buyer's actual offer.
  await page.getByTestId("whatif-preset-actual").click();
  await expect(outcome).toHaveAttribute("data-outcome", "REJECT");
});
