import { expect, test, type Page } from "@playwright/test";

/** Live-mode only: owner-token handling, the 401 state, borrower-file downloads and owner approval. */

const API = "http://localhost:8000";
const TOKEN = process.env.NEXT_PUBLIC_OWNER_TOKEN ?? "demo-owner-token";

async function walkTo(page: Page, steps: number) {
  await page.goto("/mandate");
  for (let i = 0; i < steps; i++) {
    const button = page.getByTestId("demo-next");
    await expect(button).toBeEnabled();
    await button.click();
    await expect(page.getByRole("region", { name: "Guided demo" }).locator("[aria-live=polite]")).toContainText(`${i + 1}/15`);
  }
}

test("every API request carries the owner token", async ({ page }) => {
  const seen: { url: string; token: string | undefined }[] = [];
  page.on("request", (r) => {
    if (r.url().startsWith(API) && r.method() !== "OPTIONS") seen.push({ url: r.url(), token: r.headers()["x-owner-token"] });
  });
  await walkTo(page, 4); // reset, compile, evaluate, plan
  await expect(page).toHaveURL(/\/funding/);
  expect(seen.length).toBeGreaterThan(5);
  for (const r of seen) expect(r.token, r.url).toBe(TOKEN);
});

test("a 401 from the API shows the owner-token message instead of a blank screen", async ({ page }) => {
  await page.route(`${API}/state`, (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "http://localhost:3000" },
      body: JSON.stringify({ detail: "owner token required" }),
    }),
  );
  await page.goto("/mandate");
  await expect(page.getByText(/rejected the owner token/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

test("the borrower file downloads as HTML and Word, and the owner approves both pending requests", async ({ page }) => {
  await walkTo(page, 13); // through the borrower file: capex apply + borrower file are both pending
  await expect(page).toHaveURL(/\/approvals/);

  await page.goto("/capex");
  await expect(page.getByTestId("borrower-file-downloads")).toBeVisible();
  const [html] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-html").click()]);
  expect(html.suggestedFilename()).toMatch(/^BF-.*\.html$/);
  const [docx] = await Promise.all([page.waitForEvent("download"), page.getByTestId("download-docx").click()]);
  expect(docx.suggestedFilename()).toMatch(/^BF-.*\.docx$/);

  await page.goto("/approvals");
  await expect(page.getByText("2 pending")).toBeVisible();
  const approve = page.getByRole("button", { name: "Approve" });
  await approve.first().click();
  await expect(page.getByText("1 pending")).toBeVisible();
  await approve.first().click();
  await expect(page.getByText("0 pending")).toBeVisible();
  await expect(page.getByText("Approved")).toHaveCount(2);

  await page.goto("/ledger");
  await expect(page.getByTestId("chain-status")).toContainText("Chain valid");
});

test("an approval is refused when the server does not recognise the owner", async ({ page }) => {
  await walkTo(page, 13);
  // Simulate a wrong token: the server treats the caller as the agent and the executor refuses.
  await page.route(`${API}/approvals/APR-*`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const headers = { ...route.request().headers(), "x-owner-token": "wrong-token" };
    return route.continue({ headers });
  });
  await page.goto("/approvals");
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByText(/only the owner may decide|rejected the owner token/i)).toBeVisible();
  await expect(page.getByText("2 pending")).toBeVisible();
});
