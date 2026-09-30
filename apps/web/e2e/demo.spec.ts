import { expect, test, type Page } from "@playwright/test";

/**
 * Walks the demo stepper in mock mode, in the order of docs/DEMO_FLOW.md, and asserts the golden numbers
 * from fixtures/golden/golden_values.json appear exactly as the server formats them.
 */

async function next(page: Page, url: RegExp) {
  const button = page.getByTestId("demo-next");
  await expect(button).toBeEnabled();
  await button.click();
  await expect(page).toHaveURL(url);
}

test("demo stepper walks Scene 1, Scene 2, Scene 3 and Security with the golden numbers", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/mandate/);

  // Setup: reset, then the signed mandate and its three tiers.
  await next(page, /\/mandate/);
  await expect(page.getByRole("heading", { name: "Mandate", level: 1 })).toBeVisible();
  await expect(page.getByText("Signature valid")).toBeVisible();
  await expect(page.getByText("¥300,000.00").first()).toBeVisible();
  await expect(page.getByText("¥5,000.00").first()).toBeVisible();

  // Scene 1: the offer is a loan.
  await next(page, /\/inbox/);
  await expect(page.locator("mark")).toHaveCount(3);
  await expect(page.getByText("Immediate discount").first()).toBeVisible();

  await next(page, /\/trajectory/);
  await expect(page.getByText("¥26,455.62").first()).toBeVisible();
  await expect(page.getByText(/day 47/i).first()).toBeVisible();
  await expect(page.getByText("¥254,960.00").first()).toBeVisible();

  await next(page, /\/funding/);
  await expect(page.getByText("10.8417%").first()).toBeVisible();
  await expect(page.getByText("0.88%").first()).toBeVisible();

  await next(page, /\/verdict/);
  await expect(page.getByTestId("outcome-badge")).toContainText("REJECT");
  await expect(page.getByTestId("violation-AGG_CONCESSION_EXCEEDED")).toContainText("¥26,455.62");
  await expect(page.getByTestId("violation-RESERVE_BREACH")).toContainText(/day 47/i);
  await expect(page.getByTestId("counter-CTR-A")).toContainText("¥2,641.94");
  await expect(page.getByTestId("counter-CTR-B")).toContainText("¥1,890.00");

  await next(page, /\/verdict/);
  await expect(page.getByTestId("negotiation-result")).toContainText("DEAL");
  await expect(page.getByTestId("negotiation-result")).toContainText("Option A");

  await next(page, /\/ledger/);
  await expect(page.getByTestId("chain-status")).toContainText("Chain valid");
  await expect(page.getByText("Draw facility").first()).toBeVisible();

  // Scene 2: the buyer walks, the gap is still covered.
  await next(page, /\/verdict/);
  await expect(page.getByTestId("negotiation-result")).toContainText("NO DEAL");

  await next(page, /\/funding/);
  await expect(page.getByTestId("plan-total")).toHaveText("¥2,712.94");
  await expect(page.getByText("¥5,040.00").first()).toBeVisible();
  await expect(page.getByText("¥3,392.25").first()).toBeVisible();

  await next(page, /\/ledger/);
  await expect(page.getByText("Submit invoice for financing").first()).toBeVisible();
  await expect(page.getByTestId("chain-status")).toContainText("Chain valid");

  await next(page, /\/verdict/);
  await expect(page.getByTestId("outcome-badge")).toContainText("REJECT");
  await expect(page.getByTestId("violation-AGG_CONCESSION_EXCEEDED")).toContainText("¥26,455.62");

  // Scene 3: capex.
  await next(page, /\/capex/);
  await expect(page.getByText("¥380,885.77").first()).toBeVisible();
  await expect(page.getByTestId("structure-loan_36m")).toContainText("¥18,144.62");
  await expect(page.getByTestId("structure-loan_18m")).toContainText("1.13");

  await next(page, /\/approvals/);
  await expect(page.getByText("Apply for the 36-month equipment term loan")).toBeVisible();

  // Security: the FastCapital message.
  await next(page, /\/security/);
  await expect(page.getByTestId("event-SE-1")).toContainText("UNKNOWN_COUNTERPARTY");
  await expect(page.getByTestId("event-SE-2")).toContainText("UNEVIDENCED_CLAIM");
  await expect(page.getByTestId("event-SE-3")).toContainText("DATA_EXTRACTION");
  await expect(page.getByText("¥0.00").first()).toBeVisible();

  await next(page, /\/evidence/);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-evidence").click()]);
  expect(download.suggestedFilename()).toBe("termsledger-evidence.jsonl");
  await expect(page.getByTestId("demo-next")).toBeDisabled();
});

test("Tier 2 approval queue approves the capex loan and logs it", async ({ page }) => {
  await page.goto("/mandate");
  for (let i = 0; i < 13; i++) {
    const button = page.getByTestId("demo-next");
    await expect(button).toBeEnabled();
    await button.click();
    await expect(page.getByTestId("demo-next")).toBeEnabled();
  }
  await expect(page).toHaveURL(/\/approvals/);
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByText("Approved").first()).toBeVisible();
  await page.goto("/ledger");
  await expect(page.getByTestId("chain-status")).toContainText("Chain valid");
});

test("the label toggle switches the UI to Chinese and back", async ({ page }) => {
  await page.goto("/mandate");
  await page.getByLabel("中文").check();
  await expect(page.getByRole("heading", { name: "授权书", level: 1 })).toBeVisible();
  await page.getByLabel("English").check();
  await expect(page.getByRole("heading", { name: "Mandate", level: 1 })).toBeVisible();
});

test("reset clears the session", async ({ page }) => {
  await page.goto("/mandate");
  await page.getByTestId("demo-next").click();
  await expect(page).toHaveURL(/\/mandate/);
  await page.getByTestId("demo-next").click();
  await expect(page).toHaveURL(/\/inbox/);
  await page.getByTestId("demo-reset").click();
  await expect(page).toHaveURL(/\/mandate/);
  await page.goto("/ledger");
  await expect(page.getByText("No operations yet")).toBeVisible();
});
